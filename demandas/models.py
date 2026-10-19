"""Modelos do núcleo: categorias, demandas e o histórico de cada demanda.

As `choices` só validam formulários. As regras críticas também ficam no banco,
como CheckConstraint/UniqueConstraint, para valerem venham os dados de onde vierem.
"""

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower

from core import relogio

# Texto vazio ou só com espaços (expressão regular do PostgreSQL).
_SO_ESPACOS = r"^\s*$"


class Origem(models.TextChoices):
    EMAIL = "email", "E-mail"
    CIRCULAR = "circular", "Circular"
    CHAT = "chat", "Chat (Teams/WhatsApp)"
    TELEFONE = "telefone", "Telefone"
    PRESENCIAL = "presencial", "Presencial"
    REUNIAO = "reuniao", "Reunião"
    SISTEMA = "sistema", "Sistema"
    OUTRO = "outro", "Outro"


class Prioridade(models.TextChoices):
    ALTA = "alta", "Alta"
    MEDIA = "media", "Média"
    BAIXA = "baixa", "Baixa"


class Status(models.TextChoices):
    NOVA = "nova", "Nova"
    A_FAZER = "a_fazer", "A fazer"
    EM_ANDAMENTO = "em_andamento", "Em andamento"
    AGUARDANDO = "aguardando", "Aguardando terceiro"
    CONCLUIDA = "concluida", "Concluída"
    CANCELADA = "cancelada", "Cancelada"


STATUS_ABERTOS = frozenset({Status.NOVA, Status.A_FAZER, Status.EM_ANDAMENTO, Status.AGUARDANDO})
STATUS_FECHADOS = frozenset({Status.CONCLUIDA, Status.CANCELADA})


class TipoEvento(models.TextChoices):
    CRIADA = "criada", "Criada"
    STATUS = "status", "Status"
    PRIORIDADE = "prioridade", "Prioridade"
    PRAZO = "prazo", "Prazo"
    NOTA = "nota", "Anotação"
    EDICAO = "edicao", "Edição"


class Categoria(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categorias",
        # O índice do UNIQUE (usuario, lower(nome)) já começa por usuario.
        db_index=False,
    )
    nome = models.CharField(max_length=60)
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]
        constraints = [
            # Sem diferenciar maiúsculas: "Fiscal" e "fiscal" seriam duplicadas.
            models.UniqueConstraint(
                F("usuario"), Lower("nome"), name="categoria_nome_unico_por_usuario"
            ),
            models.CheckConstraint(
                condition=~Q(nome__regex=_SO_ESPACOS), name="categoria_nome_nao_vazio"
            ),
        ]

    def __str__(self):
        return self.nome


class Demanda(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="demandas",
        # Os três índices compostos abaixo já começam por usuario.
        db_index=False,
    )
    titulo = models.CharField("título", max_length=200)
    descricao = models.TextField("descrição", blank=True)
    solicitante = models.CharField(max_length=120, blank=True)
    referencia = models.CharField("referência", max_length=120, blank=True)
    aguardando_quem = models.CharField("aguardando quem ou o quê", max_length=120, blank=True)
    origem = models.CharField(max_length=20, choices=Origem.choices, default=Origem.OUTRO)
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="demandas",
    )
    prioridade = models.CharField(
        max_length=10, choices=Prioridade.choices, default=Prioridade.MEDIA
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOVA)
    prazo = models.DateField(null=True, blank=True)
    recebida_em = models.DateTimeField(default=relogio.agora)
    status_alterado_em = models.DateTimeField(default=relogio.agora, editable=False)
    concluida_em = models.DateTimeField(null=True, blank=True, editable=False)
    criada_em = models.DateTimeField(default=relogio.agora, editable=False)
    atualizada_em = models.DateTimeField(auto_now=True)
    # Lock otimista: cada gravação incrementa a versão; quem salvar com versão
    # desatualizada (outra aba) é avisado em vez de sobrescrever.
    versao = models.PositiveIntegerField(default=1, editable=False)

    class Meta:
        ordering = ["-recebida_em"]
        constraints = [
            models.CheckConstraint(
                condition=Q(origem__in=Origem.values), name="demanda_origem_valida"
            ),
            models.CheckConstraint(
                condition=Q(prioridade__in=Prioridade.values), name="demanda_prioridade_valida"
            ),
            models.CheckConstraint(
                condition=Q(status__in=Status.values), name="demanda_status_valido"
            ),
            models.CheckConstraint(
                condition=~Q(titulo__regex=_SO_ESPACOS), name="demanda_titulo_nao_vazio"
            ),
            # Concluída se, e somente se, concluida_em estiver preenchida.
            models.CheckConstraint(
                condition=(
                    Q(status=Status.CONCLUIDA, concluida_em__isnull=False)
                    | (~Q(status=Status.CONCLUIDA) & Q(concluida_em__isnull=True))
                ),
                name="demanda_concluida_sse_data",
            ),
            # Aguardando terceiro se, e somente se, aguardando_quem estiver preenchido
            # (ao sair do status o campo é limpo; o valor fica no histórico).
            models.CheckConstraint(
                condition=(
                    (Q(status=Status.AGUARDANDO) & ~Q(aguardando_quem__regex=_SO_ESPACOS))
                    | (~Q(status=Status.AGUARDANDO) & Q(aguardando_quem=""))
                ),
                name="demanda_aguardando_sse_quem",
            ),
        ]
        indexes = [
            models.Index(
                fields=["usuario", "status", "prazo"], name="demanda_usuario_status_prazo"
            ),
            models.Index(fields=["usuario", "recebida_em"], name="demanda_usuario_recebida"),
            models.Index(fields=["usuario", "concluida_em"], name="demanda_usuario_concluida"),
        ]

    def __str__(self):
        return self.titulo

    @property
    def aberta(self) -> bool:
        return self.status in STATUS_ABERTOS


class EventoDemanda(models.Model):
    """Histórico da demanda. Só inclusão: eventos nunca são editados nem apagados
    individualmente (somem apenas junto com a própria demanda)."""

    demanda = models.ForeignKey(
        Demanda,
        on_delete=models.CASCADE,
        related_name="eventos",
        # O índice (demanda, criado_em) já começa por demanda.
        db_index=False,
    )
    tipo = models.CharField(max_length=20, choices=TipoEvento.choices)
    valor_anterior = models.CharField(max_length=60, blank=True)
    valor_novo = models.CharField(max_length=60, blank=True)
    texto = models.TextField(blank=True)
    criado_em = models.DateTimeField(default=relogio.agora, editable=False)

    class Meta:
        ordering = ["criado_em", "id"]
        verbose_name = "evento da demanda"
        verbose_name_plural = "eventos da demanda"
        constraints = [
            models.CheckConstraint(
                condition=Q(tipo__in=TipoEvento.values), name="evento_tipo_valido"
            ),
            models.CheckConstraint(
                condition=~Q(tipo=TipoEvento.NOTA) | ~Q(texto__regex=_SO_ESPACOS),
                name="evento_nota_com_texto",
            ),
        ]
        indexes = [
            models.Index(fields=["demanda", "criado_em"], name="evento_demanda_criado"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} em {self.criado_em:%d/%m/%Y %H:%M}"

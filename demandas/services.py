"""Regras de negócio das demandas. Toda gravação passa por aqui.

Cada função que grava em mais de uma tabela roda em transaction.atomic():
ou tudo é gravado (demanda + evento do histórico), ou nada é.
"""

from django.db import transaction

from core import relogio
from demandas.models import (
    STATUS_ABERTOS,
    Categoria,
    Demanda,
    EventoDemanda,
    Status,
    TipoEvento,
)
from demandas.transicoes import transicao_permitida

LIMITE_VALOR_EVENTO = 60
LIMITE_AGUARDANDO = 120


class ErroDeNegocio(Exception):
    """Erro com mensagem pronta para mostrar ao usuário."""


class ConflitoDeEdicao(ErroDeNegocio):
    """A demanda mudou (outra aba ou janela) depois que o formulário foi aberto."""


class TransicaoInvalida(ErroDeNegocio):
    pass


class DadosInvalidos(ErroDeNegocio):
    pass


MENSAGEM_CONFLITO = (
    "Esta demanda foi alterada em outra aba ou janela depois que você abriu a tela. "
    "Os dados mais recentes foram carregados; revise e salve de novo."
)


# --- Auxiliares -----------------------------------------------------------------


def _registrar(demanda: Demanda, tipo: str, anterior="", novo="", texto: str = "") -> None:
    EventoDemanda.objects.create(
        demanda=demanda,
        tipo=tipo,
        valor_anterior=str(anterior or "")[:LIMITE_VALOR_EVENTO],
        valor_novo=str(novo or "")[:LIMITE_VALOR_EVENTO],
        texto=texto,
    )


def _validar_categoria(usuario, categoria: Categoria | None) -> None:
    if categoria is not None and categoria.usuario_id != usuario.pk:
        raise DadosInvalidos("Categoria inválida.")


def _quem_obrigatorio(aguardando_quem: str) -> str:
    quem = (aguardando_quem or "").strip()
    if not quem:
        raise DadosInvalidos("Informe de quem ou do quê a demanda está aguardando.")
    return quem[:LIMITE_AGUARDANDO]


def _travar(demanda: Demanda, versao: int | None) -> Demanda:
    """Relê a demanda com trava de linha e confere a versão (lock otimista).

    A trava (SELECT ... FOR UPDATE) segura a linha até o fim da transação; a
    versão detecta mudanças feitas entre abrir a tela e salvar.
    """
    atual = Demanda.objects.select_for_update().get(pk=demanda.pk)
    if versao is not None and atual.versao != versao:
        raise ConflitoDeEdicao(MENSAGEM_CONFLITO)
    return atual


def _aplicar_status(demanda: Demanda, novo: str, aguardando_quem: str = "") -> None:
    """Muda o status em memória e registra o evento. Quem chama salva a demanda."""
    if not transicao_permitida(demanda.status, novo):
        raise TransicaoInvalida(
            f"Não é possível passar de “{Status(demanda.status).label}” "
            f"para “{Status(novo).label}”."
        )
    anterior = demanda.status
    texto = ""
    if anterior == Status.AGUARDANDO:
        texto = f"Aguardava: {demanda.aguardando_quem}"
    if novo == Status.AGUARDANDO:
        demanda.aguardando_quem = _quem_obrigatorio(aguardando_quem)
        texto = f"Aguardando: {demanda.aguardando_quem}"
    else:
        demanda.aguardando_quem = ""

    momento = relogio.agora()
    demanda.status = novo
    demanda.status_alterado_em = momento
    demanda.concluida_em = momento if novo == Status.CONCLUIDA else None
    _registrar(demanda, TipoEvento.STATUS, anterior, novo, texto)


def _iso(valor) -> str:
    return valor.isoformat() if valor else ""


def _rotulo(campo: str) -> str:
    return str(Demanda._meta.get_field(campo).verbose_name)


# --- Operações ------------------------------------------------------------------


@transaction.atomic
def criar_demanda(
    usuario,
    *,
    titulo: str,
    status: str = Status.NOVA,
    aguardando_quem: str = "",
    **campos,
) -> Demanda:
    """Cria a demanda e o evento "criada" na mesma transação."""
    _validar_categoria(usuario, campos.get("categoria"))
    if status not in STATUS_ABERTOS:
        raise DadosInvalidos("Uma demanda nova precisa começar em um status aberto.")
    quem = _quem_obrigatorio(aguardando_quem) if status == Status.AGUARDANDO else ""

    momento = relogio.agora()
    campos.setdefault("recebida_em", momento)
    demanda = Demanda.objects.create(
        usuario=usuario,
        titulo=titulo.strip(),
        status=status,
        aguardando_quem=quem,
        status_alterado_em=momento,
        criada_em=momento,
        **campos,
    )
    _registrar(demanda, TipoEvento.CRIADA, novo=status)
    return demanda


@transaction.atomic
def editar_demanda(
    demanda: Demanda,
    *,
    versao: int,
    dados: dict,
    status: str | None = None,
    aguardando_quem: str = "",
) -> Demanda:
    """Aplica os campos alterados, registrando no histórico o que mudou."""
    atual = _travar(demanda, versao)
    _validar_categoria(atual.usuario, dados.get("categoria"))

    houve_mudanca = False
    alterados: list[str] = []  # campos sem evento próprio, resumidos num evento "edição"
    for campo, valor in dados.items():
        anterior = getattr(atual, campo)
        if anterior == valor:
            continue
        houve_mudanca = True
        setattr(atual, campo, valor)
        if campo == "prioridade":
            _registrar(atual, TipoEvento.PRIORIDADE, anterior, valor)
        elif campo == "prazo":
            _registrar(atual, TipoEvento.PRAZO, _iso(anterior), _iso(valor))
        else:
            alterados.append(_rotulo(campo))

    if status and status != atual.status:
        _aplicar_status(atual, status, aguardando_quem)
        houve_mudanca = True
    elif atual.status == Status.AGUARDANDO:
        quem = _quem_obrigatorio(aguardando_quem)
        if quem != atual.aguardando_quem:
            atual.aguardando_quem = quem
            alterados.append(_rotulo("aguardando_quem"))
            houve_mudanca = True

    if alterados:
        _registrar(atual, TipoEvento.EDICAO, texto="Alterou: " + ", ".join(alterados) + ".")

    if houve_mudanca:
        atual.versao += 1
        atual.save()
    return atual


@transaction.atomic
def mudar_status(
    demanda: Demanda,
    novo: str,
    *,
    versao: int | None = None,
    aguardando_quem: str = "",
) -> Demanda:
    """Ações rápidas: iniciar, aguardar, concluir, cancelar, reabrir."""
    atual = _travar(demanda, versao)
    _aplicar_status(atual, novo, aguardando_quem)
    atual.versao += 1
    atual.save()
    return atual


def anotar(demanda: Demanda, texto: str) -> EventoDemanda:
    """Acrescenta uma anotação livre ao histórico (não altera a demanda)."""
    texto = (texto or "").strip()
    if not texto:
        raise DadosInvalidos("Escreva a anotação.")
    return EventoDemanda.objects.create(demanda=demanda, tipo=TipoEvento.NOTA, texto=texto)


@transaction.atomic
def excluir_demanda(demanda: Demanda) -> None:
    """Exclui a demanda; histórico e Top 3 vão junto (CASCADE)."""
    Demanda.objects.filter(pk=demanda.pk).delete()

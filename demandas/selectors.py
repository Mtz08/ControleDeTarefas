"""Consultas de demandas. Toda consulta parte do usuário logado (evita IDOR)."""

from datetime import date

from django.db.models import Case, DateField, F, IntegerField, Q, QuerySet, Value, When

from core import relogio
from demandas.models import STATUS_ABERTOS, Categoria, Demanda, Prioridade, Status

ITENS_POR_PAGINA = 25


def demandas_de(usuario) -> QuerySet[Demanda]:
    return Demanda.objects.filter(usuario=usuario).select_related("categoria")


def abertas_de(usuario) -> QuerySet[Demanda]:
    return demandas_de(usuario).filter(status__in=STATUS_ABERTOS)


def categorias_de(usuario, *, so_ativas: bool = False) -> QuerySet[Categoria]:
    categorias = Categoria.objects.filter(usuario=usuario)
    return categorias.filter(ativa=True) if so_ativas else categorias


def q_atrasada(hoje: date) -> Q:
    return Q(prazo__lt=hoje, status__in=STATUS_ABERTOS)


def ordenar_por_urgencia(demandas: QuerySet[Demanda], hoje: date) -> QuerySet[Demanda]:
    """Ordenação padrão: atrasadas primeiro (prazo mais antigo), depois prioridade
    (Alta → Baixa), prazo mais próximo (sem prazo por último) e recebida há mais tempo."""
    atrasada = q_atrasada(hoje)
    return demandas.annotate(
        _ordem_atraso=Case(When(atrasada, then=Value(0)), default=Value(1)),
        _prazo_atraso=Case(When(atrasada, then=F("prazo")), default=None, output_field=DateField()),
        _peso_prioridade=Case(
            When(prioridade=Prioridade.ALTA, then=Value(0)),
            When(prioridade=Prioridade.MEDIA, then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        ),
    ).order_by(
        "_ordem_atraso",
        F("_prazo_atraso").asc(nulls_last=True),
        "_peso_prioridade",
        F("prazo").asc(nulls_last=True),
        "recebida_em",
        "pk",
    )


def buscar(usuario, filtros: dict) -> QuerySet[Demanda]:
    """Aplica os filtros da lista (valores já validados pelo FiltroForm)."""
    hoje = relogio.hoje()
    demandas = demandas_de(usuario)

    situacao = filtros.get("status") or "abertas"
    if situacao == "abertas":
        demandas = demandas.filter(status__in=STATUS_ABERTOS)
    elif situacao in Status.values:
        demandas = demandas.filter(status=situacao)

    for campo in ("prioridade", "origem", "categoria"):
        if filtros.get(campo):
            demandas = demandas.filter(**{campo: filtros[campo]})

    if filtros.get("de"):
        demandas = demandas.filter(recebida_em__gte=relogio.inicio_do_dia(filtros["de"]))
    if filtros.get("ate"):
        _, fim = relogio.intervalo_dos_dias(filtros["ate"], filtros["ate"])
        demandas = demandas.filter(recebida_em__lt=fim)
    if filtros.get("atrasadas"):
        demandas = demandas.filter(q_atrasada(hoje))
    if filtros.get("sem_prazo"):
        demandas = demandas.filter(prazo__isnull=True)

    texto = (filtros.get("q") or "").strip()
    if texto:
        demandas = demandas.filter(
            Q(titulo__icontains=texto)
            | Q(descricao__icontains=texto)
            | Q(solicitante__icontains=texto)
        )
    return ordenar_por_urgencia(demandas, hoje)

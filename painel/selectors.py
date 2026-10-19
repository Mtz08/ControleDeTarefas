"""Consultas do painel do dia e do resumo do período."""

from dataclasses import dataclass, field
from datetime import date, timedelta

from django.db.models import Count, Q, QuerySet

from core import relogio
from demandas.models import Demanda, Origem, Prioridade, Status
from demandas.selectors import abertas_de, demandas_de, ordenar_por_urgencia, q_atrasada
from painel import indicadores
from painel.models import FocoDoDia

DIAS_PROXIMOS = 7
DIAS_PARA_COBRAR = 3


def top_de_hoje(usuario) -> QuerySet[FocoDoDia]:
    return (
        FocoDoDia.objects.filter(usuario=usuario, data=relogio.hoje())
        .select_related("demanda", "demanda__categoria")
        .order_by("ordem")
    )


def painel_do_dia(usuario) -> dict:
    """Blocos do painel, na ordem da tela."""
    hoje = relogio.hoje()
    abertas = abertas_de(usuario)
    inicio_hoje, fim_hoje = relogio.intervalo_dos_dias(hoje, hoje)

    return {
        "hoje": hoje,
        "top": top_de_hoje(usuario),
        "caixa": abertas.filter(status=Status.NOVA).order_by("recebida_em", "pk"),
        "atrasadas": ordenar_por_urgencia(abertas.filter(q_atrasada(hoje)), hoje),
        "vencem_hoje": ordenar_por_urgencia(abertas.filter(prazo=hoje), hoje),
        "proximos": ordenar_por_urgencia(
            abertas.filter(prazo__gt=hoje, prazo__lte=hoje + timedelta(days=DIAS_PROXIMOS)), hoje
        ),
        "aguardando": abertas.filter(status=Status.AGUARDANDO).order_by("status_alterado_em"),
        "dias_para_cobrar": DIAS_PARA_COBRAR,
        "sem_prazo": abertas.filter(prazo__isnull=True).count(),
        "concluidas_hoje": demandas_de(usuario)
        .filter(status=Status.CONCLUIDA, concluida_em__gte=inicio_hoje, concluida_em__lt=fim_hoje)
        .order_by("-concluida_em"),
        "total_abertas": abertas.count(),
    }


def candidatas_ao_top(usuario) -> QuerySet[Demanda]:
    """Abertas que ainda não estão no Top 3 de hoje, mais urgentes primeiro."""
    hoje = relogio.hoje()
    no_top = FocoDoDia.objects.filter(usuario=usuario, data=hoje).values("demanda_id")
    return ordenar_por_urgencia(abertas_de(usuario).exclude(pk__in=no_top), hoje)


def existe_top_anterior(usuario) -> bool:
    return FocoDoDia.objects.filter(usuario=usuario, data__lt=relogio.hoje()).exists()


# --- Resumo do período --------------------------------------------------------------


@dataclass
class Distribuicao:
    rotulo: str
    quantidade: int
    largura: int = 0


@dataclass
class Resumo:
    inicio: date
    fim: date
    recebidas: int
    concluidas: int
    no_prazo: indicadores.NoPrazo
    tempo: indicadores.TempoDeConclusao
    atrasadas_hoje: int
    por_origem: list[Distribuicao] = field(default_factory=list)
    por_categoria: list[Distribuicao] = field(default_factory=list)
    por_prioridade: list[Distribuicao] = field(default_factory=list)
    semanas: list[dict] = field(default_factory=list)


def recebidas_no_periodo(usuario, inicio: date, fim: date) -> QuerySet[Demanda]:
    de, ate = relogio.intervalo_dos_dias(inicio, fim)
    return demandas_de(usuario).filter(recebida_em__gte=de, recebida_em__lt=ate)


def concluidas_no_periodo(usuario, inicio: date, fim: date) -> QuerySet[Demanda]:
    de, ate = relogio.intervalo_dos_dias(inicio, fim)
    return demandas_de(usuario).filter(
        status=Status.CONCLUIDA, concluida_em__gte=de, concluida_em__lt=ate
    )


def movimentadas_no_periodo(usuario, inicio: date, fim: date) -> QuerySet[Demanda]:
    """Recebidas ou concluídas no período (base da exportação CSV do resumo)."""
    de, ate = relogio.intervalo_dos_dias(inicio, fim)
    return (
        demandas_de(usuario)
        .filter(
            Q(recebida_em__gte=de, recebida_em__lt=ate)
            | Q(status=Status.CONCLUIDA, concluida_em__gte=de, concluida_em__lt=ate)
        )
        .order_by("recebida_em", "pk")
    )


def _distribuicao(contagens: dict[str, int]) -> list[Distribuicao]:
    maximo = max(contagens.values(), default=0)
    itens = [
        Distribuicao(rotulo, qtd, indicadores.percentual(qtd, maximo))
        for rotulo, qtd in contagens.items()
        if qtd
    ]
    return sorted(itens, key=lambda d: -d.quantidade)


def _contar(demandas: QuerySet[Demanda], campo: str) -> dict:
    return dict(demandas.values_list(campo).annotate(n=Count("pk")).order_by())


def resumo_do_periodo(usuario, inicio: date, fim: date) -> Resumo:
    recebidas = recebidas_no_periodo(usuario, inicio, fim)
    concluidas = list(
        concluidas_no_periodo(usuario, inicio, fim).values_list(
            "recebida_em", "concluida_em", "prazo"
        )
    )
    conclusoes = [
        indicadores.Conclusao(relogio.data_local(r), relogio.data_local(c), p)
        for r, c, p in concluidas
    ]
    datas_recebidas = [
        relogio.data_local(r) for r in recebidas.values_list("recebida_em", flat=True)
    ]

    origens = _contar(recebidas, "origem")
    prioridades = _contar(recebidas, "prioridade")
    categorias = _contar(recebidas, "categoria__nome")

    semanas = indicadores.semanas(inicio, fim, datas_recebidas, [c.concluida for c in conclusoes])
    maximo = max((max(s.recebidas, s.concluidas) for s in semanas), default=0)

    return Resumo(
        inicio=inicio,
        fim=fim,
        recebidas=len(datas_recebidas),
        concluidas=len(conclusoes),
        no_prazo=indicadores.no_prazo(conclusoes),
        tempo=indicadores.tempo_de_conclusao(conclusoes),
        atrasadas_hoje=abertas_de(usuario).filter(q_atrasada(relogio.hoje())).count(),
        por_origem=_distribuicao({o.label: origens.get(o.value, 0) for o in Origem}),
        por_prioridade=_distribuicao({p.label: prioridades.get(p.value, 0) for p in Prioridade}),
        por_categoria=_distribuicao(
            {(nome or "Sem categoria"): qtd for nome, qtd in categorias.items()}
        ),
        semanas=[
            {
                "semana": s,
                "largura_recebidas": indicadores.percentual(s.recebidas, maximo),
                "largura_concluidas": indicadores.percentual(s.concluidas, maximo),
            }
            for s in semanas
        ],
    )

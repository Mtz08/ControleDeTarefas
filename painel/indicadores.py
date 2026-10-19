"""Cálculos puros do resumo do período (sem banco), fáceis de testar."""

import statistics
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Conclusao:
    """O mínimo de uma demanda concluída para os indicadores (datas já no fuso local)."""

    recebida: date
    concluida: date
    prazo: date | None


@dataclass(frozen=True)
class NoPrazo:
    com_prazo: int
    no_prazo: int
    sem_prazo: int

    @property
    def percentual(self) -> float | None:
        if not self.com_prazo:
            return None
        return round(100 * self.no_prazo / self.com_prazo, 1)


@dataclass(frozen=True)
class TempoDeConclusao:
    media: float | None
    mediana: float | None


@dataclass(frozen=True)
class Semana:
    inicio: date  # segunda-feira
    fim: date  # domingo
    recebidas: int = 0
    concluidas: int = 0


def no_prazo(conclusoes: list[Conclusao]) -> NoPrazo:
    """Entre as concluídas que tinham prazo, quantas terminaram até a data do prazo."""
    com_prazo = [c for c in conclusoes if c.prazo is not None]
    return NoPrazo(
        com_prazo=len(com_prazo),
        no_prazo=sum(1 for c in com_prazo if c.concluida <= c.prazo),
        sem_prazo=len(conclusoes) - len(com_prazo),
    )


def tempo_de_conclusao(conclusoes: list[Conclusao]) -> TempoDeConclusao:
    """Dias corridos entre a data de recebimento e a de conclusão (média e mediana)."""
    dias = [(c.concluida - c.recebida).days for c in conclusoes]
    if not dias:
        return TempoDeConclusao(media=None, mediana=None)
    return TempoDeConclusao(
        media=round(statistics.fmean(dias), 1),
        mediana=round(float(statistics.median(dias)), 1),
    )


def segunda_feira(dia: date) -> date:
    return dia - timedelta(days=dia.weekday())


def semanas(inicio: date, fim: date, recebidas: list[date], concluidas: list[date]) -> list[Semana]:
    """Recebidas × concluídas por semana (segunda a domingo) que toca o período."""
    contagem: dict[date, list[int]] = {}
    segunda = segunda_feira(inicio)
    while segunda <= fim:
        contagem[segunda] = [0, 0]
        segunda += timedelta(days=7)
    for dia in recebidas:
        contagem.setdefault(segunda_feira(dia), [0, 0])[0] += 1
    for dia in concluidas:
        contagem.setdefault(segunda_feira(dia), [0, 0])[1] += 1
    return [
        Semana(inicio=s, fim=s + timedelta(days=6), recebidas=r, concluidas=c)
        for s, (r, c) in sorted(contagem.items())
    ]


def percentual(parte: int, maximo: int) -> int:
    """Largura de barra (0–100) proporcional ao maior valor da tabela."""
    return round(100 * parte / maximo) if maximo else 0

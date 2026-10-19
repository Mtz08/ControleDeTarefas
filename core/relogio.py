"""Fonte única de "agora" e "hoje" do sistema.

Todo código que precisa da data ou hora atual chama estas funções, nunca
timezone.now() ou date.today() diretamente. Assim:

- "hoje" é sempre o dia em America/Sao_Paulo (TIME_ZONE), mesmo com o
  servidor em UTC;
- os testes podem fixar o relógio (ex.: 23h30) com `congelar`, sem bibliotecas extras.
"""

import calendar
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta

from django.utils import timezone

_momento_fixo: datetime | None = None


def agora() -> datetime:
    """Data e hora atuais, com fuso (aware)."""
    if _momento_fixo is not None:
        return _momento_fixo
    return timezone.now()


def hoje() -> date:
    """Data de hoje no fuso local do projeto."""
    return timezone.localdate(agora())


def inicio_do_dia(dia: date) -> datetime:
    """Meia-noite local do dia informado, com fuso."""
    return timezone.make_aware(datetime.combine(dia, time.min))


def intervalo_dos_dias(primeiro: date, ultimo: date) -> tuple[datetime, datetime]:
    """Intervalo [início do primeiro dia, início do dia seguinte ao último) para filtros."""
    return inicio_do_dia(primeiro), inicio_do_dia(ultimo + timedelta(days=1))


def data_local(momento: datetime) -> date:
    """Data, no fuso local, de um datetime com fuso."""
    return timezone.localdate(momento)


def subtrair_meses(dia: date, meses: int) -> date:
    """Mesmo dia, `meses` antes; se o dia não existir no mês (ex.: 31), usa o último."""
    ano, indice_mes = divmod(dia.year * 12 + (dia.month - 1) - meses, 12)
    mes = indice_mes + 1
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, min(dia.day, ultimo_dia))


@contextmanager
def congelar(momento: datetime):
    """Fixa o relógio em `momento` durante o bloco `with`. Uso exclusivo em testes."""
    if timezone.is_naive(momento):
        raise ValueError("Informe um datetime com fuso (aware).")
    global _momento_fixo
    anterior = _momento_fixo
    _momento_fixo = momento
    try:
        yield
    finally:
        _momento_fixo = anterior

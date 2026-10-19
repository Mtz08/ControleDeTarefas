from datetime import date

from django.conf import settings
from django.db.models import QuerySet

from core import relogio
from demandas.models import STATUS_FECHADOS, Demanda
from demandas.selectors import demandas_de


def limite_de_retencao() -> date:
    """Demandas fechadas antes desta data aparecem na tela de retenção."""
    return relogio.subtrair_meses(relogio.hoje(), settings.RETENCAO_MESES)


def retidas(usuario) -> QuerySet[Demanda]:
    """Concluídas e canceladas há mais de RETENCAO_MESES (candidatas à exclusão manual)."""
    return (
        demandas_de(usuario)
        .filter(
            status__in=STATUS_FECHADOS,
            status_alterado_em__lt=relogio.inicio_do_dia(limite_de_retencao()),
        )
        .order_by("status_alterado_em", "pk")
    )

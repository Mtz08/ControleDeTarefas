"""Filtros de exibição: "há N dias", atraso e descrição dos eventos do histórico."""

from datetime import date, datetime

from django import template
from django.utils.formats import date_format

from core import relogio
from demandas.models import STATUS_ABERTOS, Prioridade, Status, TipoEvento

register = template.Library()


def _como_data(valor) -> date | None:
    if isinstance(valor, datetime):
        return relogio.data_local(valor)
    return valor


@register.filter
def com_classe(campo):
    """Renderiza o campo com a classe CSS do Bootstrap adequada ao tipo de widget."""
    tipo = campo.widget_type
    if tipo == "checkbox":
        classe = "form-check-input"
    elif tipo in {"select", "selectmultiple"}:
        classe = "form-select"
    else:
        classe = "form-control"
    if campo.errors:
        classe += " is-invalid"
    return campo.as_widget(attrs={"class": classe})


@register.filter
def ativo_em(url: str, caminho: str) -> bool:
    """Item de menu ativo: a raiz só no próprio painel; os demais pelo prefixo."""
    return caminho == url if url == "/" else caminho.startswith(url)


@register.filter
def dias_desde(valor) -> int:
    dia = _como_data(valor)
    return (relogio.hoje() - dia).days if dia else 0


@register.filter
def ha_dias(valor) -> str:
    dia = _como_data(valor)
    if not dia:
        return ""
    dias = (relogio.hoje() - dia).days
    if dias == 0:
        return "hoje"
    if dias < 0:
        return "amanhã" if dias == -1 else f"em {-dias} dias"
    return "há 1 dia" if dias == 1 else f"há {dias} dias"


@register.filter
def atrasada(demanda) -> bool:
    return bool(
        demanda.prazo and demanda.status in STATUS_ABERTOS and demanda.prazo < relogio.hoje()
    )


@register.filter
def vence_hoje(demanda) -> bool:
    return bool(
        demanda.prazo and demanda.status in STATUS_ABERTOS and demanda.prazo == relogio.hoje()
    )


def _rotulo(opcoes, valor: str) -> str:
    try:
        return opcoes(valor).label
    except ValueError:
        return valor or "—"


def _data_iso(valor: str) -> str:
    return date_format(date.fromisoformat(valor), "d/m/Y") if valor else "sem prazo"


@register.filter
def descrever_evento(evento) -> str:
    anterior, novo = evento.valor_anterior, evento.valor_novo
    if evento.tipo == TipoEvento.CRIADA:
        return f"Criada como “{_rotulo(Status, novo)}”."
    if evento.tipo == TipoEvento.STATUS:
        return f"Status: {_rotulo(Status, anterior)} → {_rotulo(Status, novo)}."
    if evento.tipo == TipoEvento.PRIORIDADE:
        return f"Prioridade: {_rotulo(Prioridade, anterior)} → {_rotulo(Prioridade, novo)}."
    if evento.tipo == TipoEvento.PRAZO:
        return f"Prazo: {_data_iso(anterior)} → {_data_iso(novo)}."
    return ""

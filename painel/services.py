"""Regras do Top 3 do dia.

O limite de 3 itens não é verificado "contando antes de inserir": tentamos
gravar em cada posição livre e o banco (UNIQUE + CHECK) recusa o que não cabe.
Assim nem duas abas ao mesmo tempo conseguem criar um 4º item.
"""

from django.db import IntegrityError, transaction

from core import relogio
from demandas.models import STATUS_ABERTOS, Demanda
from painel.models import LIMITE_TOP, FocoDoDia


class ErroDoTop(Exception):
    """Erro com mensagem pronta para mostrar ao usuário."""


def _inserir_na_primeira_posicao_livre(usuario, dia, demanda: Demanda) -> FocoDoDia | None:
    for ordem in range(1, LIMITE_TOP + 1):
        try:
            with transaction.atomic():  # savepoint: uma recusa não derruba a transação externa
                return FocoDoDia.objects.create(
                    usuario=usuario, data=dia, ordem=ordem, demanda=demanda
                )
        except IntegrityError:
            continue
    return None


@transaction.atomic
def adicionar_ao_top(usuario, demanda: Demanda) -> FocoDoDia:
    hoje = relogio.hoje()
    if demanda.usuario_id != usuario.pk:
        raise ErroDoTop("Demanda inválida.")
    if demanda.status not in STATUS_ABERTOS:
        raise ErroDoTop("Só demandas abertas podem entrar no Top 3.")
    if FocoDoDia.objects.filter(usuario=usuario, data=hoje, demanda=demanda).exists():
        raise ErroDoTop("Esta demanda já está no Top 3 de hoje.")
    foco = _inserir_na_primeira_posicao_livre(usuario, hoje, demanda)
    if foco is None:
        raise ErroDoTop("O Top 3 de hoje já está completo. Remova um item antes.")
    return foco


@transaction.atomic
def remover_do_top(usuario, foco_id: int) -> None:
    FocoDoDia.objects.filter(usuario=usuario, pk=foco_id, data=relogio.hoje()).delete()


@transaction.atomic
def trazer_pendentes(usuario) -> int:
    """Copia para hoje, na mesma ordem, os itens ainda abertos do último Top 3 anterior.

    Só ocupa posições livres: não sobrescreve escolhas já feitas hoje.
    Retorna quantos itens foram trazidos.
    """
    hoje = relogio.hoje()
    ultimo_dia = (
        FocoDoDia.objects.filter(usuario=usuario, data__lt=hoje)
        .order_by("-data")
        .values_list("data", flat=True)
        .first()
    )
    if ultimo_dia is None:
        return 0

    ja_hoje = FocoDoDia.objects.filter(usuario=usuario, data=hoje).values("demanda_id")
    pendentes = (
        FocoDoDia.objects.filter(
            usuario=usuario, data=ultimo_dia, demanda__status__in=STATUS_ABERTOS
        )
        .exclude(demanda_id__in=ja_hoje)
        .select_related("demanda")
        .order_by("ordem")
    )
    trazidos = 0
    for foco in pendentes:
        if _inserir_na_primeira_posicao_livre(usuario, hoje, foco.demanda) is None:
            break
        trazidos += 1
    return trazidos

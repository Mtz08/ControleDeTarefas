"""Privacidade e dados do usuário: backup, exclusão total, retenção e limpeza de sessões."""

from itertools import chain

from django.contrib.sessions.backends.db import SessionStore
from django.core import serializers
from django.db import transaction

from contas.selectors import retidas
from demandas.models import Categoria, Demanda, EventoDemanda
from painel.models import FocoDoDia


def limpar_sessoes_expiradas() -> None:
    """Apaga sessões vencidas. Roda a cada login, já que o plano Free não tem tarefas agendadas.

    Usa a rotina do próprio Django (a mesma do comando clearsessions), que compara
    com o mesmo relógio usado para calcular a validade da sessão.
    """
    SessionStore.clear_expired()


def backup_json(usuario) -> str:
    """Backup completo no formato do `python manage.py loaddata`.

    Contém o usuário (com o hash da senha) e todos os dados de trabalho:
    deve ser guardado em local seguro.
    """
    objetos = chain(
        [usuario],
        Categoria.objects.filter(usuario=usuario).order_by("pk"),
        Demanda.objects.filter(usuario=usuario).order_by("pk"),
        EventoDemanda.objects.filter(demanda__usuario=usuario).order_by("pk"),
        FocoDoDia.objects.filter(usuario=usuario).order_by("pk"),
    )
    return serializers.serialize("json", objetos, indent=2, use_natural_foreign_keys=True)


@transaction.atomic
def apagar_todos_os_dados(usuario) -> int:
    """Apaga demandas (com histórico e Top 3) e categorias. O usuário é mantido."""
    FocoDoDia.objects.filter(usuario=usuario).delete()
    _, por_modelo = Demanda.objects.filter(usuario=usuario).delete()
    Categoria.objects.filter(usuario=usuario).delete()
    return por_modelo.get(Demanda._meta.label, 0)


@transaction.atomic
def excluir_retidas(usuario, ids: list[int]) -> int:
    """Exclui, entre as demandas em retenção, apenas as escolhidas na tela."""
    _, por_modelo = retidas(usuario).filter(pk__in=ids).delete()
    return por_modelo.get(Demanda._meta.label, 0)

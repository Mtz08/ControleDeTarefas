from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from contas.services import limpar_sessoes_expiradas


@receiver(user_logged_in)
def ao_entrar(sender, request, user, **kwargs):
    limpar_sessoes_expiradas()

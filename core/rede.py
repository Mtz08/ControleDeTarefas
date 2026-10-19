"""Descoberta do IP real do cliente atrás de proxies (usada pelo django-axes)."""

import ipaddress

from django.conf import settings


def ip_do_cliente(request) -> str | None:
    """IP do cliente, sem confiar cegamente no X-Forwarded-For.

    Cada proxy confiável acrescenta, à direita do cabeçalho, o endereço de quem
    se conectou a ele. Os valores à esquerda podem ter sido escritos pelo próprio
    cliente (forjados). Por isso lemos a N-ésima posição a partir da direita,
    onde N = PROXIES_CONFIAVEIS: esse valor foi gravado pelo nosso proxy.
    """
    remoto = request.META.get("REMOTE_ADDR")
    proxies = settings.PROXIES_CONFIAVEIS
    if proxies <= 0:
        return remoto

    cadeia = [ip.strip() for ip in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")]
    cadeia = [ip for ip in cadeia if ip]
    if len(cadeia) < proxies:
        return remoto

    candidato = cadeia[-proxies]
    try:
        return str(ipaddress.ip_address(candidato))
    except ValueError:
        return remoto

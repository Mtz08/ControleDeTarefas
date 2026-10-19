import logging
import sys

from django.contrib.auth.decorators import login_not_required
from django.db import OperationalError
from django.http import HttpResponse, HttpResponseServerError
from django.template import loader
from django.views.decorators.http import require_GET

log = logging.getLogger(__name__)


@login_not_required
@require_GET
def robots(request):
    return HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")


def erro_500(request):
    """Página de erro própria, sem stack trace.

    Se a causa foi o banco indisponível (ex.: Neon acordando), mostra uma
    mensagem de "tente novamente" com status 503. Os templates não usam o
    contexto da requisição para não tocar no banco de novo.
    """
    erro = sys.exception()
    if isinstance(erro, OperationalError):
        log.warning("Banco indisponível ao atender a requisição.")
        html = loader.get_template("erros/banco_indisponivel.html").render()
        resposta = HttpResponse(html, status=503)
        resposta["Retry-After"] = "10"
        return resposta
    return HttpResponseServerError(loader.get_template("500.html").render())

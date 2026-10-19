from django.conf import settings
from django.http import HttpResponse

CAMINHO_SAUDE = "/saude"

# Sem scripts nem estilos inline: só arquivos servidos pelo próprio site.
# img-src aceita data: porque o Bootstrap desenha alguns ícones como SVG embutido.
_CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "object-src 'none'",
    ]
)
# O admin do Django 5.2 ainda usa alguns estilos inline; só ele recebe essa exceção.
_CSP_ADMIN = _CSP.replace("style-src 'self'", "style-src 'self' 'unsafe-inline'")


class SaudeMiddleware:
    """Responde à rota /saude antes de qualquer outro middleware.

    Fica no topo da pilha para não passar pelo redirecionamento HTTPS nem pela
    validação de Host, e não consulta o banco para não acordar o Neon à toa.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info == CAMINHO_SAUDE:
            resposta = HttpResponse("ok", content_type="text/plain; charset=utf-8")
            resposta["Cache-Control"] = "no-store"
            return resposta
        return self.get_response(request)


class CabecalhosSegurancaMiddleware:
    """Acrescenta CSP e outros cabeçalhos que o Django 5.2 não define sozinho."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.prefixo_admin = "/" + settings.ADMIN_URL

    def __call__(self, request):
        resposta = self.get_response(request)
        no_admin = request.path_info.startswith(self.prefixo_admin)
        resposta.setdefault("Content-Security-Policy", _CSP_ADMIN if no_admin else _CSP)
        resposta.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        resposta.setdefault("X-Robots-Tag", "noindex, nofollow")
        return resposta

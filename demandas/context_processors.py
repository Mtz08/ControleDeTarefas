from demandas.models import Origem


def captura(request):
    """Opções do campo de captura rápida, presente em todas as telas (sem consultar o banco)."""
    return {"captura_origens": Origem.choices}

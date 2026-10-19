"""Transições de status permitidas, definidas em um único lugar.

- Entre abertas: qualquer mudança, exceto voltar para Nova.
- De aberta para fechada: permitido.
- De fechada: apenas reabrir para A fazer.
"""

from demandas.models import STATUS_FECHADOS, Status


def transicao_permitida(atual: str, novo: str) -> bool:
    if atual == novo or novo == Status.NOVA:
        return False
    if atual in STATUS_FECHADOS:
        return novo == Status.A_FAZER
    return True


def destinos_permitidos(atual: str) -> list[Status]:
    """Status para os quais a demanda pode ir, na ordem de exibição."""
    return [status for status in Status if transicao_permitida(atual, status)]

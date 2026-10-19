"""Detecção de CPF em texto livre, para avisar (sem bloquear) sobre dado pessoal."""

import re

# 11 dígitos, com ou sem a pontuação 000.000.000-00, sem dígitos colados antes ou depois.
_PADRAO_CPF = re.compile(r"(?<!\d)(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})(?!\d)")


def _digito_verificador(digitos: str) -> int:
    peso_inicial = len(digitos) + 1
    soma = sum(int(d) * peso for d, peso in zip(digitos, range(peso_inicial, 1, -1), strict=True))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def cpf_valido(digitos: str) -> bool:
    """True se os 11 dígitos formam um CPF com dígitos verificadores corretos."""
    if len(digitos) != 11 or not digitos.isdigit() or len(set(digitos)) == 1:
        return False
    primeiro = _digito_verificador(digitos[:9])
    segundo = _digito_verificador(digitos[:9] + str(primeiro))
    return digitos[9:] == f"{primeiro}{segundo}"


def contem_cpf(*textos: str) -> bool:
    """True se algum dos textos parece conter um CPF válido."""
    for texto in textos:
        for encontrado in _PADRAO_CPF.finditer(texto or ""):
            if cpf_valido("".join(encontrado.groups())):
                return True
    return False

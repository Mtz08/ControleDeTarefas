"""Utilitários compartilhados pelos testes (dados sempre fictícios)."""

from datetime import UTC, datetime

from django.contrib.auth import get_user_model

SENHA_FICTICIA = "senha-ficticia-123"

# 19/10/2026 às 10h em São Paulo (13h UTC): um "agora" fixo e previsível.
AGORA_PADRAO = datetime(2026, 10, 19, 13, 0, tzinfo=UTC)


def criar_usuario(nome: str = "teste"):
    return get_user_model().objects.create_user(nome, password=SENHA_FICTICIA)

"""Exportação de demandas em CSV para Excel (separador ";" e UTF-8 com BOM)."""

import csv
from collections.abc import Iterable

from django.http import HttpResponse
from django.utils import timezone

from demandas.models import Demanda

COLUNAS = [
    ("ID", lambda d: d.pk),
    ("Título", lambda d: d.titulo),
    ("Descrição", lambda d: d.descricao),
    ("Solicitante", lambda d: d.solicitante),
    ("Referência", lambda d: d.referencia),
    ("Origem", lambda d: d.get_origem_display()),
    ("Categoria", lambda d: d.categoria.nome if d.categoria else ""),
    ("Prioridade", lambda d: d.get_prioridade_display()),
    ("Status", lambda d: d.get_status_display()),
    ("Aguardando", lambda d: d.aguardando_quem),
    ("Prazo", lambda d: _data(d.prazo)),
    ("Recebida em", lambda d: _data_hora(d.recebida_em)),
    ("Concluída em", lambda d: _data_hora(d.concluida_em)),
    ("Status alterado em", lambda d: _data_hora(d.status_alterado_em)),
]

# Textos que o Excel interpretaria como fórmula (risco de "CSV injection").
_INICIO_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def _data(valor) -> str:
    return valor.strftime("%d/%m/%Y") if valor else ""


def _data_hora(valor) -> str:
    return timezone.localtime(valor).strftime("%d/%m/%Y %H:%M") if valor else ""


def _celula(valor) -> str:
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto.startswith(_INICIO_DE_FORMULA) else texto


def resposta_csv(demandas: Iterable[Demanda], nome_arquivo: str) -> HttpResponse:
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'
    resposta.write("﻿")  # BOM: faz o Excel reconhecer os acentos
    escritor = csv.writer(resposta, delimiter=";")
    escritor.writerow([titulo for titulo, _ in COLUNAS])
    for demanda in demandas:
        escritor.writerow([_celula(extrair(demanda)) for _, extrair in COLUNAS])
    return resposta

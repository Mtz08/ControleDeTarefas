import logging

from django.db import DatabaseError


class SemDadosDoBancoFilter(logging.Filter):
    """Remove o detalhe de erros de banco dos logs.

    Mensagens do PostgreSQL podem trazer a linha que falhou (ex.: "Failing row
    contains ..."), ou seja, o conteúdo da demanda. No log fica só o tipo do erro.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info and isinstance(record.exc_info[1], DatabaseError):
            tipo = type(record.exc_info[1]).__name__
            record.msg = f"{record.getMessage()} [{tipo}, detalhes omitidos]"
            record.args = None
            record.exc_info = None
            record.exc_text = None
        return True

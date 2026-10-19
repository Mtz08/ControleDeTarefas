from django.apps import AppConfig


class ContasConfig(AppConfig):
    name = "contas"
    verbose_name = "Contas"

    def ready(self):
        from contas import signals  # noqa: F401  (registra os receptores de sinais)

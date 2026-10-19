"""Rotas raiz do projeto.

A rota /saude não aparece aqui: ela é respondida por core.middleware.SaudeMiddleware,
antes de qualquer outra camada.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from core import views as core_views

admin.site.site_header = "Radar de Demandas: administração"
admin.site.site_title = "Radar de Demandas"

urlpatterns = [
    path("", include("painel.urls")),
    path("demandas/", include("demandas.urls")),
    path("conta/", include("contas.urls")),
    path("robots.txt", core_views.robots, name="robots"),
    path(settings.ADMIN_URL, admin.site.urls),
]

handler500 = "core.views.erro_500"

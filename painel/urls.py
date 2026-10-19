from django.urls import path

from painel import views

app_name = "painel"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("top/adicionar/", views.adicionar_ao_top, name="top_adicionar"),
    path("top/<int:pk>/remover/", views.remover_do_top, name="top_remover"),
    path("top/trazer-pendentes/", views.trazer_pendentes, name="top_trazer"),
    path("resumo/", views.resumo, name="resumo"),
    path("resumo/csv/", views.resumo_csv, name="resumo_csv"),
]

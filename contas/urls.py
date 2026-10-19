from django.contrib.auth import views as auth_views
from django.urls import path

from contas import views

app_name = "contas"

urlpatterns = [
    path("entrar/", views.EntrarView.as_view(), name="entrar"),
    path("sair/", auth_views.LogoutView.as_view(), name="sair"),
    path("senha/", views.TrocarSenhaView.as_view(), name="senha"),
    path("privacidade/", views.privacidade, name="privacidade"),
    path("dados/", views.meus_dados, name="meus_dados"),
    path("dados/exportar.csv", views.exportar_csv, name="exportar_csv"),
    path("dados/backup/", views.backup_json, name="backup_json"),
    path("dados/apagar-tudo/", views.apagar_tudo, name="apagar_tudo"),
    path("dados/retencao/", views.retencao, name="retencao"),
    path("dados/retencao.csv", views.retencao_csv, name="retencao_csv"),
    path("dados/retencao/excluir/", views.retencao_excluir, name="retencao_excluir"),
]

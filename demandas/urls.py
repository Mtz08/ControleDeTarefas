from django.urls import path

from demandas import views

app_name = "demandas"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nova/", views.nova, name="nova"),
    path("capturar/", views.capturar, name="capturar"),
    path("<int:pk>/", views.detalhe, name="detalhe"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/aguardar/", views.aguardar, name="aguardar"),
    path("<int:pk>/anotar/", views.anotar, name="anotar"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
    path("<int:pk>/<slug:nome>/", views.acao, name="acao"),
]

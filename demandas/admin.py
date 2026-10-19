"""Admin usado só para cadastros auxiliares (categorias)."""

from django.contrib import admin

from demandas.models import Categoria


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ["nome", "ativa"]
    list_filter = ["ativa"]
    search_fields = ["nome"]
    exclude = ["usuario"]

    def get_queryset(self, request):
        # Cada usuário só enxerga as próprias categorias (evita IDOR).
        return super().get_queryset(request).filter(usuario=request.user)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)

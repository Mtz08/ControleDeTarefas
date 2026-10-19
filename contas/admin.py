from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from contas.models import Usuario

admin.site.register(Usuario, UserAdmin)

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from contas import selectors, services
from contas.forms import ApagarTudoForm
from core import relogio
from demandas.exportacao import resposta_csv
from demandas.selectors import demandas_de


class EntrarView(auth_views.LoginView):
    template_name = "contas/entrar.html"
    redirect_authenticated_user = True


class TrocarSenhaView(auth_views.PasswordChangeView):
    template_name = "contas/senha.html"
    success_url = reverse_lazy("painel:inicio")

    def form_valid(self, form):
        resposta = super().form_valid(form)
        messages.success(self.request, "Senha alterada.")
        return resposta


def privacidade(request):
    return render(request, "contas/privacidade.html", {"retencao_meses": settings.RETENCAO_MESES})


def meus_dados(request):
    contexto = {
        "total_demandas": demandas_de(request.user).count(),
        "total_retidas": selectors.retidas(request.user).count(),
    }
    return render(request, "contas/meus_dados.html", contexto)


def exportar_csv(request):
    demandas = demandas_de(request.user).order_by("recebida_em", "pk")
    return resposta_csv(demandas, f"radar-demandas-{relogio.hoje():%Y%m%d}.csv")


@require_POST
def backup_json(request):
    # POST: o download não acontece por um simples link aberto por engano.
    resposta = HttpResponse(services.backup_json(request.user), content_type="application/json")
    nome = f"radar-backup-{relogio.hoje():%Y%m%d}.json"
    resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    return resposta


def apagar_tudo(request):
    form = ApagarTudoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        apagadas = services.apagar_todos_os_dados(request.user)
        messages.success(
            request, f"Dados apagados ({apagadas} demanda(s)). Seu usuário foi mantido."
        )
        return redirect("painel:inicio")
    return render(request, "contas/apagar_tudo.html", {"form": form})


def retencao(request):
    contexto = {
        "demandas": selectors.retidas(request.user),
        "limite": selectors.limite_de_retencao(),
    }
    return render(request, "contas/retencao.html", contexto)


def retencao_csv(request):
    return resposta_csv(
        selectors.retidas(request.user), f"radar-retencao-{relogio.hoje():%Y%m%d}.csv"
    )


@require_POST
def retencao_excluir(request):
    ids = [int(valor) for valor in request.POST.getlist("demanda") if valor.isdigit()]
    if not ids:
        messages.warning(request, "Selecione ao menos uma demanda para excluir.")
        return redirect("contas:retencao")
    excluidas = services.excluir_retidas(request.user, ids)
    messages.success(request, f"{excluidas} demanda(s) excluída(s).")
    return redirect("contas:retencao")

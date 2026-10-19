from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from demandas.exportacao import resposta_csv
from demandas.selectors import demandas_de
from painel import selectors, services
from painel.forms import PeriodoForm

LIMITE_CANDIDATAS = 50


def inicio(request):
    contexto = selectors.painel_do_dia(request.user)
    contexto["candidatas"] = selectors.candidatas_ao_top(request.user)[:LIMITE_CANDIDATAS]
    contexto["existe_top_anterior"] = selectors.existe_top_anterior(request.user)
    return render(request, "painel/inicio.html", contexto)


@require_POST
def adicionar_ao_top(request):
    demanda_id = request.POST.get("demanda", "")
    if not demanda_id.isdigit():
        messages.warning(request, "Escolha uma demanda para o Top 3.")
        return redirect("painel:inicio")
    demanda = get_object_or_404(demandas_de(request.user), pk=int(demanda_id))
    try:
        services.adicionar_ao_top(request.user, demanda)
    except services.ErroDoTop as erro:
        messages.warning(request, str(erro))
    return redirect("painel:inicio")


@require_POST
def remover_do_top(request, pk):
    services.remover_do_top(request.user, pk)
    return redirect("painel:inicio")


@require_POST
def trazer_pendentes(request):
    trazidos = services.trazer_pendentes(request.user)
    if trazidos:
        messages.success(request, f"{trazidos} pendente(s) trazida(s) para o Top 3 de hoje.")
    else:
        messages.info(request, "Nada a trazer: não há pendentes abertas ou o Top 3 já está cheio.")
    return redirect("painel:inicio")


def resumo(request):
    form = PeriodoForm(request.GET or None)
    inicio_periodo, fim_periodo = form.periodo()
    contexto = {
        "form": form,
        "resumo": selectors.resumo_do_periodo(request.user, inicio_periodo, fim_periodo),
        "querystring": request.GET.urlencode(),
    }
    return render(request, "painel/resumo.html", contexto)


def resumo_csv(request):
    inicio_periodo, fim_periodo = PeriodoForm(request.GET or None).periodo()
    demandas = selectors.movimentadas_no_periodo(request.user, inicio_periodo, fim_periodo)
    nome = f"radar-resumo-{inicio_periodo:%Y%m%d}-{fim_periodo:%Y%m%d}.csv"
    return resposta_csv(demandas, nome)

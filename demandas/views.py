"""Views finas: validam a entrada, chamam o serviço e escolhem a resposta."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from demandas import selectors, services
from demandas.cpf import contem_cpf
from demandas.forms import (
    AVISO_DADOS_PESSOAIS,
    AguardarForm,
    CapturaForm,
    DemandaForm,
    FiltroForm,
    NotaForm,
)
from demandas.models import Status
from demandas.transicoes import destinos_permitidos

AVISO_CPF = (
    "Atenção: parece haver um CPF no texto. Evite registrar dados pessoais; "
    "edite a demanda e troque por nome da empresa ou código interno."
)

# Ações rápidas → status de destino.
ACOES = {
    "triar": Status.A_FAZER,
    "iniciar": Status.EM_ANDAMENTO,
    "concluir": Status.CONCLUIDA,
    "cancelar": Status.CANCELADA,
    "reabrir": Status.A_FAZER,
}


def _destino_seguro(request, url: str | None, padrao: str) -> str:
    """Só redireciona para endereços do próprio site (evita open redirect)."""
    if url and url_has_allowed_host_and_scheme(
        url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return url
    return padrao


def _avisar_cpf(request, *textos: str) -> None:
    if contem_cpf(*textos):
        messages.warning(request, AVISO_CPF)


def _versao_enviada(request) -> int | None:
    try:
        return int(request.POST["versao"])
    except (KeyError, ValueError):
        return None


def _demanda_do_usuario(request, pk: int):
    return get_object_or_404(selectors.demandas_de(request.user), pk=pk)


@require_POST
def capturar(request):
    destino = _destino_seguro(request, request.POST.get("proximo"), reverse("painel:inicio"))
    form = CapturaForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Informe um título de até 200 caracteres.")
        return redirect(destino)
    demanda = services.criar_demanda(
        request.user, titulo=form.cleaned_data["titulo"], origem=form.cleaned_data["origem"]
    )
    messages.success(request, f"“{demanda.titulo}” foi para a caixa de entrada.")
    _avisar_cpf(request, demanda.titulo)
    return redirect(destino)


def lista(request):
    form = FiltroForm(request.GET or None, usuario=request.user)
    filtros = form.cleaned_data if form.is_valid() else {}
    demandas = selectors.buscar(request.user, filtros)
    pagina = Paginator(demandas, selectors.ITENS_POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(request, "demandas/lista.html", {"form": form, "pagina": pagina})


def detalhe(request, pk):
    demanda = _demanda_do_usuario(request, pk)
    contexto = {
        "demanda": demanda,
        "eventos": demanda.eventos.all(),
        "nota_form": NotaForm(),
        "destinos": [d.value for d in destinos_permitidos(demanda.status)],
    }
    return render(request, "demandas/detalhe.html", contexto)


def nova(request):
    form = DemandaForm(request.POST or None, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            demanda = services.criar_demanda(
                request.user,
                status=form.cleaned_data["status"],
                aguardando_quem=form.cleaned_data["aguardando_quem"],
                **form.dados_editaveis(),
            )
        except services.ErroDeNegocio as erro:
            form.add_error(None, str(erro))
        else:
            messages.success(request, "Demanda cadastrada.")
            _avisar_cpf(request, *_textos(demanda))
            return redirect("demandas:detalhe", pk=demanda.pk)
    contexto = {"form": form, "aviso": AVISO_DADOS_PESSOAIS}
    return render(request, "demandas/form.html", contexto)


def editar(request, pk):
    demanda = _demanda_do_usuario(request, pk)
    form = DemandaForm(request.POST or None, instance=demanda, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            demanda = services.editar_demanda(
                demanda,
                versao=form.cleaned_data["versao"],
                dados=form.dados_editaveis(),
                status=form.cleaned_data["status"],
                aguardando_quem=form.cleaned_data["aguardando_quem"],
            )
        except services.ConflitoDeEdicao as erro:
            messages.warning(request, str(erro))
            return redirect("demandas:editar", pk=pk)
        except services.ErroDeNegocio as erro:
            form.add_error(None, str(erro))
        else:
            messages.success(request, "Alterações salvas.")
            _avisar_cpf(request, *_textos(demanda))
            return redirect("demandas:detalhe", pk=pk)
    contexto = {"form": form, "demanda": demanda, "aviso": AVISO_DADOS_PESSOAIS}
    return render(request, "demandas/form.html", contexto)


@require_POST
def acao(request, pk, nome):
    demanda = _demanda_do_usuario(request, pk)
    destino = _destino_seguro(
        request, request.POST.get("proximo"), reverse("demandas:detalhe", args=[pk])
    )
    novo = ACOES.get(nome)
    if novo is None:
        messages.error(request, "Ação desconhecida.")
        return redirect(destino)
    try:
        services.mudar_status(demanda, novo, versao=_versao_enviada(request))
    except services.ErroDeNegocio as erro:
        messages.warning(request, str(erro))
    else:
        messages.success(request, f"Status alterado para “{novo.label}”.")
    return redirect(destino)


def aguardar(request, pk):
    demanda = _demanda_do_usuario(request, pk)
    form = AguardarForm(request.POST or None, initial={"versao": demanda.versao})
    if request.method == "POST" and form.is_valid():
        try:
            services.mudar_status(
                demanda,
                Status.AGUARDANDO,
                versao=form.cleaned_data["versao"],
                aguardando_quem=form.cleaned_data["aguardando_quem"],
            )
        except services.ErroDeNegocio as erro:
            messages.warning(request, str(erro))
        else:
            messages.success(request, "Demanda marcada como aguardando terceiro.")
            _avisar_cpf(request, form.cleaned_data["aguardando_quem"])
        return redirect("demandas:detalhe", pk=pk)
    return render(request, "demandas/aguardar.html", {"demanda": demanda, "form": form})


@require_POST
def anotar(request, pk):
    demanda = _demanda_do_usuario(request, pk)
    form = NotaForm(request.POST)
    if form.is_valid():
        services.anotar(demanda, form.cleaned_data["texto"])
        messages.success(request, "Anotação registrada.")
        _avisar_cpf(request, form.cleaned_data["texto"])
    else:
        messages.error(request, "Escreva a anotação antes de salvar.")
    return redirect("demandas:detalhe", pk=pk)


def excluir(request, pk):
    demanda = _demanda_do_usuario(request, pk)
    if request.method == "POST":
        services.excluir_demanda(demanda)
        messages.success(request, f"“{demanda.titulo}” foi excluída.")
        return redirect("demandas:lista")
    return render(request, "demandas/excluir.html", {"demanda": demanda})


def _textos(demanda) -> tuple[str, ...]:
    return (
        demanda.titulo,
        demanda.descricao,
        demanda.solicitante,
        demanda.referencia,
        demanda.aguardando_quem,
    )

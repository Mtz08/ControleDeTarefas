from datetime import timedelta

from django import forms
from django.utils import timezone

from core import relogio
from demandas.models import STATUS_ABERTOS, Demanda, Origem, Prioridade, Status
from demandas.selectors import categorias_de
from demandas.transicoes import destinos_permitidos

AVISO_DADOS_PESSOAIS = (
    "Identifique clientes pelo nome da empresa ou código interno. "
    "Não registre CPF, RG, dados bancários, salários ou dados de saúde."
)

# Tolerância para relógios levemente adiantados ao informar "recebida em".
_TOLERANCIA_FUTURO = timedelta(minutes=5)


class CapturaForm(forms.Form):
    titulo = forms.CharField(max_length=200)
    origem = forms.ChoiceField(choices=Origem.choices, initial=Origem.OUTRO, required=False)

    def clean_titulo(self):
        titulo = self.cleaned_data["titulo"].strip()
        if not titulo:
            raise forms.ValidationError("Informe um título.")
        return titulo

    def clean_origem(self):
        return self.cleaned_data.get("origem") or Origem.OUTRO


class DemandaForm(forms.ModelForm):
    """Cadastro, edição e triagem (a triagem é a edição de uma demanda Nova)."""

    status = forms.ChoiceField(label="Status")
    versao = forms.IntegerField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = Demanda
        fields = [
            "titulo",
            "descricao",
            "solicitante",
            "referencia",
            "origem",
            "categoria",
            "prioridade",
            "prazo",
            "recebida_em",
            "aguardando_quem",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "prazo": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "recebida_em": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }
        help_texts = {
            "referencia": "Cliente, sistema ou processo, por nome ou código interno. Nunca CPF.",
            "solicitante": "Nome ou área de quem pediu.",
            "aguardando_quem": "Obrigatório quando o status for “Aguardando terceiro”.",
        }

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["titulo"].widget.attrs["autofocus"] = True
        categorias = categorias_de(usuario, so_ativas=True)
        if self.instance.categoria_id:
            categorias = categorias | categorias_de(usuario).filter(pk=self.instance.categoria_id)
        self.fields["categoria"].queryset = categorias.distinct()
        self.fields["recebida_em"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["status"].choices = self._opcoes_de_status()
        self.fields["status"].initial = self.instance.status if self.instance.pk else Status.NOVA
        if self.instance.pk:
            self.fields["versao"].initial = self.instance.versao
            self.initial["recebida_em"] = self._ao_minuto(self.instance.recebida_em)
        else:
            self.initial.setdefault("recebida_em", self._ao_minuto(relogio.agora()))
            self.initial.setdefault("prioridade", Prioridade.MEDIA)

    @staticmethod
    def _ao_minuto(momento):
        return timezone.localtime(momento).replace(second=0, microsecond=0)

    def _opcoes_de_status(self):
        if not self.instance.pk:
            permitidos = [s for s in Status if s in STATUS_ABERTOS]
        else:
            atual = Status(self.instance.status)
            permitidos = [atual, *destinos_permitidos(atual)]
        return [(s.value, s.label) for s in permitidos]

    def clean_titulo(self):
        titulo = self.cleaned_data["titulo"].strip()
        if not titulo:
            raise forms.ValidationError("Informe um título.")
        return titulo

    def clean_recebida_em(self):
        recebida_em = self.cleaned_data["recebida_em"]
        if recebida_em > relogio.agora() + _TOLERANCIA_FUTURO:
            raise forms.ValidationError("A data de recebimento não pode estar no futuro.")
        # Sem mudança real (a tela só mostra até os minutos): mantém o valor exato.
        if self.instance.pk and recebida_em == self._ao_minuto(self.instance.recebida_em):
            return self.instance.recebida_em
        return recebida_em

    def clean(self):
        dados = super().clean()
        if (
            dados.get("status") == Status.AGUARDANDO
            and not (dados.get("aguardando_quem") or "").strip()
        ):
            self.add_error(
                "aguardando_quem", "Informe de quem ou do quê a demanda está aguardando."
            )
        return dados

    def dados_editaveis(self) -> dict:
        """Campos do modelo, sem status e aguardando_quem (tratados pelo serviço)."""
        return {
            campo: self.cleaned_data[campo]
            for campo in self.Meta.fields
            if campo != "aguardando_quem"
        }


class AguardarForm(forms.Form):
    aguardando_quem = forms.CharField(
        label="Aguardando de quem ou do quê?",
        max_length=120,
        widget=forms.TextInput(attrs={"autofocus": True}),
    )
    versao = forms.IntegerField(widget=forms.HiddenInput, required=False)


class NotaForm(forms.Form):
    texto = forms.CharField(label="Nova anotação", widget=forms.Textarea(attrs={"rows": 2}))


class FiltroForm(forms.Form):
    SITUACOES = [("abertas", "Abertas"), ("todas", "Todas"), *Status.choices]

    q = forms.CharField(label="Buscar", required=False)
    status = forms.ChoiceField(choices=SITUACOES, required=False)
    prioridade = forms.ChoiceField(choices=[("", "Todas"), *Prioridade.choices], required=False)
    origem = forms.ChoiceField(choices=[("", "Todas"), *Origem.choices], required=False)
    categoria = forms.ModelChoiceField(queryset=None, required=False, empty_label="Todas")
    de = forms.DateField(
        label="Recebidas de", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    ate = forms.DateField(
        label="até", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    atrasadas = forms.BooleanField(label="Só atrasadas", required=False)
    sem_prazo = forms.BooleanField(label="Só sem prazo", required=False)

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = categorias_de(usuario)
        self.fields["q"].widget.attrs.update(
            {"id": "busca", "placeholder": "Título, descrição ou solicitante (atalho: /)"}
        )

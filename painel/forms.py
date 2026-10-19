from datetime import date, timedelta

from django import forms

from core import relogio

LIMITE_DIAS_PERIODO = 731  # dois anos


def mes_inteiro(primeiro_dia: date) -> tuple[date, date]:
    proximo = (primeiro_dia.replace(day=28) + timedelta(days=4)).replace(day=1)
    return primeiro_dia, proximo - timedelta(days=1)


class PeriodoForm(forms.Form):
    """Mês (padrão: o atual) ou intervalo personalizado (de/até)."""

    mes = forms.DateField(
        label="Mês",
        required=False,
        input_formats=["%Y-%m"],
        widget=forms.DateInput(attrs={"type": "month"}, format="%Y-%m"),
    )
    de = forms.DateField(label="De", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    ate = forms.DateField(
        label="Até", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

    def clean(self):
        dados = super().clean()
        de, ate = dados.get("de"), dados.get("ate")
        if bool(de) != bool(ate):
            raise forms.ValidationError("Para um intervalo personalizado, informe as duas datas.")
        if de and ate:
            if de > ate:
                raise forms.ValidationError("A data inicial deve ser anterior à final.")
            if (ate - de).days > LIMITE_DIAS_PERIODO:
                raise forms.ValidationError("Escolha um intervalo de até dois anos.")
        return dados

    def periodo(self) -> tuple[date, date]:
        """Período escolhido; sem escolha válida, o mês atual."""
        dados = self.cleaned_data if self.is_valid() else {}
        if dados.get("de") and dados.get("ate"):
            return dados["de"], dados["ate"]
        primeiro = dados.get("mes") or relogio.hoje().replace(day=1)
        return mes_inteiro(primeiro.replace(day=1))

from django import forms

PALAVRA_DE_CONFIRMACAO = "EXCLUIR"


class ApagarTudoForm(forms.Form):
    confirmacao = forms.CharField(
        label=f"Para confirmar, digite {PALAVRA_DE_CONFIRMACAO}",
        widget=forms.TextInput(attrs={"autocomplete": "off", "autofocus": True}),
    )

    def clean_confirmacao(self):
        valor = self.cleaned_data["confirmacao"].strip()
        if valor != PALAVRA_DE_CONFIRMACAO:
            raise forms.ValidationError(
                f"Digite exatamente {PALAVRA_DE_CONFIRMACAO}, em maiúsculas."
            )
        return valor

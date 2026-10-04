from datetime import date

from django import forms

from .models import Loan, Person
from .validators import only_digits


class PersonForm(forms.ModelForm):
    # Plain fields so "123.456.789-09" and "35570-000" are accepted as typed; the model's own
    # length and check-digit validators then run on the digits-only value.
    cpf = forms.CharField(
        label="CPF",
        widget=forms.TextInput(attrs={"inputmode": "numeric", "placeholder": "000.000.000-00"}),
    )
    cep = forms.CharField(
        label="CEP",
        widget=forms.TextInput(attrs={"inputmode": "numeric", "placeholder": "00000-000"}),
    )

    class Meta:
        model = Person
        fields = [
            "name",
            "cpf",
            "rg",
            "birth_date",
            "phone",
            "email",
            "cep",
            "street",
            "number",
            "complement",
            "neighborhood",
            "city",
            "state",
        ]
        widgets = {"birth_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def clean_cpf(self):
        return only_digits(self.cleaned_data["cpf"])

    def clean_cep(self):
        return only_digits(self.cleaned_data["cep"])

    def clean_birth_date(self):
        birth_date = self.cleaned_data["birth_date"]
        if birth_date > date.today():
            raise forms.ValidationError("A data de nascimento não pode estar no futuro.")
        return birth_date


class LoanForm(forms.ModelForm):
    """Borrower and guarantor arrive as ids from the HTMX person picker."""

    person = forms.ModelChoiceField(
        Person.objects.all(),
        widget=forms.HiddenInput,
        label="Quem recebe",
        error_messages={"required": "Escolha quem recebe o equipamento."},
    )
    guarantor = forms.ModelChoiceField(
        Person.objects.all(),
        widget=forms.HiddenInput,
        label="Fiador",
        error_messages={"required": "Escolha o fiador."},
    )

    class Meta:
        model = Loan
        fields = ["person", "guarantor", "lent_date", "due_date"]
        widgets = {
            "lent_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def clean(self):
        cleaned = super().clean()
        person, guarantor = cleaned.get("person"), cleaned.get("guarantor")
        if person and person == guarantor:
            self.add_error("guarantor", "O fiador não pode ser quem recebe o equipamento.")
        lent, due = cleaned.get("lent_date"), cleaned.get("due_date")
        if lent and due and due < lent:
            self.add_error("due_date", "A devolução não pode ser antes do empréstimo.")
        return cleaned

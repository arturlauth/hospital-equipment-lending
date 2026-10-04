from datetime import date

from django import forms

from .models import CONTRACT_MAX_MB, Loan, Person
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
        label="Beneficiário",
        error_messages={"required": "Escolha o beneficiário."},
    )
    guarantor = forms.ModelChoiceField(
        Person.objects.all(),
        widget=forms.HiddenInput,
        label="Solidário",
        error_messages={"required": "Escolha o solidário."},
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
            self.add_error("guarantor", "O solidário não pode ser o próprio beneficiário.")
        lent, due = cleaned.get("lent_date"), cleaned.get("due_date")
        if lent and due and due < lent:
            self.add_error("due_date", "A devolução não pode ser antes do empréstimo.")
        return cleaned


class ReturnForm(forms.Form):
    return_date = forms.DateField(
        label="Devolvido em", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    OK, DAMAGED, LOST = "ok", "damaged", "lost"
    condition = forms.ChoiceField(
        label="Como voltou",
        choices=[(OK, "Em ordem"), (DAMAGED, "Com defeito"), (LOST, "Extraviado")],
        initial=OK,
        required=False,
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, loan, **kwargs):
        super().__init__(*args, **kwargs)
        self.loan = loan

    def clean_return_date(self):
        return_date = self.cleaned_data["return_date"]
        if return_date < self.loan.lent_date:
            raise forms.ValidationError("A devolução não pode ser antes do empréstimo.")
        if return_date > date.today():
            raise forms.ValidationError("A devolução não pode estar no futuro.")
        return return_date

    def clean_condition(self):
        return self.cleaned_data["condition"] or self.OK


class LoanEditForm(forms.ModelForm):
    """Fix a loan's dates. Clearing the return date reopens the loan."""

    class Meta:
        model = Loan
        fields = ["due_date", "return_date"]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "return_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }
        help_texts = {"return_date": "Deixe em branco para desfazer a devolução."}

    reason = forms.CharField(label="Motivo da correção", widget=forms.Textarea(attrs={"rows": 2}))

    def clean_due_date(self):
        due_date = self.cleaned_data["due_date"]
        if due_date and due_date < self.instance.lent_date:
            raise forms.ValidationError("A devolução prevista não pode ser antes do empréstimo.")
        return due_date

    def clean_return_date(self):
        return_date = self.cleaned_data["return_date"]
        if return_date is None:
            lent_again = Loan.objects.filter(
                equipment_id=self.instance.equipment_id, return_date__isnull=True
            ).exclude(pk=self.instance.pk)
            if lent_again.exists():
                raise forms.ValidationError(
                    "Não dá para desfazer: o equipamento já foi emprestado de novo."
                )
        elif return_date < self.instance.lent_date:
            raise forms.ValidationError("A devolução não pode ser antes do empréstimo.")
        elif return_date > date.today():
            raise forms.ValidationError("A devolução não pode estar no futuro.")
        return return_date


class ContractForm(forms.Form):
    """The signed contract: a PDF of at most CONTRACT_MAX_MB."""

    contract = forms.FileField(
        label="Contrato assinado (PDF)", widget=forms.FileInput(attrs={"accept": "application/pdf"})
    )

    def clean_contract(self):
        upload = self.cleaned_data["contract"]
        if upload.size > CONTRACT_MAX_MB * 1024 * 1024:
            raise forms.ValidationError(f"O arquivo passa de {CONTRACT_MAX_MB} MB.")
        header = upload.read(5)
        upload.seek(0)
        if not upload.name.lower().endswith(".pdf") or header != b"%PDF-":
            raise forms.ValidationError("Envie o contrato em PDF.")
        return upload

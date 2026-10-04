from datetime import date

from django import forms


class StatusChangeForm(forms.Form):
    """Pick a new status among the ones `services.allowed_statuses` returns for this user."""

    to_status = forms.ChoiceField(label="Nova situação")
    effective_on = forms.DateField(
        label="Em", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    reason = forms.CharField(label="Motivo", widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, allowed, **kwargs):
        kwargs.setdefault("initial", {"effective_on": date.today()})
        super().__init__(*args, **kwargs)
        self.fields["to_status"].choices = [(s.value, s.label) for s in allowed]

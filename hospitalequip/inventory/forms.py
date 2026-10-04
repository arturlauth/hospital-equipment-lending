from datetime import date

from django import forms

from .models import Equipment, EquipmentImage, EquipmentSpec


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


class EquipmentForm(forms.ModelForm):
    """Create or edit an item. The category builds the patrimônio, so it is locked after creation."""

    class Meta:
        model = Equipment
        fields = ["name", "brand", "category", "warehouse", "description", "value", "acquired_on"]
        widgets = {
            "acquired_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["category"].disabled = True
            self.fields[
                "category"
            ].help_text = "Faz parte do patrimônio; não muda depois do cadastro."


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class NewImagesField(forms.ImageField):
    """Several photos in one input; each one is validated as an image."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleImageInput(attrs={"accept": "image/*"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else [data] if data else []
        return [super(NewImagesField, self).clean(f, initial) for f in files]


class NewImagesForm(forms.Form):
    images = NewImagesField(label="Adicionar fotos", required=False)


SpecFormSet = forms.inlineformset_factory(
    Equipment,
    EquipmentSpec,
    fields=["section", "label", "value"],
    extra=0,
    can_delete=True,
)

ImageFormSet = forms.inlineformset_factory(
    Equipment, EquipmentImage, fields=["order"], extra=0, can_delete=True
)

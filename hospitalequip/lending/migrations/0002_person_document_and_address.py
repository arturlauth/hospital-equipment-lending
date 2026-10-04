from django.db import migrations, models

import hospitalequip.lending.validators

STATES = [(uf, uf) for uf in "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()]


def required_text(name, max_length, verbose_name, **extra):
    """New required field; existing rows get '' and must be completed by staff."""
    return migrations.AddField(
        "person",
        name,
        models.CharField(default="", max_length=max_length, verbose_name=verbose_name, **extra),
        preserve_default=False,
    )


class Migration(migrations.Migration):
    dependencies = [("lending", "0001_initial")]

    operations = [
        migrations.AlterModelOptions(
            name="person",
            options={"ordering": ["name"], "verbose_name": "pessoa", "verbose_name_plural": "pessoas"},
        ),
        migrations.AlterField(
            "person",
            "cpf",
            models.CharField(max_length=11, unique=True, validators=[hospitalequip.lending.validators.validate_cpf], verbose_name="CPF"),
        ),
        migrations.AddField("person", "rg", models.CharField(blank=True, max_length=20, verbose_name="RG")),
        migrations.AddField("person", "complement", models.CharField(blank=True, max_length=60, verbose_name="complemento")),
        required_text("street", 150, "rua"),
        required_text("number", 20, "número"),
        required_text("neighborhood", 80, "bairro"),
        required_text("city", 80, "cidade"),
        required_text("state", 2, "UF", choices=STATES),
        required_text("cep", 8, "CEP", validators=[hospitalequip.lending.validators.validate_cep]),
    ]

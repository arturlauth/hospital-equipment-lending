import re
import unicodedata

import django.db.models.deletion
from django.db import migrations, models


def code_for(name):
    """'cadeira de rodas' -> 'CADEIRA_DE_RODAS' (frozen copy; migrations don't import app code)."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]+", "_", ascii_name.upper()).strip("_")[:20]


def text_category_to_table(apps, schema_editor):
    Category = apps.get_model("inventory", "Category")
    Equipment = apps.get_model("inventory", "Equipment")
    next_number = {}
    for item in Equipment.objects.order_by("id"):
        name = item.category_text.strip().lower()
        category, _ = Category.objects.get_or_create(
            name=name.capitalize(), defaults={"code": code_for(name)}
        )
        next_number[category.pk] = next_number.get(category.pk, 0) + 1
        item.category = category
        item.sequence = next_number[category.pk]
        item.tag = f"{category.code} {item.sequence:04d}"
        item.save()


class Migration(migrations.Migration):
    dependencies = [("inventory", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=50, unique=True, verbose_name="nome")),
                ("code", models.CharField(help_text="Prefixo do patrimônio, ex.: ANDADOR. Não altere depois de cadastrar itens.", max_length=20, unique=True, verbose_name="código")),
            ],
            options={"verbose_name": "categoria", "verbose_name_plural": "categorias", "ordering": ["name"]},
        ),
        # Convert the free-text category into a FK, then give existing items their tags.
        migrations.RenameField("equipment", "category", "category_text"),
        migrations.AddField(
            "equipment",
            "category",
            models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="equipment", to="inventory.category", verbose_name="categoria"),
        ),
        migrations.AddField("equipment", "sequence", models.PositiveIntegerField(editable=False, null=True, verbose_name="número")),
        migrations.AddField("equipment", "tag", models.CharField(editable=False, max_length=30, null=True, verbose_name="patrimônio")),
        migrations.RunPython(text_category_to_table, migrations.RunPython.noop),
        migrations.RemoveField("equipment", "category_text"),
        migrations.AlterField(
            "equipment",
            "category",
            models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="equipment", to="inventory.category", verbose_name="categoria"),
        ),
        migrations.AlterField("equipment", "sequence", models.PositiveIntegerField(editable=False, verbose_name="número")),
        migrations.AlterField("equipment", "tag", models.CharField(editable=False, max_length=30, unique=True, verbose_name="patrimônio")),
        # New descriptive fields.
        migrations.AddField("equipment", "brand", models.CharField(blank=True, max_length=100, verbose_name="marca")),
        migrations.AddField("equipment", "status", models.CharField(choices=[("active", "Ativo"), ("damaged", "Danificado"), ("written_off", "Baixado")], default="active", max_length=20, verbose_name="situação")),
        migrations.AddField("equipment", "value", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name="valor (R$)")),
        migrations.AddField("equipment", "acquired_on", models.DateField(blank=True, null=True, verbose_name="data de aquisição")),
        migrations.AddConstraint(
            "equipment",
            models.CheckConstraint(condition=models.Q(("value__isnull", True), ("value__gte", 0), _connector="OR"), name="equipment_value_not_negative"),
        ),
        migrations.CreateModel(
            name="EquipmentImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to="equipment/", verbose_name="imagem")),
                ("order", models.PositiveSmallIntegerField(default=0, verbose_name="ordem")),
                ("equipment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="images", to="inventory.equipment", verbose_name="equipamento")),
            ],
            options={"verbose_name": "imagem", "verbose_name_plural": "imagens", "ordering": ["order", "id"]},
        ),
        migrations.CreateModel(
            name="EquipmentSpec",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("section", models.CharField(max_length=60, verbose_name="seção")),
                ("label", models.CharField(max_length=100, verbose_name="item")),
                ("value", models.CharField(max_length=200, verbose_name="valor")),
                ("order", models.PositiveSmallIntegerField(default=0, verbose_name="ordem")),
                ("equipment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="specs", to="inventory.equipment", verbose_name="equipamento")),
            ],
            options={"verbose_name": "especificação", "verbose_name_plural": "especificações", "ordering": ["order", "id"]},
        ),
    ]

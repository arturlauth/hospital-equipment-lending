from django.db import migrations

# Frozen copy of hospitalequip.staff.roles: a migration must not import code that may change.
GROUPS = ["Atendente", "Gestor"]


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in GROUPS:
        Group.objects.get_or_create(name=name)


def delete_groups(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name__in=GROUPS).delete()


class Migration(migrations.Migration):
    dependencies = [("auth", "0012_alter_user_first_name_max_length")]

    operations = [migrations.RunPython(create_groups, delete_groups)]

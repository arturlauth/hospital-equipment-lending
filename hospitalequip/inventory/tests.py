import io
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.urls import reverse
from PIL import Image

from hospitalequip.inventory.models import (
    Category,
    Equipment,
    EquipmentImage,
    EquipmentSpec,
    Warehouse,
)
from hospitalequip.lending.models import Loan, Person
from hospitalequip.staff import roles


@pytest.fixture
def warehouse():
    return Warehouse.objects.create(name="Depósito teste")


@pytest.fixture
def walkers():
    return Category.objects.create(name="Andador", code="andador")


@pytest.fixture
def make_item(warehouse, walkers):
    """An equipment with `images` photo rows (no real files needed to test the rules)."""

    def make(images=3, **fields):
        item = Equipment.objects.create(
            name=fields.pop("name", "Andador"), category=walkers, warehouse=warehouse, **fields
        )
        for n in range(images):
            EquipmentImage.objects.create(equipment=item, image=f"equipment/{item.pk}-{n}.jpg")
        return item

    return make


def lend(item, due_date=None):
    person, _ = Person.objects.get_or_create(
        cpf="00000000099",
        defaults={"name": "Pessoa Teste", "birth_date": date(1950, 1, 1), "phone": "0"},
    )
    return Loan.objects.create(
        equipment=item, person=person, lent_date=date(2026, 9, 1), due_date=due_date
    )


def catalog(client):
    return {e.pk: e for e in client.get(reverse("inventory:catalog")).context["equipment_list"]}


# Rule: the public sees only items that are not written off and have at least 3 photos.


@pytest.mark.django_db
def test_catalog_lists_an_active_item_with_three_photos_as_available(client, make_item):
    item = make_item()
    assert catalog(client)[item.pk].is_available


@pytest.mark.django_db
def test_catalog_hides_an_item_with_fewer_than_three_photos(client, make_item):
    item = make_item(images=2)
    assert item.pk not in catalog(client)


@pytest.mark.django_db
def test_catalog_hides_a_written_off_item(client, make_item):
    item = make_item(status=Equipment.Status.WRITTEN_OFF)
    assert item.pk not in catalog(client)


@pytest.mark.django_db
def test_equipment_page_is_not_found_for_a_hidden_item(client, make_item):
    item = make_item(images=2)
    response = client.get(reverse("inventory:equipment", args=[item.pk]))
    assert response.status_code == 404


# Rule: a lent or damaged item stays listed, as unavailable; a lent one shows when it is due back.


@pytest.mark.django_db
def test_lent_item_is_unavailable_and_shows_its_due_date(client, make_item):
    item = make_item()
    lend(item, due_date=date(2027, 3, 1))
    shown = catalog(client)[item.pk]
    assert not shown.is_available
    assert shown.lent_until == date(2027, 3, 1)


@pytest.mark.django_db
def test_item_is_available_again_once_returned(client, make_item):
    item = make_item()
    loan = lend(item)
    loan.return_date = date(2026, 9, 10)
    loan.save()
    shown = catalog(client)[item.pk]
    assert shown.is_available
    assert shown.lent_until is None


@pytest.mark.django_db
def test_damaged_item_is_unavailable(client, make_item):
    item = make_item(status=Equipment.Status.DAMAGED)
    assert not catalog(client)[item.pk].is_available


@pytest.mark.django_db
def test_equipment_page_shows_availability(client, make_item):
    item = make_item()
    lend(item, due_date=date(2027, 3, 1))
    response = client.get(reverse("inventory:equipment", args=[item.pk]))
    assert not response.context["equipment"].is_available
    assert response.context["equipment"].lent_until == date(2027, 3, 1)


# Rule: the return month shows only on the equipment page; the pickup place only when it is free.


@pytest.mark.django_db
def test_catalog_says_unavailable_without_the_return_month(client, make_item):
    lend(make_item(), due_date=date(2027, 3, 1))
    page = client.get(reverse("inventory:catalog")).content.decode()
    assert "Indisponível" in page
    assert "Volta em" not in page


@pytest.mark.django_db
def test_equipment_page_shows_return_month_and_hides_pickup_place_when_lent(client, make_item):
    item = make_item()
    lend(item, due_date=date(2027, 3, 1))
    page = client.get(reverse("inventory:equipment", args=[item.pk])).content.decode()
    assert "Volta em" in page
    assert "Depósito teste" not in page


@pytest.mark.django_db
def test_equipment_page_shows_pickup_place_when_available(client, make_item):
    page = client.get(reverse("inventory:equipment", args=[make_item().pk])).content.decode()
    assert "Depósito teste" in page


# Rule: the asset tag is the category code + the next number in that category, assigned once.


@pytest.mark.django_db
def test_tags_number_each_category_separately(warehouse, walkers):
    beds = Category.objects.create(name="Cama", code="CAMA")
    first = Equipment.objects.create(name="A", category=walkers, warehouse=warehouse)
    second = Equipment.objects.create(name="B", category=walkers, warehouse=warehouse)
    bed = Equipment.objects.create(name="C", category=beds, warehouse=warehouse)
    assert [first.tag, second.tag, bed.tag] == ["ANDADOR 0001", "ANDADOR 0002", "CAMA 0001"]


@pytest.mark.django_db
def test_numbering_continues_after_an_imported_plate(warehouse, walkers):
    Equipment.objects.create(
        name="Placa antiga", category=walkers, warehouse=warehouse, sequence=62
    )
    new = Equipment.objects.create(name="Novo", category=walkers, warehouse=warehouse)
    assert new.tag == "ANDADOR 0063"


@pytest.mark.django_db
def test_tag_never_changes_after_creation(warehouse, walkers):
    item = Equipment.objects.create(name="A", category=walkers, warehouse=warehouse)
    walkers.code = "ANDA"
    walkers.save()
    item.name = "Renomeado"
    item.save()
    item.refresh_from_db()
    assert item.tag == "ANDADOR 0001"


# Rule: an equipment's value, when known, is never negative.


@pytest.mark.django_db
def test_negative_value_is_rejected(warehouse, walkers):
    with pytest.raises(IntegrityError):
        Equipment.objects.create(
            name="A", category=walkers, warehouse=warehouse, value=Decimal("-1.00")
        )


@pytest.mark.django_db
def test_only_available_filter_hides_lent_and_damaged_items(client, make_item):
    free = make_item()
    lend(make_item())
    make_item(status=Equipment.Status.DAMAGED)
    response = client.get(reverse("inventory:catalog"), {"disponiveis": "1"})
    assert [e.pk for e in response.context["equipment_list"]] == [free.pk]


# Rule: status changes go through change_status, logged; write-off is Gestor only, never with an
# open loan; written off is final; dates are not in the future nor before the last change.


@pytest.fixture
def staff_user(db):
    def make(role):
        user = User.objects.create_user(role, password="x")
        user.groups.add(Group.objects.get(name=role))
        return user

    return make


def set_status(client, item, to, on="2026-09-10", reason="Roda quebrada"):
    return client.post(
        reverse("inventory:equipment_status", args=[item.pk]),
        {"to_status": to, "effective_on": on, "reason": reason},
    )


@pytest.mark.django_db
def test_attendant_sends_equipment_to_maintenance_and_it_is_logged(client, make_item, staff_user):
    item, user = make_item(), staff_user(roles.ATTENDANT)
    client.force_login(user)
    assert set_status(client, item, "damaged").status_code == 302
    item.refresh_from_db()
    change = item.status_logs.get()
    assert item.status == Equipment.Status.DAMAGED
    assert (change.from_status, change.to_status) == ("active", "damaged")
    assert (change.effective_on, change.reason, change.changed_by) == (
        date(2026, 9, 10),
        "Roda quebrada",
        user,
    )


@pytest.mark.django_db
def test_attendant_cannot_write_off(client, make_item, staff_user):
    item = make_item()
    client.force_login(staff_user(roles.ATTENDANT))
    set_status(client, item, "written_off")
    item.refresh_from_db()
    assert item.status == Equipment.Status.ACTIVE
    assert not item.status_logs.exists()


@pytest.mark.django_db
def test_gestor_writes_off_a_lost_item(client, make_item, staff_user):
    item = make_item(status=Equipment.Status.LOST)
    client.force_login(staff_user(roles.MANAGER))
    set_status(client, item, "written_off", reason="Não encontrado")
    item.refresh_from_db()
    assert item.status == Equipment.Status.WRITTEN_OFF


@pytest.mark.django_db
def test_write_off_is_blocked_while_a_loan_is_open(client, make_item, staff_user):
    item = make_item()
    lend(item)
    client.force_login(staff_user(roles.MANAGER))
    set_status(client, item, "written_off")
    item.refresh_from_db()
    assert item.status == Equipment.Status.ACTIVE


@pytest.mark.django_db
def test_written_off_is_final(client, make_item, staff_user):
    item = make_item(status=Equipment.Status.WRITTEN_OFF)
    client.force_login(staff_user(roles.MANAGER))
    set_status(client, item, "active")
    item.refresh_from_db()
    assert item.status == Equipment.Status.WRITTEN_OFF


@pytest.mark.parametrize("on", ["2999-01-01", "2026-09-04"])
@pytest.mark.django_db
def test_status_date_is_not_in_the_future_nor_before_the_last_change(
    client, make_item, staff_user, on
):
    item = make_item()
    client.force_login(staff_user(roles.ATTENDANT))
    set_status(client, item, "damaged", on="2026-09-05")
    response = set_status(client, item, "active", on=on)
    assert response.status_code == 200
    item.refresh_from_db()
    assert item.status == Equipment.Status.DAMAGED


@pytest.mark.django_db
def test_status_change_needs_a_reason(client, make_item, staff_user):
    item = make_item()
    client.force_login(staff_user(roles.ATTENDANT))
    set_status(client, item, "damaged", reason="  ")
    assert not item.status_logs.exists()


@pytest.mark.django_db
def test_database_rejects_a_change_to_the_same_status(make_item, staff_user):
    with pytest.raises(IntegrityError):
        make_item().status_logs.create(
            from_status="active",
            to_status="active",
            effective_on=date(2026, 9, 1),
            reason="x",
            changed_by=staff_user(roles.MANAGER),
        )


@pytest.mark.django_db
def test_lost_item_is_hidden_from_the_public_but_staff_still_open_it(client, make_item, staff_user):
    item = make_item(status=Equipment.Status.LOST)
    assert item.pk not in catalog(client)
    url = reverse("inventory:equipment", args=[item.pk])
    assert client.get(url).status_code == 404
    client.force_login(staff_user(roles.ATTENDANT))
    assert client.get(url).status_code == 200


# Rule: logs live only under Registros, which only the Gestor opens.


@pytest.mark.django_db
def test_registros_lists_status_logs_for_the_gestor(client, make_item, staff_user):
    item = make_item(name="Andador X")
    client.force_login(staff_user(roles.ATTENDANT))
    set_status(client, item, "damaged")
    client.force_login(staff_user(roles.MANAGER))
    response = client.get(reverse("inventory:status_log"), {"q": item.tag})
    assert [c.equipment for c in response.context["changes"]] == [item]
    assert not client.get(reverse("inventory:status_log"), {"q": "nada"}).context["changes"]


@pytest.mark.django_db
def test_registros_is_forbidden_to_attendants(client, staff_user):
    client.force_login(staff_user(roles.ATTENDANT))
    assert client.get(reverse("inventory:status_log")).status_code == 403


@pytest.mark.django_db
def test_equipment_page_never_shows_the_status_log(client, make_item, staff_user):
    item = make_item()
    client.force_login(staff_user(roles.ATTENDANT))
    set_status(client, item, "damaged", reason="Motivo secreto")
    client.force_login(staff_user(roles.MANAGER))
    page = client.get(reverse("inventory:equipment", args=[item.pk])).content.decode()
    assert "Motivo secreto" not in page


# --- Equipment form (staff create/edit) -----------------------------------------------------


def png(name="foto.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 3), "teal").save(buffer, "PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def equipment_post(item=None, specs=(), photos=(), new_images=(), **fields):
    """POST data for the equipment form: specs are (section, label, value[, delete]) rows."""
    data = {
        "name": "Andador articulado",
        "brand": "",
        "category": fields.pop("category"),
        "warehouse": fields.pop("warehouse"),
        "description": "",
        "value": "",
        "acquired_on": "",
        "specs-TOTAL_FORMS": len(specs),
        "specs-INITIAL_FORMS": sum(1 for s in specs if s[0] is not None and len(s) > 3),
        "images-TOTAL_FORMS": len(photos),
        "images-INITIAL_FORMS": len(photos),
        "images": list(new_images),
    } | fields
    for n, row in enumerate(specs):
        spec_id, section, label, value, *delete = row
        data |= {
            f"specs-{n}-id": spec_id or "",
            f"specs-{n}-section": section,
            f"specs-{n}-label": label,
            f"specs-{n}-value": value,
        }
        if delete:
            data[f"specs-{n}-DELETE"] = "on"
    for n, (photo_id, order, *delete) in enumerate(photos):
        data |= {f"images-{n}-id": photo_id, f"images-{n}-order": order}
        if delete:
            data[f"images-{n}-DELETE"] = "on"
    return data


@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


# Rule: any staff member creates an item; the patrimônio is generated from its category.


@pytest.mark.django_db
def test_attendant_creates_an_item_with_photos_and_ordered_specs(
    client, staff_user, warehouse, walkers, media
):
    client.force_login(staff_user(roles.ATTENDANT))
    data = equipment_post(
        category=walkers.pk,
        warehouse=warehouse.pk,
        specs=[(None, "Medidas", "Altura", "90 cm"), (None, "Medidas", "Peso", "3 kg")],
        new_images=[png("a.png"), png("b.png"), png("c.png")],
    )
    data["specs-INITIAL_FORMS"] = 0
    response = client.post(reverse("inventory:equipment_new"), data)
    item = Equipment.objects.get()
    assert response.url == reverse("inventory:equipment", args=[item.pk])
    assert item.tag == "ANDADOR 0001"
    assert [s.label for s in item.specs.all()] == ["Altura", "Peso"]
    assert item.images.count() == 3


@pytest.mark.django_db
def test_edit_never_changes_category_nor_patrimonio(client, staff_user, make_item, warehouse):
    item = make_item(images=0)
    beds = Category.objects.create(name="Cama", code="CAMA")
    client.force_login(staff_user(roles.ATTENDANT))
    data = equipment_post(category=beds.pk, warehouse=warehouse.pk, name="Novo nome")
    client.post(reverse("inventory:equipment_edit", args=[item.pk]), data)
    item.refresh_from_db()
    assert (item.name, item.category, item.tag) == ("Novo nome", item.category, "ANDADOR 0001")
    assert item.category.code == "ANDADOR"


@pytest.mark.django_db
def test_edit_removes_a_spec_row_and_ignores_a_blank_new_row(
    client, staff_user, make_item, warehouse, walkers
):
    item = make_item(images=0)
    keep = EquipmentSpec.objects.create(equipment=item, section="A", label="Fica", value="1")
    drop = EquipmentSpec.objects.create(equipment=item, section="A", label="Sai", value="2")
    client.force_login(staff_user(roles.ATTENDANT))
    data = equipment_post(
        category=walkers.pk,
        warehouse=warehouse.pk,
        specs=[
            (keep.pk, "A", "Fica", "1", False),
            (drop.pk, "A", "Sai", "2", True),
            (None, "", "", ""),
        ],
    )
    data["specs-INITIAL_FORMS"] = 2
    data.pop("specs-0-DELETE", None)
    client.post(reverse("inventory:equipment_edit", args=[item.pk]), data)
    assert list(item.specs.values_list("label", flat=True)) == ["Fica"]


@pytest.mark.django_db
def test_edit_removes_a_photo(client, staff_user, make_item, warehouse, walkers):
    item = make_item(images=3)
    first, *rest = item.images.all()
    client.force_login(staff_user(roles.ATTENDANT))
    photos = [(first.pk, 0, True), *((p.pk, n + 1) for n, p in enumerate(rest))]
    data = equipment_post(category=walkers.pk, warehouse=warehouse.pk, photos=photos)
    client.post(reverse("inventory:equipment_edit", args=[item.pk]), data)
    assert list(item.images.values_list("pk", flat=True)) == [p.pk for p in rest]


@pytest.mark.django_db
def test_equipment_form_is_staff_only(client, warehouse, walkers):
    response = client.get(reverse("inventory:equipment_new"))
    assert response.status_code == 302
    client.force_login(User.objects.create_user("visitante", password="x"))
    assert client.get(reverse("inventory:equipment_new")).status_code == 403


# --- Listings: public catalog and staff equipment view --------------------------------------


def staff_list(client, **params):
    return {
        e.pk
        for e in client.get(reverse("inventory:staff_equipment"), params).context["equipment_list"]
    }


# Rule: the staff view shows every item, hidden ones included; Baixado only when chosen.


@pytest.mark.django_db
def test_staff_list_shows_hidden_items_but_baixado_only_when_chosen(client, staff_user, make_item):
    no_photos = make_item(images=0)
    lost = make_item(status=Equipment.Status.LOST)
    written_off = make_item(status=Equipment.Status.WRITTEN_OFF)
    client.force_login(staff_user(roles.ATTENDANT))
    assert staff_list(client) == {no_photos.pk, lost.pk}
    assert staff_list(client, situacao="written_off") == {written_off.pk}


@pytest.mark.django_db
def test_staff_list_lent_filter_follows_open_loans(client, staff_user, make_item):
    lent, free, returned = make_item(), make_item(), make_item()
    lend(lent)
    loan = lend(returned)
    loan.return_date = date(2026, 9, 5)
    loan.save()
    client.force_login(staff_user(roles.ATTENDANT))
    assert staff_list(client, emprestimo="emprestado") == {lent.pk}
    assert staff_list(client, emprestimo="livre") == {free.pk, returned.pk}


@pytest.mark.django_db
def test_staff_list_filters_combine_and_search_finds_the_patrimonio(
    client, staff_user, make_item, warehouse
):
    walker = make_item()
    bed = Equipment.objects.create(
        name="Cama", category=Category.objects.create(name="Cama", code="CAMA"), warehouse=warehouse
    )
    lend(walker)
    client.force_login(staff_user(roles.ATTENDANT))
    assert staff_list(client, categoria=walker.category_id, emprestimo="emprestado") == {walker.pk}
    assert staff_list(client, categoria=bed.category_id, emprestimo="emprestado") == set()
    assert staff_list(client, q="cama 0001") == {bed.pk}


@pytest.mark.django_db
def test_staff_list_is_staff_only(client):
    assert client.get(reverse("inventory:staff_equipment")).status_code == 302


# Rule: the public catalog is a paged feed of 24 items, filterable by category.


@pytest.mark.django_db
def test_catalog_pages_hold_24_items(client, make_item):
    items = [make_item(name=f"Andador {n:02d}") for n in range(25)]
    assert len(catalog(client)) == 24
    page_two = client.get(reverse("inventory:catalog"), {"pagina": 2}).context["equipment_list"]
    assert [e.pk for e in page_two] == [items[-1].pk]


@pytest.mark.django_db
def test_catalog_category_filter_never_shows_hidden_items(client, make_item, walkers):
    shown = make_item()
    make_item(images=2)
    response = client.get(reverse("inventory:catalog"), {"categoria": walkers.pk})
    assert [e.pk for e in response.context["equipment_list"]] == [shown.pk]

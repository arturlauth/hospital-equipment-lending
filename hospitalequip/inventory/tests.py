from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.urls import reverse

from hospitalequip.inventory.models import Category, Equipment, Warehouse
from hospitalequip.lending.models import Loan, Person


@pytest.fixture
def warehouse():
    return Warehouse.objects.create(name="Depósito teste")


@pytest.fixture
def walkers():
    return Category.objects.create(name="Andador", code="andador")


@pytest.fixture
def lent_and_free(warehouse, walkers):
    lent = Equipment.objects.create(name="Andador A", category=walkers, warehouse=warehouse)
    free = Equipment.objects.create(name="Andador B", category=walkers, warehouse=warehouse)
    person = Person.objects.create(
        name="Pessoa Teste", cpf="00000000099", birth_date=date(1950, 1, 1), phone="0"
    )
    loan = Loan.objects.create(equipment=lent, person=person, lent_date=date(2026, 9, 1))
    return loan, free


@pytest.mark.django_db
def test_catalog_hides_equipment_on_open_loan(client, lent_and_free):
    _, free = lent_and_free
    response = client.get(reverse("inventory:catalog"))
    assert list(response.context["equipment_list"]) == [free]


@pytest.mark.django_db
def test_catalog_shows_equipment_again_once_returned(client, lent_and_free):
    loan, free = lent_and_free
    loan.return_date = date(2026, 9, 10)
    loan.save()
    response = client.get(reverse("inventory:catalog"))
    assert set(response.context["equipment_list"]) == {loan.equipment, free}


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

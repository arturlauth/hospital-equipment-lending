from datetime import date

import pytest
from django.urls import reverse

from hospitalequip.inventory.models import Equipment, Warehouse
from hospitalequip.lending.models import Loan, Person


@pytest.fixture
def lent_and_free():
    warehouse = Warehouse.objects.create(name="Depósito teste")
    lent = Equipment.objects.create(name="Cadeira A", category="cadeira", warehouse=warehouse)
    free = Equipment.objects.create(name="Cadeira B", category="cadeira", warehouse=warehouse)
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

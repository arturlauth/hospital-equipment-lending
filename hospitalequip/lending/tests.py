import os
from datetime import date

import pytest
from django.db import IntegrityError

from hospitalequip.inventory.models import Equipment, Warehouse
from hospitalequip.lending.models import Loan, Person


@pytest.fixture
def open_loan():
    # The test builds the exact rows it needs, so nothing outside this file can break it.
    warehouse = Warehouse.objects.create(name="Depósito teste")
    equipment = Equipment.objects.create(
        name="Cadeira de rodas", category="cadeira", warehouse=warehouse
    )
    person = Person.objects.create(
        name="Pessoa Teste", cpf="00000000099", birth_date=date(1950, 1, 1), phone="0"
    )
    return Loan.objects.create(equipment=equipment, person=person, lent_date=date(2026, 9, 1))


@pytest.mark.django_db
def test_second_open_loan_for_same_equipment_is_rejected(open_loan):
    with pytest.raises(IntegrityError):
        Loan.objects.create(
            equipment=open_loan.equipment, person=open_loan.person, lent_date=date(2026, 9, 2)
        )

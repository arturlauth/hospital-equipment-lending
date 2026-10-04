from datetime import date

import pytest
from django.contrib.auth.models import Group, User
from django.db import IntegrityError
from django.urls import reverse

from hospitalequip.inventory.models import Category, Equipment, Warehouse
from hospitalequip.lending.models import Loan, Person
from hospitalequip.lending.views import add_months
from hospitalequip.staff import roles


@pytest.fixture
def open_loan():
    # The test builds the exact rows it needs, so nothing outside this file can break it.
    warehouse = Warehouse.objects.create(name="Depósito teste")
    equipment = Equipment.objects.create(
        name="Cadeira de rodas",
        category=Category.objects.create(name="Cadeira de rodas", code="CADEIRA"),
        warehouse=warehouse,
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


# --- Borrower registration ---------------------------------------------------------------


def person_data(**overrides):
    data = {
        "name": "Maria da Silva",
        "cpf": "529.982.247-25",
        "rg": "",
        "birth_date": "1960-05-10",
        "phone": "(37) 99999-0000",
        "email": "",
        "cep": "35570-000",
        "street": "Rua das Flores",
        "number": "10",
        "complement": "",
        "neighborhood": "Centro",
        "city": "Formiga",
        "state": "MG",
    }
    return data | overrides


@pytest.fixture
def attendant(client):
    user = User.objects.create_user("atendente", password="x")
    user.groups.add(Group.objects.get(name=roles.ATTENDANT))
    client.force_login(user)
    return user


# Rule: a person is registered with a valid CPF, stored as digits only and never twice.


@pytest.mark.django_db
def test_attendant_registers_a_person_with_formatted_cpf_and_cep(client, attendant):
    response = client.post(reverse("lending:person_new"), person_data())
    person = Person.objects.get()
    assert response.url == reverse("lending:person", args=[person.pk])
    assert (person.cpf, person.cep) == ("52998224725", "35570000")


@pytest.mark.parametrize("cpf", ["529.982.247-24", "111.111.111-11", "5299822472"])
@pytest.mark.django_db
def test_invalid_cpf_is_rejected(client, attendant, cpf):
    response = client.post(reverse("lending:person_new"), person_data(cpf=cpf))
    assert "cpf" in response.context["form"].errors
    assert not Person.objects.exists()


@pytest.mark.django_db
def test_same_cpf_cannot_be_registered_twice_even_formatted_differently(client, attendant):
    client.post(reverse("lending:person_new"), person_data(cpf="52998224725"))
    response = client.post(reverse("lending:person_new"), person_data(cpf="529.982.247-25"))
    assert "cpf" in response.context["form"].errors
    assert Person.objects.count() == 1


@pytest.mark.django_db
def test_cep_must_have_eight_digits(client, attendant):
    response = client.post(reverse("lending:person_new"), person_data(cep="3557-000"))
    assert "cep" in response.context["form"].errors


@pytest.mark.django_db
def test_birth_date_cannot_be_in_the_future(client, attendant):
    response = client.post(reverse("lending:person_new"), person_data(birth_date="2999-01-01"))
    assert "birth_date" in response.context["form"].errors


@pytest.mark.django_db
def test_search_finds_a_person_by_formatted_cpf(client, attendant):
    client.post(reverse("lending:person_new"), person_data())
    response = client.get(reverse("lending:people"), {"q": "529.982"})
    assert [p.name for p in response.context["people"]] == ["Maria da Silva"]


# Rule: personal data is visible only to staff roles.


@pytest.mark.django_db
def test_people_pages_send_anonymous_visitors_to_login(client):
    response = client.get(reverse("lending:people"))
    assert response.url.startswith(reverse("staff:login"))


@pytest.mark.django_db
def test_logged_in_user_without_a_staff_role_is_forbidden(client):
    client.force_login(User.objects.create_user("sem-papel", password="x"))
    assert client.get(reverse("lending:people")).status_code == 403


# --- Lending -------------------------------------------------------------------------------


@pytest.fixture
def lendable(open_loan):
    """A second, free wheelchair plus a guarantor; open_loan's equipment stays lent."""
    equipment = Equipment.objects.create(
        name="Andador",
        category=open_loan.equipment.category,
        warehouse=open_loan.equipment.warehouse,
    )
    guarantor = Person.objects.create(
        name="Fiador Teste", cpf="52998224725", birth_date=date(1970, 1, 1), phone="0"
    )
    return equipment, open_loan.person, guarantor


def lend_data(person, guarantor, **overrides):
    data = {
        "person": person.pk,
        "guarantor": guarantor.pk,
        "lent_date": "2026-10-03",
        "due_date": "2027-04-03",
    }
    return data | overrides


# Rule: a loan has a borrower and a different guarantor, on equipment that is free and active.


@pytest.mark.django_db
def test_attendant_lends_free_equipment_and_lands_on_the_loan(client, attendant, lendable):
    equipment, person, guarantor = lendable
    response = client.post(
        reverse("lending:lend", args=[equipment.pk]), lend_data(person, guarantor)
    )
    loan = Loan.objects.get(equipment=equipment)
    assert response.url == reverse("lending:loan", args=[loan.pk])
    assert (loan.person, loan.guarantor, loan.return_date) == (person, guarantor, None)


@pytest.mark.django_db
def test_guarantor_cannot_be_the_borrower(client, attendant, lendable):
    equipment, person, _ = lendable
    response = client.post(reverse("lending:lend", args=[equipment.pk]), lend_data(person, person))
    assert "guarantor" in response.context["form"].errors
    assert not Loan.objects.filter(equipment=equipment).exists()


@pytest.mark.django_db
def test_database_rejects_guarantor_equal_to_borrower(open_loan):
    open_loan.guarantor = open_loan.person
    with pytest.raises(IntegrityError):
        open_loan.save()


@pytest.mark.django_db
def test_loan_needs_a_guarantor(client, attendant, lendable):
    equipment, person, guarantor = lendable
    response = client.post(
        reverse("lending:lend", args=[equipment.pk]),
        lend_data(person, guarantor) | {"guarantor": ""},
    )
    assert "guarantor" in response.context["form"].errors


@pytest.mark.django_db
def test_due_date_cannot_be_before_lent_date(client, attendant, lendable):
    equipment, person, guarantor = lendable
    response = client.post(
        reverse("lending:lend", args=[equipment.pk]),
        lend_data(person, guarantor, due_date="2026-10-02"),
    )
    assert "due_date" in response.context["form"].errors


@pytest.mark.django_db
def test_equipment_already_lent_cannot_be_lent_again(client, attendant, lendable, open_loan):
    _, person, guarantor = lendable
    response = client.post(
        reverse("lending:lend", args=[open_loan.equipment.pk]), lend_data(person, guarantor)
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_damaged_equipment_cannot_be_lent(client, attendant, lendable):
    equipment, person, guarantor = lendable
    equipment.status = Equipment.Status.DAMAGED
    equipment.save()
    response = client.post(
        reverse("lending:lend", args=[equipment.pk]), lend_data(person, guarantor)
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_lend_form_suggests_due_date_six_months_ahead(client, attendant, lendable):
    response = client.get(reverse("lending:lend", args=[lendable[0].pk]))
    form = response.context["form"]
    lent, due = form.initial["lent_date"], form.initial["due_date"]
    assert (due.year * 12 + due.month) - (lent.year * 12 + lent.month) == 6


@pytest.mark.parametrize(
    ("start", "expected"),
    [(date(2026, 8, 31), date(2027, 2, 28)), (date(2026, 10, 3), date(2027, 4, 3))],
)
def test_add_months_clamps_to_the_last_day_of_the_month(start, expected):
    assert add_months(start, 6) == expected


@pytest.mark.django_db
def test_person_picker_leaves_out_the_one_chosen_in_the_other_box(client, attendant, lendable):
    _, person, guarantor = lendable
    response = client.get(
        reverse("lending:person_picker"), {"campo": "guarantor", "q": "teste", "person": person.pk}
    )
    assert list(response.context["results"]) == [guarantor]

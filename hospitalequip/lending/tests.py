from datetime import date

import pytest
from django.contrib.auth.models import Group, User
from django.db import IntegrityError
from django.urls import reverse

from hospitalequip.inventory.models import Category, Equipment, Warehouse
from hospitalequip.lending.models import Loan, Person
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

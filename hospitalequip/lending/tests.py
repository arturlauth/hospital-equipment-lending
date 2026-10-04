from datetime import date, timedelta

import pytest
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.urls import reverse

from hospitalequip.inventory.models import Category, Equipment, EquipmentImage, Warehouse
from hospitalequip.lending.models import Loan, LoanLog, Person
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
        name="Solidário Teste", cpf="52998224725", birth_date=date(1970, 1, 1), phone="0"
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


# Rule: returning closes the loan once; "voltou com defeito" takes the equipment out of lending.


@pytest.mark.django_db
def test_return_closes_the_loan_and_frees_the_equipment(client, attendant, open_loan):
    client.post(reverse("lending:return", args=[open_loan.pk]), {"return_date": "2026-09-15"})
    open_loan.refresh_from_db()
    assert open_loan.return_date == date(2026, 9, 15)
    assert open_loan.equipment.status == Equipment.Status.ACTIVE


@pytest.mark.django_db
def test_return_with_defect_marks_equipment_damaged(client, attendant, open_loan):
    client.post(
        reverse("lending:return", args=[open_loan.pk]),
        {"return_date": "2026-09-15", "condition": "damaged"},
    )
    open_loan.equipment.refresh_from_db()
    assert open_loan.equipment.status == Equipment.Status.DAMAGED


@pytest.mark.django_db
def test_loan_cannot_be_returned_twice(client, attendant, open_loan):
    url = reverse("lending:return", args=[open_loan.pk])
    client.post(url, {"return_date": "2026-09-15"})
    assert client.post(url, {"return_date": "2026-09-20"}).status_code == 404
    open_loan.refresh_from_db()
    assert open_loan.return_date == date(2026, 9, 15)


@pytest.mark.parametrize("return_date", ["2026-08-31", "2999-01-01"])
@pytest.mark.django_db
def test_return_date_must_be_between_lent_date_and_today(client, attendant, open_loan, return_date):
    response = client.post(
        reverse("lending:return", args=[open_loan.pk]), {"return_date": return_date}
    )
    assert "return_date" in response.context["return_form"].errors
    open_loan.refresh_from_db()
    assert open_loan.return_date is None


@pytest.mark.django_db
def test_returned_equipment_can_be_lent_again(client, attendant, lendable, open_loan):
    _, person, guarantor = lendable
    client.post(reverse("lending:return", args=[open_loan.pk]), {"return_date": "2026-09-15"})
    response = client.post(
        reverse("lending:lend", args=[open_loan.equipment.pk]), lend_data(person, guarantor)
    )
    assert response.status_code == 302
    assert open_loan.equipment.loans.filter(return_date__isnull=True).count() == 1


# Rule: staff can correct a loan's dates; clearing the return date reopens it, unless lent again.


@pytest.fixture
def returned_loan(open_loan):
    open_loan.return_date = date(2026, 9, 15)
    open_loan.save()
    return open_loan


def edit(client, loan, **data):
    return client.post(
        reverse("lending:loan_edit", args=[loan.pk]),
        {"due_date": "", "reason": "Erro de digitação", **data},
    )


@pytest.mark.django_db
def test_staff_corrects_a_mistyped_return_date(client, attendant, returned_loan):
    edit(client, returned_loan, return_date="2026-09-12")
    returned_loan.refresh_from_db()
    assert returned_loan.return_date == date(2026, 9, 12)


@pytest.mark.django_db
def test_clearing_the_return_date_reopens_the_loan(client, attendant, returned_loan):
    response = edit(client, returned_loan, return_date="")
    returned_loan.refresh_from_db()
    assert response.status_code == 302
    assert returned_loan.return_date is None


@pytest.mark.django_db
def test_return_cannot_be_undone_once_the_equipment_was_lent_again(
    client, attendant, returned_loan
):
    Loan.objects.create(
        equipment=returned_loan.equipment,
        person=Person.objects.create(
            name="Outra", cpf="52998224725", birth_date=date(1970, 1, 1), phone="0"
        ),
        lent_date=date(2026, 9, 20),
    )
    response = edit(client, returned_loan, return_date="")
    assert "return_date" in response.context["form"].errors
    returned_loan.refresh_from_db()
    assert returned_loan.return_date == date(2026, 9, 15)


@pytest.mark.parametrize("return_date", ["2026-08-31", "2999-01-01"])
@pytest.mark.django_db
def test_corrected_return_date_stays_between_lent_date_and_today(
    client, attendant, returned_loan, return_date
):
    response = edit(client, returned_loan, return_date=return_date)
    assert "return_date" in response.context["form"].errors


@pytest.mark.django_db
def test_equipment_page_lists_its_loan_history_for_staff(client, attendant, returned_loan):
    item = returned_loan.equipment
    for n in range(3):  # enough photos to be public
        EquipmentImage.objects.create(equipment=item, image=f"equipment/{n}.jpg")
    reopened = Loan.objects.create(
        equipment=item, person=returned_loan.person, lent_date=date(2026, 9, 20)
    )
    response = client.get(reverse("inventory:equipment", args=[item.pk]))
    assert response.context["loans"] == [reopened, returned_loan]
    assert response.context["open_loan"] == reopened


# Rule: the history filters by status (open, overdue, returned) and by equipment name or tag.


@pytest.mark.django_db
def test_history_filters_by_status(client, attendant, open_loan, lendable):
    equipment, person, _ = lendable
    overdue = open_loan  # due date set below, in the past
    overdue.due_date = date(2026, 9, 2)
    overdue.save()
    returned = Loan.objects.create(
        equipment=equipment, person=person, lent_date=date(2026, 9, 1), return_date=date(2026, 9, 3)
    )

    def shown(status):
        return list(client.get(reverse("lending:loans"), {"situacao": status}).context["loans"])

    assert shown("abertos") == [overdue]
    assert shown("atrasados") == [overdue]
    assert shown("devolvidos") == [returned]
    assert set(shown("")) == {overdue, returned}


@pytest.mark.django_db
def test_open_loan_due_today_is_not_overdue(client, attendant, open_loan):
    open_loan.due_date = date.today()
    open_loan.save()
    response = client.get(reverse("lending:loans"), {"situacao": "atrasados"})
    assert list(response.context["loans"]) == []


@pytest.mark.django_db
def test_history_finds_equipment_by_tag(client, attendant, open_loan, lendable):
    response = client.get(
        reverse("lending:loans"), {"equipamento": open_loan.equipment.tag.lower()}
    )
    assert list(response.context["loans"]) == [open_loan]


@pytest.mark.django_db
def test_tapping_the_active_status_chip_clears_it_and_keeps_the_search(client, attendant):
    response = client.get(
        reverse("lending:loans"), {"situacao": "abertos", "equipamento": "andador"}
    )
    chips = {chip["label"]: chip for chip in response.context["chips"]}
    assert chips["Em aberto"]["active"]
    assert chips["Em aberto"]["query"] == "equipamento=andador"
    assert chips["Devolvidos"]["query"] == "situacao=devolvidos&equipamento=andador"


@pytest.mark.django_db
def test_history_page_renders_each_loan_row(client, attendant, open_loan):
    page = client.get(reverse("lending:loans")).content.decode()
    assert reverse("lending:loan", args=[open_loan.pk]) in page


@pytest.mark.parametrize(
    ("due", "returned", "overdue"),
    [(-1, False, True), (0, False, False), (-1, True, False), (None, False, False)],
)
@pytest.mark.django_db
def test_loan_is_overdue_only_when_open_and_past_due(open_loan, due, returned, overdue):
    today = date.today()
    open_loan.due_date = today + timedelta(days=due) if due is not None else None
    open_loan.return_date = today if returned else None
    assert open_loan.is_overdue is overdue


@pytest.mark.django_db
def test_person_page_marks_an_overdue_loan_as_late(client, attendant, open_loan):
    open_loan.due_date = date(2026, 9, 2)
    open_loan.save()
    page = client.get(reverse("lending:person", args=[open_loan.person.pk])).content.decode()
    assert "Atrasado" in page


@pytest.mark.django_db
def test_loan_page_warns_when_open_loan_equipment_is_not_active(client, attendant, open_loan):
    open_loan.equipment.status = Equipment.Status.DAMAGED
    open_loan.equipment.save()
    page = client.get(reverse("lending:loan", args=[open_loan.pk])).content.decode()
    assert "Equipamento em manutenção" in page


# Rule: every loan action is logged with who, when and the changed fields; only the Gestor sees it.


@pytest.mark.django_db
def test_lending_logs_who_lent(client, attendant, lendable):
    equipment, person, guarantor = lendable
    client.post(reverse("lending:lend", args=[equipment.pk]), lend_data(person, guarantor))
    event = LoanLog.objects.get()
    assert (event.action, event.changed_by) == (LoanLog.Action.LENT, attendant)


@pytest.mark.django_db
def test_return_logs_the_return_date_and_condition(client, attendant, open_loan):
    client.post(
        reverse("lending:return", args=[open_loan.pk]),
        {"return_date": "2026-09-15", "condition": "damaged"},
    )
    event = open_loan.logs.get()
    assert event.action == LoanLog.Action.RETURNED
    assert event.changes == {"return_date": [None, "2026-09-15"]}
    assert event.reason == "Com defeito"


@pytest.mark.django_db
def test_correction_logs_old_and_new_dates_with_its_reason(client, attendant, returned_loan):
    edit(client, returned_loan, return_date="2026-09-12")
    event = returned_loan.logs.get()
    assert event.action == LoanLog.Action.EDITED
    assert event.changes == {"return_date": ["2026-09-15", "2026-09-12"]}
    assert event.reason == "Erro de digitação"


@pytest.mark.django_db
def test_undoing_a_return_is_logged_as_reopened(client, attendant, returned_loan):
    edit(client, returned_loan, return_date="")
    assert returned_loan.logs.get().action == LoanLog.Action.REOPENED


@pytest.mark.django_db
def test_correction_needs_a_reason(client, attendant, returned_loan):
    response = edit(client, returned_loan, return_date="2026-09-12", reason="")
    assert "reason" in response.context["form"].errors
    returned_loan.refresh_from_db()
    assert returned_loan.return_date == date(2026, 9, 15)


@pytest.mark.django_db
def test_saving_a_correction_without_changes_logs_nothing(client, attendant, returned_loan):
    edit(client, returned_loan, return_date="2026-09-15")
    assert not returned_loan.logs.exists()


@pytest.mark.django_db
def test_failed_return_logs_nothing(client, attendant, open_loan):
    client.post(reverse("lending:return", args=[open_loan.pk]), {"return_date": "2999-01-01"})
    assert not open_loan.logs.exists()


@pytest.mark.django_db
def test_loan_log_lives_only_under_registros(client, attendant, returned_loan):
    edit(client, returned_loan, return_date="2026-09-12", reason="Motivo secreto")
    loan_page = client.get(reverse("lending:loan", args=[returned_loan.pk])).content.decode()
    assert "Motivo secreto" not in loan_page
    assert client.get(reverse("lending:loan_log")).status_code == 403
    client.force_login(User.objects.create_superuser("chefe", password="x"))
    events = client.get(reverse("lending:loan_log"), {"q": "Pessoa Teste"}).context["events"]
    assert [e.reason for e in events] == ["Motivo secreto"]


# Rule: a return "com defeito" or "extraviado" sets the equipment status, logged.


@pytest.mark.django_db
def test_return_as_lost_marks_equipment_lost_and_logs_it(client, attendant, open_loan):
    client.post(
        reverse("lending:return", args=[open_loan.pk]),
        {"return_date": "2026-09-15", "condition": "lost"},
    )
    equipment = open_loan.equipment
    equipment.refresh_from_db()
    change = equipment.status_logs.get()
    assert equipment.status == Equipment.Status.LOST
    assert (change.from_status, change.changed_by) == (Equipment.Status.ACTIVE, attendant)
    assert change.effective_on == date(2026, 9, 15)


@pytest.mark.django_db
def test_returning_already_damaged_equipment_with_defect_logs_no_status_change(
    client, attendant, open_loan
):
    open_loan.equipment.status = Equipment.Status.DAMAGED
    open_loan.equipment.save()
    response = client.post(
        reverse("lending:return", args=[open_loan.pk]),
        {"return_date": "2026-09-15", "condition": "damaged"},
    )
    assert response.status_code == 302
    assert not open_loan.equipment.status_logs.exists()


@pytest.mark.django_db
def test_return_dated_before_the_last_status_change_is_rejected_whole(client, attendant, open_loan):
    open_loan.equipment.status_logs.create(
        from_status="damaged",
        to_status="active",
        effective_on=date(2026, 9, 20),
        reason="Consertado",
        changed_by=attendant,
    )
    response = client.post(
        reverse("lending:return", args=[open_loan.pk]),
        {"return_date": "2026-09-15", "condition": "lost"},
    )
    assert response.context["return_form"].non_field_errors()
    open_loan.refresh_from_db()
    assert open_loan.return_date is None
    assert not open_loan.logs.exists()


# --- People overview -----------------------------------------------------------------------


@pytest.fixture
def roles_people(returned_loan):
    """Borrower: one returned loan + one open loan. Guarantor: vouched once. Idle: no loans."""
    borrower = returned_loan.person
    guarantor = Person.objects.create(
        name="Solidária Teste", cpf="00000000088", birth_date=date(1960, 1, 1), phone="0"
    )
    idle = Person.objects.create(
        name="Sem Empréstimo", cpf="00000000077", birth_date=date(1970, 1, 1), phone="0"
    )
    second = Equipment.objects.create(
        name="Andador",
        category=Category.objects.create(name="Andador", code="AND"),
        warehouse=returned_loan.equipment.warehouse,
    )
    Loan.objects.create(
        equipment=second, person=borrower, guarantor=guarantor, lent_date=date(2026, 9, 20)
    )
    return borrower, guarantor, idle


def listed(client, **params):
    return {p.name: p for p in client.get(reverse("lending:people"), params).context["people"]}


@pytest.mark.django_db
def test_counts_include_returned_loans_and_keep_roles_apart(client, attendant, roles_people):
    borrower, guarantor, _ = roles_people
    people = listed(client)
    assert (people[borrower.name].borrower_count, people[borrower.name].guarantor_count) == (2, 0)
    assert (people[guarantor.name].borrower_count, people[guarantor.name].guarantor_count) == (0, 1)


@pytest.mark.django_db
def test_person_without_loans_shows_only_under_todas(client, attendant, roles_people):
    _, _, idle = roles_people
    assert idle.name in listed(client)
    assert idle.name not in listed(client, papel="beneficiario")
    assert idle.name not in listed(client, papel="solidario")


@pytest.mark.django_db
def test_role_tabs_list_only_people_in_that_role(client, attendant, roles_people):
    borrower, guarantor, _ = roles_people
    assert set(listed(client, papel="beneficiario")) == {borrower.name}
    assert set(listed(client, papel="solidario")) == {guarantor.name}


@pytest.mark.django_db
def test_person_in_both_roles_shows_on_both_tabs(client, attendant, roles_people):
    borrower, guarantor, _ = roles_people
    Loan.objects.filter(guarantor=guarantor).update(guarantor=None)
    loan = Loan.objects.filter(person=borrower, return_date__isnull=False).get()
    Loan.objects.filter(pk=loan.pk).update(person=guarantor, guarantor=borrower)
    assert borrower.name in listed(client, papel="beneficiario")
    assert borrower.name in listed(client, papel="solidario")


@pytest.mark.django_db
def test_why_listed_shows_open_loans_before_the_latest_returned(client, attendant, roles_people):
    borrower, _, _ = roles_people
    # The open loan is older than the returned one, so "latest" alone would pick the wrong row.
    Loan.objects.filter(return_date__isnull=True).update(lent_date=date(2026, 8, 1))
    why = listed(client, papel="beneficiario")[borrower.name].why
    assert [(loan.lent_date, loan.return_date) for loan in why] == [(date(2026, 8, 1), None)]
    Loan.objects.filter(return_date__isnull=True).update(return_date=date(2026, 8, 20))
    why = listed(client, papel="beneficiario")[borrower.name].why
    assert [loan.lent_date for loan in why] == [date(2026, 9, 1)]


@pytest.mark.django_db
def test_todas_lists_people_alphabetically_and_search_keeps_the_tab(
    client, attendant, roles_people
):
    Person.objects.create(  # created last, sorts first
        name="Ana Última", cpf="00000000066", birth_date=date(1980, 1, 1), phone="0"
    )
    names = list(listed(client))
    assert names[0] == "Ana Última" and names == sorted(names)
    page = client.get(reverse("lending:people"), {"papel": "solidario"}).content.decode()
    assert '<input type="hidden" name="papel" value="solidario">' in page


# --- Signed contract ------------------------------------------------------------------------

PDF = b"%PDF-1.4\n% contrato de teste\n"


@pytest.fixture
def private_media(settings, tmp_path):
    settings.PRIVATE_MEDIA_ROOT = tmp_path
    return tmp_path


def upload_contract(client, loan, content=PDF, name="contrato.pdf"):
    return client.post(
        reverse("lending:contract", args=[loan.pk]),
        {"contract": SimpleUploadedFile(name, content, content_type="application/pdf")},
    )


# Rule: staff attach the signed PDF to a loan; replacing it overwrites the file; both are logged.


@pytest.mark.django_db
def test_staff_attaches_a_contract_and_downloads_it(client, attendant, open_loan, private_media):
    upload_contract(client, open_loan)
    open_loan.refresh_from_db()
    assert open_loan.logs.get().action == LoanLog.Action.CONTRACT_ADDED
    response = client.get(reverse("lending:contract_download", args=[open_loan.pk]))
    assert b"".join(response.streaming_content) == PDF


@pytest.mark.django_db
def test_replacing_a_contract_overwrites_the_file_and_is_logged(
    client, attendant, open_loan, private_media
):
    upload_contract(client, open_loan)
    upload_contract(client, open_loan, content=PDF + b"v2")
    open_loan.refresh_from_db()
    files = list(private_media.rglob("*.pdf"))
    assert len(files) == 1 and files[0].read_bytes() == PDF + b"v2"
    assert [log.action for log in open_loan.logs.all()] == [
        LoanLog.Action.CONTRACT_REPLACED,
        LoanLog.Action.CONTRACT_ADDED,
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "content, name",
    [(b"texto qualquer", "contrato.pdf"), (PDF, "contrato.docx")],
)
def test_contract_must_be_a_pdf(client, attendant, open_loan, private_media, content, name):
    upload_contract(client, open_loan, content=content, name=name)
    open_loan.refresh_from_db()
    assert not open_loan.contract


@pytest.mark.django_db
def test_contract_size_limit_is_inclusive(client, attendant, open_loan, private_media, monkeypatch):
    monkeypatch.setattr("hospitalequip.lending.forms.CONTRACT_MAX_MB", 1)
    limit = 1024 * 1024
    upload_contract(client, open_loan, content=PDF + b"x" * (limit - len(PDF) + 1))
    open_loan.refresh_from_db()
    assert not open_loan.contract
    upload_contract(client, open_loan, content=PDF + b"x" * (limit - len(PDF)))
    open_loan.refresh_from_db()
    assert open_loan.contract


@pytest.mark.django_db
def test_contract_is_never_public(client, open_loan, private_media, settings):
    open_loan.contract.save("c.pdf", SimpleUploadedFile("c.pdf", PDF))
    url = reverse("lending:contract_download", args=[open_loan.pk])
    assert client.get(url).status_code == 302  # anonymous -> login
    client.force_login(User.objects.create_user("visitante", password="x"))
    assert client.get(url).status_code == 403
    assert not str(private_media).startswith(str(settings.MEDIA_ROOT))
    with pytest.raises(ValueError):
        _ = open_loan.contract.url


@pytest.mark.django_db
def test_pending_contract_filter_lists_only_loans_without_one(
    client, attendant, open_loan, returned_loan, private_media
):
    second = Loan.objects.create(
        equipment=open_loan.equipment, person=open_loan.person, lent_date=date(2026, 9, 20)
    )
    upload_contract(client, second)
    loans = client.get(reverse("lending:loans"), {"situacao": "sem-contrato"}).context["loans"]
    assert [loan.pk for loan in loans] == [returned_loan.pk]

import calendar
from datetime import date
from urllib.parse import urlencode

from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Prefetch, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from hospitalequip.inventory.services import (
    StatusChangeError,
    change_status,
    get_lendable_equipment,
)
from hospitalequip.staff.access import manager_required, staff_required

from .forms import ContractForm, LoanEditForm, LoanForm, PersonForm, ReturnForm
from .models import LOAN_TERM_MONTHS, Loan, LoanLog, Person
from .validators import only_digits


def search_people(query):
    """Name contains the query, or CPF starts with its digits."""
    match = Q(name__icontains=query)
    if digits := only_digits(query):
        match |= Q(cpf__startswith=digits)
    return Person.objects.filter(match)


def add_months(day, months):
    """Same day N months later, clamped to the month's last day (31 Aug + 6 = 28 Feb)."""
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return day.replace(
        year=year, month=month, day=min(day.day, calendar.monthrange(year, month)[1])
    )


# Tab key -> (label, the person's loans in that role as a related name, its count annotation).
PERSON_ROLES = {
    "beneficiario": ("Beneficiários", "loans", "borrower_count"),
    "solidario": ("Solidários", "guaranteed_loans", "guarantor_count"),
}


def why_listed(person, role):
    """Why the person shows on a role tab: their open loans in that role, else the latest one."""
    loans = sorted(
        getattr(person, PERSON_ROLES[role][1]).all(), key=lambda loan: loan.lent_date, reverse=True
    )
    open_loans = [loan for loan in loans if loan.return_date is None]
    return open_loans or loans[:1]


@staff_required
def person_list(request):
    """People with how often each was Beneficiário and Solidário, counted from all loans."""
    query = request.GET.get("q", "").strip()
    role = request.GET.get("papel", "")
    people = (
        (search_people(query) if query else Person.objects.all())
        .annotate(
            borrower_count=Count("loans", distinct=True),
            guarantor_count=Count("guaranteed_loans", distinct=True),
        )
        .order_by("name")  # aggregation drops Meta.ordering
    )
    if role in PERSON_ROLES:
        _, related, count = PERSON_ROLES[role]
        people = (
            people.filter(**{f"{count}__gt": 0})
            .annotate(
                has_open=Count(related, filter=Q(**{f"{related}__return_date__isnull": True})),
                latest=Max(f"{related}__lent_date"),
            )
            .order_by("-has_open", "-latest", "name")
            .prefetch_related(
                Prefetch(
                    related,
                    queryset=Loan.objects.select_related("equipment", "person", "guarantor"),
                )
            )
        )
        for person in people:
            person.why = why_listed(person, role)
    else:
        role = ""
    tabs = [
        {
            "label": label,
            "active": key == role,
            "query": urlencode({k: v for k, v in {"papel": key, "q": query}.items() if v}),
        }
        for key, label in [("", "Todas"), *((k, v[0]) for k, v in PERSON_ROLES.items())]
    ]
    context = {"people": people, "query": query, "role": role, "tabs": tabs}
    return render(request, "lending/person_list.html", context)


@staff_required
def person_detail(request, pk):
    person = get_object_or_404(Person, pk=pk)
    loans = person.loans.select_related("equipment").order_by("-lent_date")
    return render(request, "lending/person_detail.html", {"person": person, "loans": loans})


@staff_required
def person_form(request, pk=None):
    person = get_object_or_404(Person, pk=pk) if pk else None
    form = PersonForm(request.POST or None, instance=person)
    if request.method == "POST" and form.is_valid():
        person = form.save()
        return redirect("lending:person", pk=person.pk)
    return render(request, "lending/person_form.html", {"form": form, "person": person})


@staff_required
def person_picker(request):
    """HTMX fragment for one picker field: search results, the chosen person, or an empty box."""
    field = request.GET.get("campo", "person")
    context = {"field": field, "label": request.GET.get("rotulo", "")}
    if chosen := request.GET.get("id"):
        context["chosen"] = get_object_or_404(Person, pk=chosen)
    elif query := request.GET.get("q", "").strip():
        # Borrower and guarantor must differ, so the other box's choice is left out.
        other = request.GET.get("guarantor" if field == "person" else "person")
        people = search_people(query).exclude(pk=other) if other else search_people(query)
        context |= {"query": query, "results": people[:8]}
    return render(request, "lending/includes/person_picker.html", context)


@staff_required
def lend(request, equipment_pk):
    equipment = get_lendable_equipment(equipment_pk)
    today = date.today()
    initial = {"lent_date": today, "due_date": add_months(today, LOAN_TERM_MONTHS)}
    form = LoanForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        form.instance.equipment_id = equipment.pk
        try:
            with transaction.atomic():
                loan = form.save()
                LoanLog.record(loan, LoanLog.Action.LENT, request.user)
        except IntegrityError:  # another attendant lent it a moment ago
            form.add_error(None, "Este equipamento acabou de ser emprestado.")
        else:
            return redirect("lending:loan", pk=loan.pk)
    return render(request, "lending/lend_form.html", {"form": form, "equipment": equipment})


@staff_required
def loan_detail(request, pk):
    loan = get_object_or_404(Loan.objects.select_related("equipment", "person", "guarantor"), pk=pk)
    return_form = ReturnForm(initial={"return_date": date.today()}, loan=loan)
    return render_loan(request, loan, return_form)


def render_loan(request, loan, return_form, contract_form=None):
    context = {
        "loan": loan,
        "return_form": return_form,
        "contract_form": contract_form or ContractForm(),
    }
    return render(request, "lending/loan_detail.html", context)


@staff_required
def loan_contract(request, pk):
    """Attach or replace the signed contract; the old file is overwritten and the action logged."""
    if request.method != "POST":
        return redirect("lending:loan", pk=pk)
    loan = get_object_or_404(Loan.objects.select_related("equipment", "person", "guarantor"), pk=pk)
    form = ContractForm(request.POST, request.FILES)
    if not form.is_valid():
        return_form = ReturnForm(initial={"return_date": date.today()}, loan=loan)
        return render_loan(request, loan, return_form, contract_form=form)
    action = LoanLog.Action.CONTRACT_REPLACED if loan.contract else LoanLog.Action.CONTRACT_ADDED
    with transaction.atomic():
        loan.contract.save("contrato.pdf", form.cleaned_data["contract"], save=False)
        loan.save(update_fields=["contract"])
        LoanLog.record(loan, action, request.user)
    return redirect("lending:loan", pk=pk)


@staff_required
def contract_download(request, pk):
    """The only way to read a contract: staff only, served from private storage."""
    loan = get_object_or_404(Loan.objects.select_related("equipment"), pk=pk)
    if not loan.contract:
        raise Http404
    return FileResponse(
        loan.contract.open("rb"),
        content_type="application/pdf",
        filename=f"contrato-{loan.equipment.tag}-{loan.pk}.pdf",
    )


RETURN_STATUS = {ReturnForm.DAMAGED: "damaged", ReturnForm.LOST: "lost"}


@staff_required
def return_loan(request, pk):
    """Close an open loan; "com defeito" or "extraviado" also sets the equipment status."""
    if request.method != "POST":
        return redirect("lending:loan", pk=pk)
    with transaction.atomic():
        loan = get_object_or_404(
            Loan.objects.select_for_update(of=("self",)).select_related(
                "equipment", "person", "guarantor"
            ),
            pk=pk,
            return_date__isnull=True,
        )
        form = ReturnForm(request.POST, loan=loan)
        if form.is_valid():
            condition = form.cleaned_data["condition"]
            label = dict(form.fields["condition"].choices)[condition]
            try:
                with transaction.atomic():
                    loan.return_date = form.cleaned_data["return_date"]
                    loan.save(update_fields=["return_date"])
                    LoanLog.record(
                        loan,
                        LoanLog.Action.RETURNED,
                        request.user,
                        old={"return_date": None},
                        reason=label,
                    )
                    if (
                        condition in RETURN_STATUS
                        and loan.equipment.status != RETURN_STATUS[condition]
                    ):
                        change_status(
                            loan.equipment_id,
                            RETURN_STATUS[condition],
                            by=request.user,
                            on=loan.return_date,
                            reason=f"Devolução {label.lower()} (empréstimo #{loan.pk})",
                        )
            except StatusChangeError as error:
                loan.return_date = None
                form.add_error(None, str(error))
            else:
                return redirect("lending:loan", pk=loan.pk)
    return render_loan(request, loan, form)


@staff_required
def loan_edit(request, pk):
    """Correct a loan's dates; an empty return date undoes the return."""
    with transaction.atomic():
        loans = Loan.objects.select_related("equipment", "person")
        if request.method == "POST":
            loans = loans.select_for_update(of=("self",))
        loan = get_object_or_404(loans, pk=pk)
        old = {"due_date": loan.due_date, "return_date": loan.return_date}
        form = LoanEditForm(request.POST or None, instance=loan)
        if request.method == "POST" and form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                    reopened = old["return_date"] and loan.return_date is None
                    action = LoanLog.Action.REOPENED if reopened else LoanLog.Action.EDITED
                    if any(getattr(loan, field) != value for field, value in old.items()):
                        LoanLog.record(
                            loan, action, request.user, old=old, reason=form.cleaned_data["reason"]
                        )
            except IntegrityError:  # lent again between the check and the save
                form.add_error("return_date", "O equipamento acabou de ser emprestado de novo.")
            else:
                return redirect("lending:loan", pk=loan.pk)
    return render(request, "lending/loan_form.html", {"form": form, "loan": loan})


def overdue_loans():
    """Same rule as Loan.is_overdue, as a query."""
    return Q(return_date__isnull=True, due_date__lt=date.today())


LOAN_FILTERS = {
    "abertos": ("Em aberto", lambda: Q(return_date__isnull=True)),
    "atrasados": ("Atrasados", overdue_loans),
    "devolvidos": ("Devolvidos", lambda: Q(return_date__isnull=False)),
    "sem-contrato": ("Contrato pendente", lambda: Q(contract="")),
}


@staff_required
def loan_list(request):
    """Global loan history, filtered by status and by equipment name or tag."""
    status = request.GET.get("situacao", "")
    equipment = request.GET.get("equipamento", "").strip()
    loans = Loan.objects.select_related("equipment", "person").order_by("-lent_date", "-pk")
    if status in LOAN_FILTERS:
        loans = loans.filter(LOAN_FILTERS[status][1]())
    if equipment:
        loans = loans.filter(
            Q(equipment__name__icontains=equipment) | Q(equipment__tag__icontains=equipment)
        )
    context = {
        "loans": loans,
        "status": status,
        "equipment": equipment,
        "chips": [  # tapping the active chip again clears it
            {
                "label": label,
                "active": key == status,
                "query": urlencode(
                    {
                        k: v
                        for k, v in {
                            "situacao": "" if key == status else key,
                            "equipamento": equipment,
                        }.items()
                        if v
                    }
                ),
            }
            for key, (label, _) in LOAN_FILTERS.items()
        ],
    }
    return render(request, "lending/loan_list.html", context)


LOG_LIMIT = 200


@manager_required
def loan_log(request):
    """Registros, Empréstimos tab: every loan action, newest first, searchable by item or person."""
    query = request.GET.get("q", "").strip()
    events = LoanLog.objects.select_related("loan__equipment", "loan__person", "changed_by")
    if query:
        events = events.filter(
            Q(loan__equipment__tag__icontains=query)
            | Q(loan__equipment__name__icontains=query)
            | Q(loan__person__name__icontains=query)
        )
    context = {"events": events[:LOG_LIMIT], "query": query, "tab": "loans"}
    return render(request, "lending/loan_log.html", context)

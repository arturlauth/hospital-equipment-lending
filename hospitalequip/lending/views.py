import calendar
from datetime import date
from urllib.parse import urlencode

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from hospitalequip.inventory.services import get_lendable_equipment, mark_damaged
from hospitalequip.staff.access import staff_required

from .forms import LoanEditForm, LoanForm, PersonForm, ReturnForm
from .models import LOAN_TERM_MONTHS, Loan, Person
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


@staff_required
def person_list(request):
    query = request.GET.get("q", "").strip()
    people = search_people(query) if query else Person.objects.all()
    return render(request, "lending/person_list.html", {"people": people, "query": query})


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
        except IntegrityError:  # another attendant lent it a moment ago
            form.add_error(None, "Este equipamento acabou de ser emprestado.")
        else:
            return redirect("lending:loan", pk=loan.pk)
    return render(request, "lending/lend_form.html", {"form": form, "equipment": equipment})


@staff_required
def loan_detail(request, pk):
    loan = get_object_or_404(Loan.objects.select_related("equipment", "person", "guarantor"), pk=pk)
    return_form = ReturnForm(initial={"return_date": date.today()}, loan=loan)
    return render(request, "lending/loan_detail.html", {"loan": loan, "return_form": return_form})


@staff_required
def return_loan(request, pk):
    """Close an open loan; "voltou com defeito" also takes the equipment out of lending."""
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
            loan.return_date = form.cleaned_data["return_date"]
            loan.save(update_fields=["return_date"])
            if form.cleaned_data["damaged"]:
                mark_damaged(loan.equipment_id)
            return redirect("lending:loan", pk=loan.pk)
    return render(request, "lending/loan_detail.html", {"loan": loan, "return_form": form})


@staff_required
def loan_edit(request, pk):
    """Correct a loan's dates; an empty return date undoes the return."""
    with transaction.atomic():
        loans = Loan.objects.select_related("equipment", "person")
        if request.method == "POST":
            loans = loans.select_for_update(of=("self",))
        loan = get_object_or_404(loans, pk=pk)
        form = LoanEditForm(request.POST or None, instance=loan)
        if request.method == "POST" and form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
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

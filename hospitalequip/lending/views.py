from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from hospitalequip.staff.access import staff_required

from .forms import PersonForm
from .models import Person
from .validators import only_digits


@staff_required
def person_list(request):
    query = request.GET.get("q", "").strip()
    people = Person.objects.all()
    if query:
        match = Q(name__icontains=query)
        if digits := only_digits(query):
            match |= Q(cpf__startswith=digits)
        people = people.filter(match)
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

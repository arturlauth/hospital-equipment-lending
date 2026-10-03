from django.shortcuts import render

from hospitalequip.lending.services import equipment_ids_on_loan

from .models import Equipment


def catalog(request):
    equipment_list = (
        Equipment.objects.select_related("category")
        .exclude(id__in=equipment_ids_on_loan())
        .order_by("category__name", "name")
    )
    return render(request, "inventory/catalog.html", {"equipment_list": equipment_list})

from django.shortcuts import render

from hospitalequip.lending.services import equipment_ids_on_loan

from .models import Equipment


def catalog(request):
    equipment_list = Equipment.objects.exclude(id__in=equipment_ids_on_loan()).order_by(
        "category", "name"
    )
    return render(request, "inventory/catalog.html", {"equipment_list": equipment_list})

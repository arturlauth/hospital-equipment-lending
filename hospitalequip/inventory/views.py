from django.shortcuts import get_object_or_404, render

from .models import Equipment


def catalog(request):
    equipment_list = (
        Equipment.objects.public()
        .select_related("category")
        .prefetch_related("images")
        .order_by("category__name", "name")
    )
    return render(request, "inventory/catalog.html", {"equipment_list": equipment_list})


def equipment_detail(request, pk):
    equipment = get_object_or_404(
        Equipment.objects.public()
        .select_related("category", "warehouse")
        .prefetch_related("images", "specs"),
        pk=pk,
    )
    return render(request, "inventory/equipment_detail.html", {"equipment": equipment})

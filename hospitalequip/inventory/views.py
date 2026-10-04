from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from hospitalequip.staff.access import is_staff_member

from .models import Equipment


def catalog(request):
    only_available = request.GET.get("disponiveis") == "1"
    equipment_list = (
        Equipment.objects.public()
        .select_related("category")
        .prefetch_related("images")
        .order_by("category__name", "name")
    )
    if only_available:
        equipment_list = equipment_list.filter(Q(status=Equipment.Status.ACTIVE), open_loans=0)
    return render(
        request,
        "inventory/catalog.html",
        {"equipment_list": equipment_list, "only_available": only_available},
    )


def equipment_detail(request, pk):
    equipment = get_object_or_404(
        Equipment.objects.public()
        .select_related("category", "warehouse")
        .prefetch_related("images", "specs"),
        pk=pk,
    )
    context = {"equipment": equipment, "staff": is_staff_member(request.user)}
    if context["staff"]:
        loans = list(equipment.loans.select_related("person").order_by("-lent_date", "-pk"))
        context["loans"] = loans
        context["open_loan"] = next((loan for loan in loans if loan.return_date is None), None)
    return render(request, "inventory/equipment_detail.html", context)

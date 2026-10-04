from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from hospitalequip.staff.access import is_staff_member, manager_required, staff_required

from .forms import StatusChangeForm
from .models import Equipment, EquipmentStatusLog
from .services import StatusChangeError, allowed_statuses, change_status


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


def equipment_detail(request, pk, status_form=None):
    """Public page; staff also see loans and status actions, even for hidden items."""
    staff = is_staff_member(request.user)
    equipment_list = Equipment.objects.with_availability() if staff else Equipment.objects.public()
    equipment = get_object_or_404(
        equipment_list.select_related("category", "warehouse").prefetch_related("images", "specs"),
        pk=pk,
    )
    context = {"equipment": equipment, "staff": staff}
    if staff:
        loans = list(equipment.loans.select_related("person").order_by("-lent_date", "-pk"))
        context["loans"] = loans
        context["open_loan"] = next((loan for loan in loans if loan.return_date is None), None)
        allowed = allowed_statuses(equipment, request.user)
        context["status_form"] = status_form or (allowed and StatusChangeForm(allowed=allowed))
    return render(request, "inventory/equipment_detail.html", context)


@staff_required
def equipment_status(request, pk):
    """Apply a status action from the equipment page."""
    if request.method != "POST":
        return redirect("inventory:equipment", pk=pk)
    equipment = get_object_or_404(Equipment, pk=pk)
    form = StatusChangeForm(request.POST, allowed=allowed_statuses(equipment, request.user))
    if form.is_valid():
        try:
            change_status(
                equipment.pk,
                form.cleaned_data["to_status"],
                by=request.user,
                on=form.cleaned_data["effective_on"],
                reason=form.cleaned_data["reason"],
            )
        except StatusChangeError as error:
            form.add_error(None, str(error))
        else:
            return redirect("inventory:equipment", pk=pk)
    return equipment_detail(request, pk, status_form=form)


LOG_LIMIT = 200


@manager_required
def status_log(request):
    """Registros, Situação tab: every status change, newest first, searchable by item."""
    query = request.GET.get("q", "").strip()
    changes = EquipmentStatusLog.objects.select_related("equipment", "changed_by")
    if query:
        changes = changes.filter(
            Q(equipment__tag__icontains=query) | Q(equipment__name__icontains=query)
        )
    context = {"changes": changes[:LOG_LIMIT], "query": query, "tab": "status"}
    return render(request, "inventory/status_log.html", context)

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Max, Q
from django.shortcuts import get_object_or_404, redirect, render

from hospitalequip.staff.access import is_staff_member, manager_required, staff_required

from .forms import EquipmentForm, ImageFormSet, NewImagesForm, SpecFormSet, StatusChangeForm
from .models import Category, Equipment, EquipmentImage, EquipmentStatusLog, Warehouse
from .services import StatusChangeError, allowed_statuses, change_status

PAGE_SIZE = 24  # 4 per row on desktop, 6 rows


def filter_groups(request, groups):
    """Left-column filter groups as data: (param, label, [(value, label)]) plus what is chosen."""
    return [
        {
            "param": param,
            "label": label,
            "options": options,
            "selected": request.GET.get(param, ""),
        }
        for param, label, options in groups
    ]


def place_filters():
    return [
        ("categoria", "Categoria", [(str(c.pk), c.name) for c in Category.objects.all()]),
        ("deposito", "Depósito", [(str(w.pk), w.name) for w in Warehouse.objects.order_by("name")]),
    ]


def apply_common_filters(request, equipment_list, search_fields):
    """Search box and the category/warehouse filters shared by the public and staff listings."""
    if query := request.GET.get("q", "").strip():
        match = Q()
        for field in search_fields:
            match |= Q(**{f"{field}__icontains": query})
        equipment_list = equipment_list.filter(match)
    if category := request.GET.get("categoria", "").strip():
        equipment_list = equipment_list.filter(category_id=category if category.isdigit() else 0)
    if warehouse := request.GET.get("deposito", "").strip():
        equipment_list = equipment_list.filter(warehouse_id=warehouse if warehouse.isdigit() else 0)
    return equipment_list


def render_listing(request, template, equipment_list, groups, extra=None):
    page = Paginator(equipment_list, PAGE_SIZE).get_page(request.GET.get("pagina"))
    context = {
        "page": page,
        "equipment_list": page.object_list,
        "filters": filter_groups(request, groups),
        "query": request.GET.get("q", "").strip(),
        "filtered": any(request.GET.get(k) for k in ["q", *(g[0] for g in groups)]),
    }
    return render(request, template, context | (extra or {}))


def catalog(request):
    """Public catalog: search on top, filters on the left, a paged feed of cards."""
    equipment_list = (
        Equipment.objects.public()
        .select_related("category")
        .prefetch_related("images")
        .order_by("category__name", "name", "pk")
    )
    equipment_list = apply_common_filters(request, equipment_list, ["name", "category__name"])
    if request.GET.get("disponiveis") == "1":
        equipment_list = equipment_list.filter(status=Equipment.Status.ACTIVE, open_loans=0)
    groups = [*place_filters(), ("disponiveis", "Disponibilidade", [("1", "Só disponíveis")])]
    return render_listing(request, "inventory/catalog.html", equipment_list, groups)


LENT_FILTERS = {"emprestado": Q(open_loans__gt=0), "livre": Q(open_loans=0)}


@staff_required
def staff_equipment(request):
    """Staff ("back-end") equipment list: every item incl. hidden ones; Baixado only when chosen."""
    equipment_list = (
        Equipment.objects.with_availability()
        .select_related("category", "warehouse")
        .prefetch_related("images")
        .order_by("category__name", "name", "pk")
    )
    equipment_list = apply_common_filters(request, equipment_list, ["name", "tag"])
    status = request.GET.get("situacao", "")
    if status in Equipment.Status.values:
        equipment_list = equipment_list.filter(status=status)
    else:
        equipment_list = equipment_list.exclude(status=Equipment.Status.WRITTEN_OFF)
    if lent := LENT_FILTERS.get(request.GET.get("emprestimo", "")):
        equipment_list = equipment_list.filter(lent)
    groups = [
        ("situacao", "Situação", list(Equipment.Status.choices)),
        ("emprestimo", "Empréstimo", [("emprestado", "Emprestado"), ("livre", "Livre")]),
        *place_filters(),
    ]
    return render_listing(request, "inventory/staff_equipment.html", equipment_list, groups)


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


@staff_required
def equipment_form(request, pk=None):
    """Create or edit an item with its photos and spec rows; any staff member may do both."""
    equipment = get_object_or_404(Equipment, pk=pk) if pk else Equipment()
    data, files = (request.POST, request.FILES) if request.method == "POST" else (None, None)
    form = EquipmentForm(data, instance=equipment)
    specs = SpecFormSet(data, instance=equipment, prefix="specs")
    images = ImageFormSet(data, instance=equipment, prefix="images")
    new_images = NewImagesForm(data, files)
    forms_ok = all(f.is_valid() for f in (form, specs, images, new_images))
    if request.method == "POST" and forms_ok:
        with transaction.atomic():
            equipment = form.save()
            save_specs(specs, equipment)
            images.instance = equipment
            images.save()
            next_order = (equipment.images.aggregate(m=Max("order"))["m"] or 0) + 1
            for offset, upload in enumerate(new_images.cleaned_data["images"]):
                EquipmentImage.objects.create(
                    equipment=equipment, image=upload, order=next_order + offset
                )
        return redirect("inventory:equipment", pk=equipment.pk)
    context = {
        "form": form,
        "specs": specs,
        "images": images,
        "new_images": new_images,
        "equipment": equipment if pk else None,
    }
    return render(request, "inventory/equipment_form.html", context)


def save_specs(specs, equipment):
    """Save spec rows in the order they appear on the form; removed and untouched blank rows go."""
    position = 0
    for spec_form in specs.forms:
        spec = spec_form.instance
        if spec_form in specs.deleted_forms:
            if spec.pk:
                spec.delete()
            continue
        if not spec.pk and not spec_form.has_changed():
            continue
        spec = spec_form.save(commit=False)
        spec.equipment, spec.order = equipment, position
        spec.save()
        position += 1


@staff_required
def spec_row(request):
    """One blank spec row for the HTMX 'Adicionar linha' button; `i` is its formset index."""
    index = int(request.GET.get("i", 0))
    row = SpecFormSet(prefix="specs").empty_form
    row.prefix = f"specs-{index}"
    return render(request, "inventory/includes/spec_row.html", {"row": row})

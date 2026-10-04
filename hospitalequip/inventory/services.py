from datetime import date

from django.db import transaction
from django.shortcuts import get_object_or_404

from hospitalequip.staff.access import is_manager

from .models import Equipment, EquipmentStatusLog

Status = Equipment.Status


class StatusChangeError(Exception):
    """A status change that the business rules do not allow; the message is shown to staff."""


def get_lendable_equipment(pk):
    """Active equipment with no open loan, or 404. Photos are not required: staff lend anything."""
    return get_object_or_404(
        Equipment.objects.with_availability().select_related("category"),
        pk=pk,
        status=Status.ACTIVE,
        open_loans=0,
    )


def allowed_statuses(equipment, user):
    """Statuses this user may set now. Write-off is Gestor only and never while a loan is open.

    Written off is final: a mistaken write-off is fixed by the Gestor in the admin.
    """
    if equipment.status == Status.WRITTEN_OFF:
        return []
    allowed = [s for s in (Status.ACTIVE, Status.DAMAGED, Status.LOST) if s != equipment.status]
    if is_manager(user) and not equipment.loans.filter(return_date__isnull=True).exists():
        allowed.append(Status.WRITTEN_OFF)
    return allowed


def change_status(equipment_id, to_status, *, by, on, reason):
    """Set the status and log who, when, from/to and why. The only writer of `Equipment.status`.

    Raises StatusChangeError when a rule forbids it. Call inside the caller's transaction.
    """
    with transaction.atomic():
        equipment = Equipment.objects.select_for_update().get(pk=equipment_id)
        if to_status not in allowed_statuses(equipment, by):
            if to_status == Status.WRITTEN_OFF and equipment.status != Status.WRITTEN_OFF:
                if not is_manager(by):
                    raise StatusChangeError("Só o Gestor pode dar baixa.")
                raise StatusChangeError("Não dá para dar baixa com empréstimo em aberto.")
            raise StatusChangeError("Esta mudança de situação não é permitida.")
        if on > date.today():
            raise StatusChangeError("A data não pode estar no futuro.")
        last = equipment.status_logs.first()
        if last and on < last.effective_on:
            raise StatusChangeError(
                f"A data não pode ser antes da última mudança ({last.effective_on:%d/%m/%Y})."
            )
        if not reason.strip():
            raise StatusChangeError("Informe o motivo.")
        EquipmentStatusLog.objects.create(
            equipment=equipment,
            from_status=equipment.status,
            to_status=to_status,
            effective_on=on,
            reason=reason.strip(),
            changed_by=by,
        )
        equipment.status = to_status
        equipment.save(update_fields=["status"])
        return equipment

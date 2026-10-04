from django.shortcuts import get_object_or_404

from .models import Equipment


def get_lendable_equipment(pk):
    """Active equipment with no open loan, or 404. Photos are not required: staff lend anything."""
    return get_object_or_404(
        Equipment.objects.with_availability().select_related("category"),
        pk=pk,
        status=Equipment.Status.ACTIVE,
        open_loans=0,
    )

from django.db.models import QuerySet

from .models import Loan


def equipment_ids_on_loan() -> QuerySet:
    """IDs of equipment currently lent out (an open loan has no return date)."""
    return Loan.objects.filter(return_date__isnull=True).values("equipment_id")

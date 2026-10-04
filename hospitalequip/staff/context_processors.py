from .access import is_manager
from .menu import menu_items


def roles(request):
    """`is_manager` and the staff menu for the layout; Gestor-only items show only to the Gestor."""
    user = request.user
    return {
        "is_manager": user.is_authenticated and is_manager(user),
        "staff_menu": menu_items(user),
    }

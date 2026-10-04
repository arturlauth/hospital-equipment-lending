from .access import is_manager


def roles(request):
    """`is_manager` for the layout, so the Registros menu shows only to the Gestor."""
    return {"is_manager": request.user.is_authenticated and is_manager(request.user)}

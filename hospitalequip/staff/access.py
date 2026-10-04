from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from . import roles


def is_staff_member(user):
    """Belongs to a staff role. Superusers (the Gestor's admin account) always pass."""
    return user.is_superuser or user.groups.filter(name__in=roles.ALL).exists()


def staff_required(view):
    """Logged in and in a staff role; anonymous goes to login, anyone else gets 403."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not is_staff_member(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper

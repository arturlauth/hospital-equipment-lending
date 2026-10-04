from django.shortcuts import render

from .access import staff_required


@staff_required
def home(request):
    """Staff landing page after login; placeholder until the lending pages exist."""
    return render(request, "staff/home.html")

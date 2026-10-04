from django.shortcuts import render

from .access import staff_required


@staff_required
def home(request):
    """Staff hub after login: the same destinations as the header menu, as cards."""
    return render(request, "staff/home.html")

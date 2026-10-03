from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def home(request):
    """Staff landing page after login; placeholder until the lending pages exist."""
    return render(request, "staff/home.html")

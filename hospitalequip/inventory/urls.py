from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("equipamento/<int:pk>/", views.equipment_detail, name="equipment"),
]

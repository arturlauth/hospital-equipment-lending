from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("equipamento/<int:pk>/", views.equipment_detail, name="equipment"),
    path("equipamento/<int:pk>/situacao/", views.equipment_status, name="equipment_status"),
    path("equipe/registros/situacao/", views.status_log, name="status_log"),
]

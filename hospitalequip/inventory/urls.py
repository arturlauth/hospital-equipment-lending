from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("equipamento/<int:pk>/", views.equipment_detail, name="equipment"),
    path("equipamento/<int:pk>/situacao/", views.equipment_status, name="equipment_status"),
    path("equipe/equipamentos/", views.staff_equipment, name="staff_equipment"),
    path("equipe/equipamentos/novo/", views.equipment_form, name="equipment_new"),
    path("equipe/equipamentos/<int:pk>/editar/", views.equipment_form, name="equipment_edit"),
    path("equipe/equipamentos/linha-especificacao/", views.spec_row, name="spec_row"),
    path("equipe/registros/situacao/", views.status_log, name="status_log"),
]

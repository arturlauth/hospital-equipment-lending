from django.urls import path

from . import views

app_name = "lending"

urlpatterns = [
    path("pessoas/", views.person_list, name="people"),
    path("pessoas/nova/", views.person_form, name="person_new"),
    path("pessoas/<int:pk>/", views.person_detail, name="person"),
    path("pessoas/<int:pk>/editar/", views.person_form, name="person_edit"),
]

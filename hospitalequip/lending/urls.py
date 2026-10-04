from django.urls import path

from . import views

app_name = "lending"

urlpatterns = [
    path("pessoas/", views.person_list, name="people"),
    path("pessoas/nova/", views.person_form, name="person_new"),
    path("pessoas/<int:pk>/", views.person_detail, name="person"),
    path("pessoas/<int:pk>/editar/", views.person_form, name="person_edit"),
    path("pessoas/escolher/", views.person_picker, name="person_picker"),
    path("emprestar/<int:equipment_pk>/", views.lend, name="lend"),
    path("emprestimos/<int:pk>/", views.loan_detail, name="loan"),
    path("emprestimos/<int:pk>/devolver/", views.return_loan, name="return"),
]

from django.contrib import admin

from .models import Loan, Person


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ["name", "cpf", "phone", "email"]
    search_fields = ["name", "cpf", "phone"]


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ["equipment", "person", "lent_date", "due_date", "return_date"]
    list_filter = ["return_date", "due_date"]
    search_fields = ["person__name", "equipment__name"]
    autocomplete_fields = ["equipment", "person"]

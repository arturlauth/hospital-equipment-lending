from django.contrib import admin

from .models import Equipment, Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ["name", "address"]
    search_fields = ["name"]


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "warehouse", "created_at"]
    list_filter = ["category", "warehouse"]
    search_fields = ["name", "description"]

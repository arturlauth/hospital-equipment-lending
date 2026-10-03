from django.contrib import admin

from .models import Category, Equipment, EquipmentImage, EquipmentSpec, Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ["name", "address"]
    search_fields = ["name"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "code"]
    search_fields = ["name", "code"]


class EquipmentImageInline(admin.TabularInline):
    model = EquipmentImage
    extra = 3


class EquipmentSpecInline(admin.TabularInline):
    model = EquipmentSpec
    extra = 1


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ["tag", "name", "category", "warehouse", "status"]
    list_filter = ["category", "warehouse", "status"]
    search_fields = ["tag", "name", "brand", "description"]
    readonly_fields = ["tag", "created_at"]
    inlines = [EquipmentImageInline, EquipmentSpecInline]

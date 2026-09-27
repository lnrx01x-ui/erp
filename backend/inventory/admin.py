from django.contrib import admin

from .models import StockMovement, Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "organization", "is_active")
    list_filter = ("organization", "is_active")
    search_fields = ("name", "code")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "organization", "warehouse", "product", "direction", "quantity")
    list_filter = ("organization", "direction")
    readonly_fields = (
        "organization",
        "warehouse",
        "product",
        "direction",
        "quantity",
        "note",
        "actor",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

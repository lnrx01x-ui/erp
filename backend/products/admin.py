from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sku",
        "organization",
        "unit",
        "sale_price",
        "cost_price",
        "is_active",
    )
    list_filter = ("is_active", "unit", "organization")
    search_fields = ("name", "sku", "organization__name")
    readonly_fields = ("id", "created_at", "updated_at")

from django.contrib import admin

from audit.models import AuditEvent
from .models import Product, ProductCategory


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "created_at")
    list_filter = ("organization",)
    search_fields = ("name", "organization__name")
    readonly_fields = ("id", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        previous = type(obj).objects.filter(pk=obj.pk).first() if change else None
        super().save_model(request, obj, form, change)
        changes = (
            {
                "name": {
                    "old": previous.name,
                    "new": obj.name,
                }
            }
            if previous and previous.name != obj.name
            else {}
        )
        if previous is not None and not changes:
            return
        AuditEvent.objects.create(
            organization=obj.organization,
            actor=request.user,
            action="product_category.updated_by_platform_admin" if change else "product_category.created_by_platform_admin",
            entity_type="product_category",
            entity_id=str(obj.id),
            metadata={"name": obj.name, "changes": changes},
        )

    def delete_model(self, request, obj):
        AuditEvent.objects.create(
            organization=obj.organization,
            actor=request.user,
            action="product_category.deleted_by_platform_admin",
            entity_type="product_category",
            entity_id=str(obj.id),
            metadata={"name": obj.name},
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for category in queryset.select_related("organization").iterator():
            self.delete_model(request, category)


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

    def save_model(self, request, obj, form, change):
        previous = type(obj).objects.filter(pk=obj.pk).first() if change else None
        super().save_model(request, obj, form, change)
        fields = ("name", "sku", "unit", "sale_price", "cost_price", "is_active")
        old_values = {field: str(getattr(previous, field)) for field in fields} if previous else {}
        new_values = {field: str(getattr(obj, field)) for field in fields}
        changes = {
            key: {"old": old_values[key], "new": new_values[key]}
            for key in old_values
            if old_values[key] != new_values[key]
        }
        if previous is not None and not changes:
            return
        AuditEvent.objects.create(
            organization=obj.organization,
            actor=request.user,
            action="product.updated_by_platform_admin" if change else "product.created_by_platform_admin",
            entity_type="product",
            entity_id=str(obj.id),
            metadata={"name": obj.name, "sku": obj.sku, "changes": changes},
        )

    def delete_model(self, request, obj):
        AuditEvent.objects.create(
            organization=obj.organization,
            actor=request.user,
            action="product.deleted_by_platform_admin",
            entity_type="product",
            entity_id=str(obj.id),
            metadata={"name": obj.name, "sku": obj.sku},
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for product in queryset.select_related("organization").iterator():
            self.delete_model(request, product)

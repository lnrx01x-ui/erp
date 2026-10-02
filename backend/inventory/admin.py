from django.contrib import admin

from audit.models import AuditEvent
from .models import StockMovement, Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "organization", "is_active")
    list_filter = ("organization", "is_active")
    search_fields = ("name", "code")

    def save_model(self, request, obj, form, change):
        previous = type(obj).objects.filter(pk=obj.pk).first() if change else None
        super().save_model(request, obj, form, change)
        fields = ("name", "code", "address", "is_active")
        old_values = {field: getattr(previous, field) for field in fields} if previous else {}
        new_values = {field: getattr(obj, field) for field in fields}
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
            action="warehouse.updated_by_platform_admin" if change else "warehouse.created_by_platform_admin",
            entity_type="warehouse",
            entity_id=str(obj.id),
            metadata={"name": obj.name, "changes": changes},
        )

    def delete_model(self, request, obj):
        AuditEvent.objects.create(
            organization=obj.organization,
            actor=request.user,
            action="warehouse.deleted_by_platform_admin",
            entity_type="warehouse",
            entity_id=str(obj.id),
            metadata={"name": obj.name, "code": obj.code},
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for warehouse in queryset.select_related("organization").iterator():
            self.delete_model(request, warehouse)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "organization",
        "warehouse",
        "product",
        "direction",
        "quantity",
        "performed_by",
    )
    list_filter = ("organization", "direction", "created_at")
    search_fields = ("warehouse__name", "product__name", "actor__email", "note")
    readonly_fields = (
        "organization",
        "warehouse",
        "product",
        "direction",
        "quantity",
        "note",
        "actor",
        "actor_email_snapshot",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="نفذها")
    def performed_by(self, obj):
        return obj.actor.email if obj.actor_id else obj.actor_email_snapshot or "مستخدم غير معروف"

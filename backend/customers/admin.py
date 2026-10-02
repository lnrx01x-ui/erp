from django.contrib import admin

from audit.models import AuditEvent
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "phone", "email", "is_active", "created_at")
    list_filter = ("is_active", "organization")
    search_fields = ("name", "phone", "email", "organization__name")
    readonly_fields = ("id", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        previous = type(obj).objects.filter(pk=obj.pk).first() if change else None
        super().save_model(request, obj, form, change)
        fields = ("name", "phone", "email", "address", "notes", "is_active")
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
            action="customer.updated_by_platform_admin" if change else "customer.created_by_platform_admin",
            entity_type="customer",
            entity_id=str(obj.id),
            metadata={"name": obj.name, "changes": changes},
        )

    def delete_model(self, request, obj):
        AuditEvent.objects.create(
            organization=obj.organization,
            actor=request.user,
            action="customer.deleted_by_platform_admin",
            entity_type="customer",
            entity_id=str(obj.id),
            metadata={"name": obj.name},
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for customer in queryset.select_related("organization").iterator():
            self.delete_model(request, customer)

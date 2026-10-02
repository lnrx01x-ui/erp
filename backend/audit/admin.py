from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = (
        "action",
        "organization_display",
        "actor_display",
        "entity_type",
        "created_at",
    )
    list_filter = ("action", "entity_type", "created_at")
    search_fields = (
        "organization__name",
        "organization_name_snapshot",
        "organization_id_snapshot",
        "actor__email",
        "entity_id",
    )
    readonly_fields = (
        "id",
        "organization",
        "organization_id_snapshot",
        "organization_name_snapshot",
        "actor",
        "actor_email_snapshot",
        "action",
        "entity_type",
        "entity_id",
        "metadata",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

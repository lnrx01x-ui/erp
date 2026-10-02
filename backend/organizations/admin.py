from django.contrib import admin

from audit.models import AuditEvent
from .models import AccessPermission, Membership, Organization, Role


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    can_delete = False
    readonly_fields = ("user", "role", "is_active", "joined_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "created_by",
        "member_count",
        "business_type",
        "country_code",
        "is_active",
        "id",
        "created_at",
    )
    list_filter = ("business_type", "country_code", "is_active")
    search_fields = ("name", "id")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (MembershipInline,)

    @admin.display(description="أنشأها")
    def created_by(self, obj):
        event = AuditEvent.objects.filter(
            organization_id_snapshot=str(obj.id),
            action__in=("organization.created", "organization.created_by_admin"),
        ).select_related("actor").first()
        if event:
            return event.actor_display
        return "غير مسجل تاريخيًا"

    @admin.display(description="الأعضاء النشطون")
    def member_count(self, obj):
        return obj.memberships.filter(is_active=True).count()

    def save_model(self, request, obj, form, change):
        previous = type(obj).objects.filter(pk=obj.pk).first() if change else None
        super().save_model(request, obj, form, change)
        if previous is None:
            action = "organization.created_by_admin"
            changes = {}
        else:
            fields = ("name", "business_type", "country_code", "is_active")
            changes = {
                field: {"old": getattr(previous, field), "new": getattr(obj, field)}
                for field in fields
                if getattr(previous, field) != getattr(obj, field)
            }
            if not changes:
                return
            action = "organization.updated"
        AuditEvent.objects.create(
            organization=obj,
            actor=request.user,
            action=action,
            entity_type="organization",
            entity_id=str(obj.id),
            metadata={"name": obj.name, "changes": changes},
        )

    def delete_model(self, request, obj):
        event = AuditEvent.objects.create(
            organization=obj,
            actor=request.user,
            action="organization.deleted",
            entity_type="organization",
            entity_id=str(obj.id),
            metadata={"name": obj.name, "source": "platform_admin"},
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for organization in queryset.select_for_update().iterator():
            self.delete_model(request, organization)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "organization", "is_system")
    list_filter = ("is_system",)
    filter_horizontal = ("permissions",)

    def save_model(self, request, obj, form, change):
        previous = type(obj).objects.filter(pk=obj.pk).first() if change else None
        self._old_role_permissions = (
            set(previous.permissions.values_list("code", flat=True))
            if previous
            else set()
        )
        super().save_model(request, obj, form, change)
        if previous is None:
            action = "role.created"
            changes = {}
        else:
            changes = {
                field: {"old": getattr(previous, field), "new": getattr(obj, field)}
                for field in ("name", "code")
                if getattr(previous, field) != getattr(obj, field)
            }
            action = "role.updated"
        AuditEvent.objects.create(
            organization=obj.organization,
            actor=request.user,
            action=action,
            entity_type="role",
            entity_id=str(obj.id),
            metadata={"name": obj.name, "changes": changes},
        )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        role = form.instance
        new_permissions = set(role.permissions.values_list("code", flat=True))
        old_permissions = getattr(self, "_old_role_permissions", new_permissions)
        if old_permissions != new_permissions:
            AuditEvent.objects.create(
                organization=role.organization,
                actor=request.user,
                action="role.permissions_changed",
                entity_type="role",
                entity_id=str(role.id),
                metadata={
                    "name": role.name,
                    "permissions": {
                        "old": sorted(old_permissions),
                        "new": sorted(new_permissions),
                    },
                },
            )


@admin.register(AccessPermission)
class AccessPermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "is_active", "joined_at")
    list_filter = ("organization", "is_active", "role")
    search_fields = ("user__email", "organization__name")

    def save_model(self, request, obj, form, change):
        previous = type(obj).objects.select_related("user", "role").filter(
            pk=obj.pk
        ).first() if change else None
        super().save_model(request, obj, form, change)
        if previous is None:
            action = "membership.created"
            changes = {}
        else:
            old_values = {
                "role": previous.role.code,
                "is_active": previous.is_active,
            }
            new_values = {
                "role": obj.role.code,
                "is_active": obj.is_active,
            }
            changes = {
                key: {"old": old_values[key], "new": new_values[key]}
                for key in old_values
                if old_values[key] != new_values[key]
            }
            if not changes:
                return
            action = "membership.updated"
        AuditEvent.objects.create(
            organization=obj.organization,
            actor=request.user,
            action=action,
            entity_type="membership",
            entity_id=str(obj.id),
            metadata={
                "user_id": str(obj.user_id),
                "email": obj.user.email,
                "changes": changes,
            },
        )

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from audit.models import AuditEvent
from organizations.models import Membership
from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = (
        "email",
        "created_by",
        "first_name",
        "last_name",
        "companies",
        "is_staff",
        "is_superuser",
        "is_platform_owner",
        "email_verified",
        "is_active",
    )
    list_filter = (
        "is_platform_owner",
        "email_verified",
        "is_staff",
        "is_superuser",
        "is_active",
    )
    readonly_fields = ("last_login", "date_joined")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "phone")}),
        (
            "Platform access",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "is_platform_owner",
                    "email_verified",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )
    search_fields = ("email", "first_name", "last_name")

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related(
            "organization_memberships__organization",
            "organization_memberships__role",
        )

    @admin.display(description="الشركات / الأدوار")
    def companies(self, obj):
        memberships = obj.organization_memberships.all()
        if not memberships:
            return "مالك المنصة" if obj.is_platform_owner else "بدون عضويات"
        return ", ".join(
            f"{membership.organization.name} ({membership.role.name})"
            for membership in memberships
        )

    @admin.display(description="أنشأ الحساب")
    def created_by(self, obj):
        event = AuditEvent.objects.filter(
            entity_type="user",
            entity_id=str(obj.pk),
            action__in=(
                "user.registered",
                "user.created",
                "user.created_by_admin",
                "platform_owner.provisioned",
            ),
        ).select_related("actor").first()
        if not event:
            return "غير مسجل تاريخيًا"
        if event.actor_id == obj.pk or event.actor_email_snapshot == obj.email:
            return "تسجيل ذاتي"
        if event.metadata.get("creator") == "createsuperuser bootstrap":
            return "تهيئة المنصة"
        return event.actor_display

    def save_model(self, request, obj, form, change):
        if obj.is_superuser:
            obj.is_platform_owner = True
        if not change and obj.is_active:
            obj.email_verified = True
        previous = type(obj).objects.filter(pk=obj.pk).first() if change else None
        super().save_model(request, obj, form, change)
        if not change:
            action = "user.created"
            metadata = {
                "email": obj.email,
                "is_active": obj.is_active,
                "email_verified": obj.email_verified,
            }
        else:
            old_values = {
                "email": previous.email,
                "first_name": previous.first_name,
                "last_name": previous.last_name,
                "phone": previous.phone,
                "is_active": previous.is_active,
                "email_verified": previous.email_verified,
                "is_staff": previous.is_staff,
                "is_superuser": previous.is_superuser,
                "is_platform_owner": previous.is_platform_owner,
            }
            new_values = {
                "email": obj.email,
                "first_name": obj.first_name,
                "last_name": obj.last_name,
                "phone": obj.phone,
                "is_active": obj.is_active,
                "email_verified": obj.email_verified,
                "is_staff": obj.is_staff,
                "is_superuser": obj.is_superuser,
                "is_platform_owner": obj.is_platform_owner,
            }
            changes = {
                key: {"old": old_values[key], "new": new_values[key]}
                for key in old_values
                if old_values[key] != new_values[key]
            }
            if not changes:
                return
            action = "user.updated"
            metadata = {"email": obj.email, "changes": changes}
        AuditEvent.objects.create(
            actor=request.user,
            action=action,
            entity_type="user",
            entity_id=str(obj.id),
            metadata=metadata,
        )

    def delete_model(self, request, obj):
        user_id = str(obj.pk)
        email = obj.email
        memberships = list(
            obj.organization_memberships.select_related("organization").all()
        )
        for membership in memberships:
            AuditEvent.objects.create(
                organization=membership.organization,
                actor=request.user,
                action="user.deleted",
                entity_type="user",
                entity_id=user_id,
                metadata={"email": email, "company": membership.organization.name},
            )
        if not memberships:
            AuditEvent.objects.create(
                actor=request.user,
                action="user.deleted",
                entity_type="user",
                entity_id=user_id,
                metadata={"email": email},
            )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for user in queryset.prefetch_related(
            "organization_memberships__organization"
        ).iterator(chunk_size=100):
            self.delete_model(request, user)

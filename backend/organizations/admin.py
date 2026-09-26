from django.contrib import admin

from .models import AccessPermission, Membership, Organization, Role


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "id", "created_at")
    search_fields = ("name", "id")
    inlines = (MembershipInline,)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "organization", "is_system")
    list_filter = ("is_system",)
    filter_horizontal = ("permissions",)


@admin.register(AccessPermission)
class AccessPermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "is_active", "joined_at")
    list_filter = ("is_active", "role")
    search_fields = ("user__email", "organization__name")

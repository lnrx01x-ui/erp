from rest_framework.permissions import BasePermission

from .models import Membership


class HasOrganizationPermission(BasePermission):
    message = "You do not have the required permission in this organization."

    def has_permission(self, request, view):
        permission_code = getattr(view, "required_permission_code", None)
        organization_id = view.kwargs.get("organization_id")
        if not permission_code or not organization_id or not request.user.is_authenticated:
            return False

        return Membership.objects.filter(
            organization_id=organization_id,
            organization__is_active=True,
            user=request.user,
            is_active=True,
            role__organization_id=organization_id,
            role__permissions__code=permission_code,
        ).exists()

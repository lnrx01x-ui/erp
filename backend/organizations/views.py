from rest_framework.generics import ListCreateAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated

from .models import Membership, Organization, Role
from .permissions import HasOrganizationPermission
from .serializers import (
    OrganizationMembershipSerializer,
    OrganizationRoleSummarySerializer,
    OrganizationSerializer,
)
from .services import create_organization_for_owner


class OrganizationListCreateView(ListCreateAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Organization.objects.filter(
            memberships__user=self.request.user,
            memberships__is_active=True,
        ).distinct()

    def perform_create(self, serializer):
        organization = create_organization_for_owner(
            name=serializer.validated_data["name"],
            actor=self.request.user,
        )
        serializer.instance = organization


class OrganizationMembershipListView(ListAPIView):
    serializer_class = OrganizationMembershipSerializer
    permission_classes = (IsAuthenticated, HasOrganizationPermission)

    def get_permissions(self):
        self.required_permission_code = "users.manage"
        return super().get_permissions()

    def get_queryset(self):
        return (
            Membership.objects.filter(organization_id=self.kwargs["organization_id"])
            .select_related("user", "role", "organization")
            .prefetch_related("role__permissions")
        )


class OrganizationRoleListView(ListAPIView):
    serializer_class = OrganizationRoleSummarySerializer
    permission_classes = (IsAuthenticated, HasOrganizationPermission)

    def get_permissions(self):
        self.required_permission_code = "roles.manage"
        return super().get_permissions()

    def get_queryset(self):
        return Role.objects.filter(
            organization_id=self.kwargs["organization_id"]
        ).prefetch_related("permissions")

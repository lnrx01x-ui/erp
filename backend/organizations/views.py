from django.db import transaction
from django.db.models.deletion import ProtectedError
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.generics import (
    ListAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import IsAuthenticated

from audit.models import AuditEvent
from .models import Membership, Organization, Role
from .permissions import HasOrganizationPermission
from .serializers import (
    OrganizationMembershipSerializer,
    OrganizationRoleSummarySerializer,
    OrganizationSerializer,
)
from .services import create_organization_for_owner


class DeletionConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "لا يمكن حذف الشركة لوجود سجلات مالية أو حركات مخزون مرتبطة بها."
    default_code = "deletion_conflict"


class OrganizationListCreateView(ListCreateAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Organization.objects.filter(
            is_active=True,
            memberships__user=self.request.user,
            memberships__is_active=True,
        ).distinct()

    def perform_create(self, serializer):
        organization = create_organization_for_owner(
            name=serializer.validated_data["name"],
            actor=self.request.user,
            business_type=serializer.validated_data.get(
                "business_type",
                Organization.BusinessType.COMPANY,
            ),
            country_code=serializer.validated_data.get(
                "country_code",
                Organization.CountryCode.EGYPT,
            ),
        )
        serializer.instance = organization


class OrganizationDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = (IsAuthenticated, HasOrganizationPermission)
    http_method_names = ("get", "put", "patch", "delete", "head", "options")
    lookup_field = "id"
    lookup_url_kwarg = "organization_id"

    def get_permissions(self):
        self.required_permission_code = "organization.manage"
        return super().get_permissions()

    def get_queryset(self):
        return Organization.objects.filter(
            is_active=True,
            memberships__user=self.request.user,
            memberships__is_active=True,
        ).distinct()

    @transaction.atomic
    def perform_update(self, serializer):
        previous_name = serializer.instance.name
        organization = serializer.save()
        changes = {}
        if previous_name != organization.name:
            changes["name"] = {"old": previous_name, "new": organization.name}
        AuditEvent.objects.create(
            organization=organization,
            actor=self.request.user,
            action="organization.updated",
            entity_type="organization",
            entity_id=str(organization.id),
            metadata={"name": organization.name, "changes": changes},
        )

    @transaction.atomic
    def perform_destroy(self, instance):
        organization = Organization.objects.select_for_update().get(pk=instance.pk)
        if organization.sales_invoices.exists() or organization.stock_movements.exists():
            raise DeletionConflict()
        AuditEvent.objects.create(
            organization=organization,
            actor=self.request.user,
            action="organization.deleted",
            entity_type="organization",
            entity_id=str(organization.id),
            metadata={
                "name": organization.name,
                "message": "Company deleted; business history retained.",
            },
        )
        Membership.objects.filter(organization=organization).delete()
        try:
            organization.delete()
        except ProtectedError as error:
            raise DeletionConflict() from error


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

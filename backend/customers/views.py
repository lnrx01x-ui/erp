from django.db import transaction
from django.db.models.deletion import ProtectedError
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated

from audit.models import AuditEvent
from organizations.models import Membership
from organizations.permissions import HasOrganizationPermission

from .models import Customer
from .serializers import CustomerSerializer


class DeletionConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "لا يمكن حذف العميل لارتباطه بفواتير أو سجلات تاريخية."
    default_code = "deletion_conflict"


class OrganizationCustomerListCreateView(ListCreateAPIView):
    serializer_class = CustomerSerializer
    permission_classes = (IsAuthenticated, HasOrganizationPermission)

    def get_permissions(self):
        self.required_permission_code = (
            "customers.manage" if self.request.method == "POST" else "customers.read"
        )
        return super().get_permissions()

    def get_queryset(self):
        return Customer.objects.filter(
            organization_id=self.kwargs["organization_id"],
            is_active=True,
            organization__memberships__user=self.request.user,
            organization__memberships__is_active=True,
        ).distinct()

    @transaction.atomic
    def perform_create(self, serializer):
        organization_membership = Membership.objects.get(
            organization_id=self.kwargs["organization_id"],
            user=self.request.user,
            is_active=True,
        )
        customer = serializer.save(organization=organization_membership.organization)
        AuditEvent.objects.create(
            organization=customer.organization,
            actor=self.request.user,
            action="customer.created",
            entity_type="customer",
            entity_id=str(customer.id),
            metadata={
                "name": customer.name,
                "email": customer.email,
                "phone": customer.phone,
            },
        )


class OrganizationCustomerDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = CustomerSerializer
    permission_classes = (IsAuthenticated, HasOrganizationPermission)
    http_method_names = ("get", "put", "patch", "delete", "head", "options")

    def get_permissions(self):
        self.required_permission_code = (
            "customers.read" if self.request.method == "GET" else "customers.manage"
        )
        return super().get_permissions()

    def get_queryset(self):
        return Customer.objects.filter(
            organization_id=self.kwargs["organization_id"],
            is_active=True,
            organization__memberships__user=self.request.user,
            organization__memberships__is_active=True,
        ).distinct()

    @transaction.atomic
    def perform_update(self, serializer):
        previous = serializer.instance
        old_values = {
            "name": previous.name,
            "email": previous.email,
            "phone": previous.phone,
            "address": previous.address,
            "notes": previous.notes,
        }
        customer = serializer.save()
        new_values = {
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "address": customer.address,
            "notes": customer.notes,
        }
        changes = {
            key: {"old": old_values[key], "new": new_values[key]}
            for key in old_values
            if old_values[key] != new_values[key]
        }
        AuditEvent.objects.create(
            organization=customer.organization,
            actor=self.request.user,
            action="customer.updated",
            entity_type="customer",
            entity_id=str(customer.id),
            metadata={
                "name": customer.name,
                "email": customer.email,
                "phone": customer.phone,
                "changes": changes,
            },
        )

    @transaction.atomic
    def perform_destroy(self, instance):
        customer = Customer.objects.select_for_update().get(pk=instance.pk)
        customer_id = str(customer.id)
        customer_name = customer.name
        organization_id = customer.organization_id
        try:
            customer.delete()
        except ProtectedError as error:
            raise DeletionConflict() from error
        AuditEvent.objects.create(
            organization_id=organization_id,
            actor=self.request.user,
            action="customer.deleted",
            entity_type="customer",
            entity_id=customer_id,
            metadata={"name": customer_name},
        )

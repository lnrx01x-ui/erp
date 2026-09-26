from django.db import transaction
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated

from audit.models import AuditEvent
from organizations.models import Membership
from organizations.permissions import HasOrganizationPermission

from .models import Customer
from .serializers import CustomerSerializer


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

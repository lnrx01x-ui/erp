from django.db import transaction
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated

from audit.models import AuditEvent
from organizations.models import Membership
from organizations.permissions import HasOrganizationPermission

from .models import Product
from .serializers import ProductSerializer


class OrganizationProductListCreateView(ListCreateAPIView):
    serializer_class = ProductSerializer
    permission_classes = (IsAuthenticated, HasOrganizationPermission)

    def get_permissions(self):
        self.required_permission_code = (
            "products.manage" if self.request.method == "POST" else "products.read"
        )
        return super().get_permissions()

    def get_queryset(self):
        return Product.objects.filter(
            organization_id=self.kwargs["organization_id"],
            organization__memberships__user=self.request.user,
            organization__memberships__is_active=True,
        ).distinct()

    @transaction.atomic
    def perform_create(self, serializer):
        membership = Membership.objects.get(
            organization_id=self.kwargs["organization_id"],
            user=self.request.user,
            is_active=True,
        )
        product = serializer.save(organization=membership.organization)
        AuditEvent.objects.create(
            organization=product.organization,
            actor=self.request.user,
            action="product.created",
            entity_type="product",
            entity_id=str(product.id),
            metadata={
                "name": product.name,
                "sku": product.sku,
                "sale_price": str(product.sale_price),
                "cost_price": str(product.cost_price),
            },
        )

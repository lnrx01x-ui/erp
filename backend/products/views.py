from django.db import transaction
from rest_framework.generics import ListCreateAPIView, UpdateAPIView
from rest_framework.permissions import IsAuthenticated

from audit.models import AuditEvent
from organizations.models import Membership
from organizations.permissions import HasOrganizationPermission

from .models import Product, ProductCategory
from .serializers import ProductCategorySerializer, ProductSerializer


class OrganizationProductCategoryListCreateView(ListCreateAPIView):
    serializer_class = ProductCategorySerializer
    permission_classes = (IsAuthenticated, HasOrganizationPermission)

    def get_permissions(self):
        self.required_permission_code = (
            "products.manage" if self.request.method == "POST" else "products.read"
        )
        return super().get_permissions()

    def get_queryset(self):
        return ProductCategory.objects.filter(
            organization_id=self.kwargs["organization_id"],
        )

    @transaction.atomic
    def perform_create(self, serializer):
        membership = Membership.objects.get(
            organization_id=self.kwargs["organization_id"],
            user=self.request.user,
            is_active=True,
        )
        category = serializer.save(organization=membership.organization)
        AuditEvent.objects.create(
            organization=category.organization,
            actor=self.request.user,
            action="product_category.created",
            entity_type="product_category",
            entity_id=str(category.id),
            metadata={"name": category.name},
        )


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
        ).select_related("category").distinct()

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
                "category_id": str(product.category_id) if product.category_id else None,
                "sale_price": str(product.sale_price),
                "cost_price": str(product.cost_price),
            },
        )


class OrganizationProductDetailView(UpdateAPIView):
    serializer_class = ProductSerializer
    permission_classes = (IsAuthenticated, HasOrganizationPermission)
    http_method_names = ("put", "patch", "head", "options")

    def get_permissions(self):
        self.required_permission_code = "products.manage"
        return super().get_permissions()

    def get_queryset(self):
        return Product.objects.filter(
            organization_id=self.kwargs["organization_id"],
            organization__memberships__user=self.request.user,
            organization__memberships__is_active=True,
        ).select_related("category").distinct()

    @transaction.atomic
    def perform_update(self, serializer):
        product = serializer.save()
        AuditEvent.objects.create(
            organization=product.organization,
            actor=self.request.user,
            action="product.updated",
            entity_type="product",
            entity_id=str(product.id),
            metadata={
                "name": product.name,
                "sku": product.sku,
                "category_id": str(product.category_id) if product.category_id else None,
                "sale_price": str(product.sale_price),
                "cost_price": str(product.cost_price),
            },
        )

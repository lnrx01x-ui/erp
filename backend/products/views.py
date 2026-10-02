from django.db import transaction
from django.db.models.deletion import ProtectedError
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated

from audit.models import AuditEvent
from organizations.models import Membership
from organizations.permissions import HasOrganizationPermission

from .models import Product, ProductCategory
from .serializers import ProductCategorySerializer, ProductSerializer


class DeletionConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "لا يمكن حذف المنتج لارتباطه بفواتير أو حركات مخزون."
    default_code = "deletion_conflict"


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
            is_active=True,
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


class OrganizationProductDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSerializer
    permission_classes = (IsAuthenticated, HasOrganizationPermission)
    http_method_names = ("put", "patch", "delete", "head", "options")

    def get_permissions(self):
        self.required_permission_code = "products.manage"
        return super().get_permissions()

    def get_queryset(self):
        return Product.objects.filter(
            organization_id=self.kwargs["organization_id"],
            is_active=True,
            organization__memberships__user=self.request.user,
            organization__memberships__is_active=True,
        ).select_related("category").distinct()

    @transaction.atomic
    def perform_update(self, serializer):
        previous = serializer.instance
        old_values = {
            "name": previous.name,
            "sku": previous.sku,
            "category_id": str(previous.category_id) if previous.category_id else None,
            "description": previous.description,
            "unit": previous.unit,
            "sale_price": str(previous.sale_price),
            "cost_price": str(previous.cost_price),
        }
        product = serializer.save()
        new_values = {
            "name": product.name,
            "sku": product.sku,
            "category_id": str(product.category_id) if product.category_id else None,
            "description": product.description,
            "unit": product.unit,
            "sale_price": str(product.sale_price),
            "cost_price": str(product.cost_price),
        }
        changes = {
            key: {"old": old_values[key], "new": new_values[key]}
            for key in old_values
            if old_values[key] != new_values[key]
        }
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
                "changes": changes,
            },
        )

    @transaction.atomic
    def perform_destroy(self, instance):
        product = Product.objects.select_for_update().get(pk=instance.pk)
        product_id = str(product.id)
        organization_id = product.organization_id
        metadata = {"name": product.name, "sku": product.sku}
        try:
            product.delete()
        except ProtectedError as error:
            raise DeletionConflict() from error
        AuditEvent.objects.create(
            organization_id=organization_id,
            actor=self.request.user,
            action="product.deleted",
            entity_type="product",
            entity_id=product_id,
            metadata=metadata,
        )

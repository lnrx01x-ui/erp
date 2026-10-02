from django.db import transaction
from django.db.models import Case, DecimalField, F, Sum, When
from django.db.models.deletion import ProtectedError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditEvent
from organizations.models import Membership
from organizations.permissions import HasOrganizationPermission
from products.models import Product

from .models import StockMovement, Warehouse
from .serializers import (
    StockBalanceSerializer,
    StockMovementSerializer,
    WarehouseSerializer,
)


def active_membership_for_request(request, organization_id):
    return Membership.objects.select_related("organization").get(
        organization_id=organization_id,
        user=request.user,
        is_active=True,
    )


class OrganizationWarehouseListCreateView(ListCreateAPIView):
    serializer_class = WarehouseSerializer
    permission_classes = (IsAuthenticated, HasOrganizationPermission)

    def get_permissions(self):
        self.required_permission_code = (
            "inventory.manage"
            if self.request.method in {"POST", "PUT", "PATCH", "DELETE"}
            else "inventory.read"
        )
        return super().get_permissions()

    def get_queryset(self):
        return Warehouse.objects.filter(
            organization_id=self.kwargs["organization_id"],
        )

    @transaction.atomic
    def perform_create(self, serializer):
        membership = active_membership_for_request(
            self.request,
            self.kwargs["organization_id"],
        )
        warehouse = serializer.save(organization=membership.organization)
        AuditEvent.objects.create(
            organization=membership.organization,
            actor=self.request.user,
            action="warehouse.created",
            entity_type="warehouse",
            entity_id=str(warehouse.id),
            metadata={"name": warehouse.name, "code": warehouse.code},
        )


class OrganizationWarehouseDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = WarehouseSerializer
    permission_classes = (IsAuthenticated, HasOrganizationPermission)
    http_method_names = ("get", "put", "patch", "delete", "head", "options")

    def get_permissions(self):
        self.required_permission_code = (
            "inventory.manage"
            if self.request.method in {"PUT", "PATCH", "DELETE"}
            else "inventory.read"
        )
        return super().get_permissions()

    def get_queryset(self):
        return Warehouse.objects.filter(
            organization_id=self.kwargs["organization_id"],
        )

    @transaction.atomic
    def perform_update(self, serializer):
        previous = serializer.instance
        old_values = {
            "name": previous.name,
            "code": previous.code,
            "address": previous.address,
            "is_active": previous.is_active,
        }
        warehouse = serializer.save()
        new_values = {
            "name": warehouse.name,
            "code": warehouse.code,
            "address": warehouse.address,
            "is_active": warehouse.is_active,
        }
        changes = {
            key: {"old": old_values[key], "new": new_values[key]}
            for key in old_values
            if old_values[key] != new_values[key]
        }
        AuditEvent.objects.create(
            organization=warehouse.organization,
            actor=self.request.user,
            action="warehouse.updated",
            entity_type="warehouse",
            entity_id=str(warehouse.id),
            metadata={
                "name": warehouse.name,
                "code": warehouse.code,
                "is_active": warehouse.is_active,
                "changes": changes,
            },
        )

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        warehouse = Warehouse.objects.select_for_update().get(
            pk=self.get_object().pk,
            organization_id=self.kwargs["organization_id"],
        )
        if warehouse.stock_movements.exists() or warehouse.sales_invoices.exists():
            return Response(
                {
                    "detail": (
                        "لا يمكن حذف مخزن مرتبط بحركات مخزون أو فواتير. "
                        "يمكنك تعديله أو تعطيله للاحتفاظ بالسجل."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        organization = warehouse.organization
        warehouse_id = str(warehouse.id)
        name = warehouse.name
        try:
            warehouse.delete()
        except ProtectedError:
            return Response(
                {
                    "detail": (
                        "لا يمكن حذف مخزن مرتبط بحركات مخزون أو فواتير. "
                        "يمكنك تعديله أو تعطيله للاحتفاظ بالسجل."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        AuditEvent.objects.create(
            organization=organization,
            actor=request.user,
            action="warehouse.deleted",
            entity_type="warehouse",
            entity_id=warehouse_id,
            metadata={"name": name},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationStockMovementListCreateView(ListCreateAPIView):
    serializer_class = StockMovementSerializer
    permission_classes = (IsAuthenticated, HasOrganizationPermission)

    def get_permissions(self):
        self.required_permission_code = (
            "inventory.manage"
            if self.request.method == "POST"
            else "inventory.read"
        )
        return super().get_permissions()

    def get_queryset(self):
        return StockMovement.objects.filter(
            organization_id=self.kwargs["organization_id"],
        ).select_related("warehouse", "product", "actor")

    @transaction.atomic
    def perform_create(self, serializer):
        membership = active_membership_for_request(
            self.request,
            self.kwargs["organization_id"],
        )
        product = serializer.validated_data["product"]
        direction = serializer.validated_data["direction"]

        Product.objects.select_for_update().get(pk=product.pk)
        balance = StockMovement.objects.filter(
            organization=membership.organization,
            warehouse=serializer.validated_data["warehouse"],
            product=product,
        ).aggregate(
            balance=Sum(
                Case(
                    When(direction=StockMovement.Direction.IN, then="quantity"),
                    default=-F("quantity"),
                    output_field=DecimalField(max_digits=14, decimal_places=3),
                )
            )
        )["balance"] or 0
        quantity = serializer.validated_data["quantity"]
        if direction == StockMovement.Direction.OUT and quantity > balance:
            raise ValidationError(
                {"quantity": "Stock movement would make the warehouse balance negative."}
            )

        movement = serializer.save(
            organization=membership.organization,
            actor=self.request.user,
        )
        AuditEvent.objects.create(
            organization=membership.organization,
            actor=self.request.user,
            action="stock_movement.created",
            entity_type="stock_movement",
            entity_id=str(movement.id),
            metadata={
                "warehouse_id": str(movement.warehouse_id),
                "product_id": str(movement.product_id),
                "direction": movement.direction,
                "quantity": str(movement.quantity),
                "balance": str(
                    balance
                    + (
                        movement.quantity
                        if movement.direction == StockMovement.Direction.IN
                        else -movement.quantity
                    )
                ),
            },
        )


class OrganizationStockBalanceListView(APIView):
    permission_classes = (IsAuthenticated, HasOrganizationPermission)

    def get_permissions(self):
        self.required_permission_code = "inventory.read"
        return super().get_permissions()

    def get(self, request, *args, **kwargs):
        movements = StockMovement.objects.filter(
            organization_id=self.kwargs["organization_id"],
        )
        warehouse_id = request.query_params.get("warehouse_id")
        product_id = request.query_params.get("product_id")
        if warehouse_id:
            movements = movements.filter(warehouse_id=warehouse_id)
        if product_id:
            movements = movements.filter(product_id=product_id)

        signed_quantity = Case(
            When(direction=StockMovement.Direction.IN, then="quantity"),
            default=-F("quantity"),
            output_field=DecimalField(max_digits=14, decimal_places=3),
        )
        balances = movements.values(
            "warehouse_id",
            "product_id",
            warehouse_name=F("warehouse__name"),
            product_name=F("product__name"),
            product_sku=F("product__sku"),
        ).annotate(quantity=Sum(signed_quantity)).order_by(
            "warehouse_name",
            "product_name",
            "product_id",
        )
        serializer = StockBalanceSerializer(balances, many=True)
        return Response(serializer.data)

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Case, DecimalField, F, Sum, When
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListCreateAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from audit.models import AuditEvent
from customers.models import Customer
from inventory.models import StockMovement, Warehouse
from organizations.models import Membership, Organization
from organizations.permissions import HasOrganizationPermission
from products.models import Product

from .models import Invoice, InvoiceLine, PaymentCollection
from .serializers import (
    CURRENCY_QUANTUM,
    InvoiceCreateSerializer,
    InvoiceSerializer,
    PaymentCollectionCreateSerializer,
    PaymentCollectionSerializer,
)


class OrganizationInvoiceListCreateView(ListCreateAPIView):
    permission_classes = (IsAuthenticated, HasOrganizationPermission)

    def get_permissions(self):
        self.required_permission_code = (
            "sales.manage" if self.request.method == "POST" else "sales.read"
        )
        return super().get_permissions()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return InvoiceCreateSerializer
        return InvoiceSerializer

    def get_queryset(self):
        return (
            Invoice.objects.filter(organization_id=self.kwargs["organization_id"])
            .select_related("customer", "warehouse", "actor")
            .annotate(collected_total=Sum("payments__amount"))
            .prefetch_related("lines", "payments")
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        output = InvoiceSerializer(serializer.instance, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()

    @transaction.atomic
    def issue_invoice(self, validated_data):
        organization_id = self.kwargs["organization_id"]
        membership = get_object_or_404(
            Membership.objects.select_related("organization"),
            organization_id=organization_id,
            user=self.request.user,
            is_active=True,
        )
        organization = Organization.objects.select_for_update().get(pk=organization_id)
        customer_id = validated_data["customer"].pk
        warehouse_id = validated_data["warehouse"].pk
        customer = get_object_or_404(
            Customer.objects.select_for_update(),
            pk=customer_id,
            organization=organization,
            is_active=True,
        )
        warehouse = get_object_or_404(
            Warehouse.objects.select_for_update(),
            pk=warehouse_id,
            organization=organization,
            is_active=True,
        )
        lines_data = validated_data["lines"]
        product_ids = {line["product"].pk for line in lines_data}
        products = {
            product.pk: product
            for product in Product.objects.select_for_update()
            .filter(
                pk__in=product_ids,
                organization=organization,
                is_active=True,
            )
            .order_by("pk")
        }
        if len(products) != len(product_ids):
            raise ValidationError({"lines": "يجب اختيار منتجات نشطة تابعة لهذه الشركة."})

        quantities_by_product = defaultdict(lambda: Decimal("0"))
        total = Decimal("0.00")
        for line in lines_data:
            product = products[line["product"].pk]
            quantity = line["quantity"]
            line_total = (quantity * line["unit_price"]).quantize(
                CURRENCY_QUANTUM,
                rounding=ROUND_HALF_UP,
            )
            total += line_total
            if product.unit != Product.Unit.SERVICE:
                quantities_by_product[product.pk] += quantity

        current_issue_date = timezone.localdate()
        if quantities_by_product:
            balances = (
                StockMovement.objects.filter(
                    organization=organization,
                    warehouse=warehouse,
                    product_id__in=quantities_by_product,
                )
                .values("product_id")
                .annotate(
                    balance=Sum(
                        Case(
                            When(
                                direction=StockMovement.Direction.IN,
                                then="quantity",
                            ),
                            default=-F("quantity"),
                            output_field=DecimalField(max_digits=14, decimal_places=3),
                        )
                    )
                )
            )
            balance_by_product = {
                row["product_id"]: row["balance"] or Decimal("0")
                for row in balances
            }
            for product_id, required_quantity in quantities_by_product.items():
                if required_quantity > balance_by_product.get(product_id, Decimal("0")):
                    raise ValidationError(
                        {
                            "lines": (
                                f"الرصيد غير كافٍ من {products[product_id].name} "
                                "في المخزن المحدد."
                            )
                        }
                    )

        daily_count = Invoice.objects.filter(
            organization=organization,
            issue_date=current_issue_date,
        ).count()
        invoice_number = f"INV-{current_issue_date:%Y%m%d}-{daily_count + 1:06d}"
        invoice = Invoice.objects.create(
            organization=organization,
            number=invoice_number,
            customer=customer,
            warehouse=warehouse,
            issue_date=current_issue_date,
            total=total,
            actor=self.request.user,
        )
        invoice_lines = []
        for position, line in enumerate(lines_data, start=1):
            product = products[line["product"].pk]
            quantity = line["quantity"]
            unit_price = line["unit_price"]
            invoice_lines.append(
                InvoiceLine(
                    invoice=invoice,
                    product=product,
                    product_name=product.name,
                    position=position,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=(quantity * unit_price).quantize(
                        CURRENCY_QUANTUM,
                        rounding=ROUND_HALF_UP,
                    ),
                )
            )
        InvoiceLine.objects.bulk_create(invoice_lines)

        for product_id, quantity in quantities_by_product.items():
            movement = StockMovement.objects.create(
                organization=organization,
                warehouse=warehouse,
                product=products[product_id],
                direction=StockMovement.Direction.OUT,
                quantity=quantity,
                note=f"Sales invoice {invoice.number}",
                actor=self.request.user,
            )
            AuditEvent.objects.create(
                organization=organization,
                actor=self.request.user,
                action="stock_movement.created",
                entity_type="stock_movement",
                entity_id=str(movement.id),
                metadata={
                    "warehouse_id": str(warehouse.id),
                    "product_id": str(movement.product_id),
                    "direction": movement.direction,
                    "quantity": str(movement.quantity),
                    "invoice_id": str(invoice.id),
                    "invoice_number": invoice.number,
                },
            )

        AuditEvent.objects.create(
            organization=organization,
            actor=self.request.user,
            action="sales_invoice.issued",
            entity_type="sales_invoice",
            entity_id=str(invoice.id),
            metadata={
                "number": invoice.number,
                "customer_id": str(customer.id),
                "warehouse_id": str(warehouse.id),
                "total": str(invoice.total),
                "line_count": len(invoice_lines),
            },
        )
        return invoice


class OrganizationInvoiceDetailView(RetrieveAPIView):
    serializer_class = InvoiceSerializer
    permission_classes = (IsAuthenticated, HasOrganizationPermission)

    def get_permissions(self):
        self.required_permission_code = "sales.read"
        return super().get_permissions()

    def get_queryset(self):
        return (
            Invoice.objects.filter(organization_id=self.kwargs["organization_id"])
            .select_related("customer", "warehouse", "actor")
            .annotate(collected_total=Sum("payments__amount"))
            .prefetch_related("lines", "payments")
        )


class OrganizationInvoicePaymentListCreateView(ListCreateAPIView):
    permission_classes = (IsAuthenticated, HasOrganizationPermission)

    def get_permissions(self):
        self.required_permission_code = (
            "sales.manage" if self.request.method == "POST" else "sales.read"
        )
        return super().get_permissions()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PaymentCollectionCreateSerializer
        return PaymentCollectionSerializer

    def get_queryset(self):
        self.get_invoice()
        return PaymentCollection.objects.filter(
            organization_id=self.kwargs["organization_id"],
            invoice_id=self.kwargs["invoice_id"],
        ).select_related("actor")

    def get_invoice(self):
        return get_object_or_404(
            Invoice.objects.filter(organization_id=self.kwargs["organization_id"]),
            pk=self.kwargs["invoice_id"],
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        output = PaymentCollectionSerializer(
            serializer.instance,
            context=self.get_serializer_context(),
        )
        return Response(output.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()

    @transaction.atomic
    def collect_payment(self, validated_data):
        organization_id = self.kwargs["organization_id"]
        membership = get_object_or_404(
            Membership.objects.select_related("organization"),
            organization_id=organization_id,
            user=self.request.user,
            is_active=True,
        )
        invoice = get_object_or_404(
            Invoice.objects.select_for_update().filter(
                organization=membership.organization,
            ),
            pk=self.kwargs["invoice_id"],
        )
        collected = invoice.payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        amount = validated_data["amount"]
        if collected + amount > invoice.total:
            raise ValidationError(
                {"amount": "مبلغ التحصيل أكبر من الرصيد المتبقي على الفاتورة."}
            )
        payment = PaymentCollection.objects.create(
            organization=membership.organization,
            invoice=invoice,
            amount=amount,
            method=validated_data["method"],
            note=validated_data.get("note", ""),
            actor=self.request.user,
        )
        AuditEvent.objects.create(
            organization=membership.organization,
            actor=self.request.user,
            action="sales_payment.collected",
            entity_type="sales_payment",
            entity_id=str(payment.id),
            metadata={
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.number,
                "amount": str(payment.amount),
                "method": payment.method,
            },
        )
        return payment

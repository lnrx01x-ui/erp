from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db.models import Sum
from rest_framework import serializers

from customers.models import Customer
from inventory.models import Warehouse
from products.models import Product

from .models import Invoice, InvoiceLine, PaymentCollection


MAX_AMOUNT = Decimal("999999999999.99")
CURRENCY_QUANTUM = Decimal("0.01")


class InvoiceLineInputSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.none())
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2)

    def get_fields(self):
        fields = super().get_fields()
        view = self.context.get("view")
        if view is not None:
            fields["product"].queryset = Product.objects.filter(
                organization_id=view.kwargs["organization_id"],
                is_active=True,
            )
        fields["product"].error_messages["does_not_exist"] = (
            "المنتج المحدد غير متاح لهذه الشركة."
        )
        return fields

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("يجب أن تكون الكمية أكبر من صفر.")
        return value

    def validate_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError("لا يمكن أن يكون سعر الوحدة سالبًا.")
        return value


class InvoiceCreateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.none())
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.none())
    lines = InvoiceLineInputSerializer(many=True, allow_empty=False)

    def get_fields(self):
        fields = super().get_fields()
        view = self.context.get("view")
        if view is not None:
            organization_id = view.kwargs["organization_id"]
            fields["customer"].queryset = Customer.objects.filter(
                organization_id=organization_id,
                is_active=True,
            )
            fields["warehouse"].queryset = Warehouse.objects.filter(
                organization_id=organization_id,
                is_active=True,
            )
        fields["customer"].error_messages["does_not_exist"] = (
            "العميل المحدد غير متاح لهذه الشركة."
        )
        fields["warehouse"].error_messages["does_not_exist"] = (
            "المخزن المحدد غير متاح لهذه الشركة."
        )
        return fields

    def validate(self, attrs):
        total = Decimal("0.00")
        for index, line in enumerate(attrs["lines"]):
            try:
                line_total = (line["quantity"] * line["unit_price"]).quantize(
                    CURRENCY_QUANTUM,
                    rounding=ROUND_HALF_UP,
                )
            except InvalidOperation:
                raise serializers.ValidationError(
                    {"lines": {index: "إجمالي البند يتجاوز الحد المسموح."}}
                )
            if line_total > MAX_AMOUNT:
                raise serializers.ValidationError(
                    {"lines": {index: "إجمالي البند يتجاوز الحد المسموح."}}
                )
            total += line_total
        if total > MAX_AMOUNT:
            raise serializers.ValidationError(
                {"lines": "إجمالي الفاتورة يتجاوز الحد المسموح."}
            )
        attrs["total"] = total
        return attrs

    def create(self, validated_data):
        return self.context["view"].issue_invoice(validated_data)


class InvoiceLineSerializer(serializers.ModelSerializer):
    product = serializers.UUIDField(source="product_id", read_only=True)

    class Meta:
        model = InvoiceLine
        fields = ("id", "product", "product_name", "quantity", "unit_price", "line_total")


class PaymentCollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentCollection
        fields = ("id", "amount", "method", "note", "actor", "collected_at")
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    lines = InvoiceLineSerializer(many=True, read_only=True)
    payments = PaymentCollectionSerializer(many=True, read_only=True)
    amount_collected = serializers.SerializerMethodField()
    balance_due = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = (
            "id",
            "number",
            "customer",
            "customer_name",
            "warehouse",
            "warehouse_name",
            "issue_date",
            "total",
            "amount_collected",
            "balance_due",
            "actor",
            "issued_at",
            "lines",
            "payments",
        )
        read_only_fields = fields

    def get_amount_collected(self, invoice):
        total = getattr(invoice, "collected_total", None)
        if total is None:
            total = invoice.payments.aggregate(total=Sum("amount"))["total"]
        return total or Decimal("0.00")

    def get_balance_due(self, invoice):
        return invoice.total - self.get_amount_collected(invoice)


class PaymentCollectionCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    method = serializers.ChoiceField(choices=PaymentCollection.Method.choices)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("يجب أن يكون مبلغ التحصيل أكبر من صفر.")
        return value

    def validate_note(self, value):
        return value.strip()

    def create(self, validated_data):
        return self.context["view"].collect_payment(validated_data)

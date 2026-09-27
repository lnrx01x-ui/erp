from rest_framework import serializers

from products.models import Product

from .models import StockMovement, Warehouse


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = (
            "id",
            "name",
            "code",
            "address",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Warehouse name cannot be blank.")
        return name

    def validate_code(self, value):
        code = value.strip().upper()
        organization_id = self.context["view"].kwargs["organization_id"]
        if code and Warehouse.objects.filter(
            organization_id=organization_id,
            code__iexact=code,
        ).exclude(pk=getattr(self.instance, "pk", None)).exists():
            raise serializers.ValidationError("This warehouse code is already used in this company.")
        return code

    def validate(self, attrs):
        organization_id = self.context["view"].kwargs["organization_id"]
        name = attrs.get("name", getattr(self.instance, "name", ""))
        if Warehouse.objects.filter(
            organization_id=organization_id,
            name__iexact=name.strip(),
        ).exclude(pk=getattr(self.instance, "pk", None)).exists():
            raise serializers.ValidationError({"name": "A warehouse with this name already exists."})
        return attrs


class StockMovementSerializer(serializers.ModelSerializer):
    warehouse = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.none(),
    )
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.none(),
    )

    class Meta:
        model = StockMovement
        fields = (
            "id",
            "warehouse",
            "product",
            "direction",
            "quantity",
            "note",
            "actor",
            "created_at",
        )
        read_only_fields = ("id", "actor", "created_at")

    def get_fields(self):
        fields = super().get_fields()
        view = self.context.get("view")
        if view is not None:
            organization_id = view.kwargs["organization_id"]
            fields["warehouse"].queryset = Warehouse.objects.filter(
                organization_id=organization_id,
                is_active=True,
            )
            fields["product"].queryset = Product.objects.filter(
                organization_id=organization_id,
                is_active=True,
            )
        return fields

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Movement quantity must be greater than zero.")
        return value

    def validate_note(self, value):
        return value.strip()


class StockBalanceSerializer(serializers.Serializer):
    warehouse_id = serializers.UUIDField()
    warehouse_name = serializers.CharField()
    product_id = serializers.UUIDField()
    product_name = serializers.CharField()
    product_sku = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)

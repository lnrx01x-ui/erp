from rest_framework import serializers

from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    sale_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=False,
    )
    cost_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=False,
    )

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "sku",
            "description",
            "unit",
            "sale_price",
            "cost_price",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "is_active", "created_at", "updated_at")

    def validate_name(self, value):
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("Product name cannot be blank.")
        return normalized

    def validate_sku(self, value):
        return value.strip().upper()

    def validate_description(self, value):
        return value.strip()

    def validate(self, attrs):
        organization_id = self.context["view"].kwargs["organization_id"]
        sku = attrs.get("sku", getattr(self.instance, "sku", ""))
        if sku and Product.objects.filter(organization_id=organization_id, sku=sku).exclude(
            pk=getattr(self.instance, "pk", None)
        ).exists():
            raise serializers.ValidationError({"sku": "This SKU is already used in this company."})
        return attrs

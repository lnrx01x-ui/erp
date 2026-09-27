from rest_framework import serializers

from .models import Product, ProductCategory


class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ("id", "name", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, value):
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("Category name cannot be blank.")
        organization_id = self.context["view"].kwargs["organization_id"]
        if ProductCategory.objects.filter(
            organization_id=organization_id,
            name__iexact=normalized,
        ).exists():
            raise serializers.ValidationError(
                "A category with this name already exists in this company."
            )
        return normalized


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=ProductCategory.objects.none(),
        required=False,
        allow_null=True,
    )
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
            "category",
            "description",
            "unit",
            "sale_price",
            "cost_price",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "is_active", "created_at", "updated_at")

    def get_fields(self):
        fields = super().get_fields()
        view = self.context.get("view")
        if view is not None:
            organization_id = view.kwargs["organization_id"]
            fields["category"].queryset = ProductCategory.objects.filter(
                organization_id=organization_id,
            )
        return fields

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

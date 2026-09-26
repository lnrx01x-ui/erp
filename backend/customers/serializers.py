from rest_framework import serializers

from .models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "id",
            "name",
            "phone",
            "email",
            "address",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "is_active", "created_at", "updated_at")

    def validate_name(self, value):
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("Customer name cannot be blank.")
        return normalized

    def validate_phone(self, value):
        return value.strip()

    def validate_email(self, value):
        return value.strip().lower()

    def validate_address(self, value):
        return value.strip()

    def validate_notes(self, value):
        return value.strip()

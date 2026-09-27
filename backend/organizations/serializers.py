from rest_framework import serializers

from .models import AccessPermission, Membership, Organization, Role


class AccessPermissionSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessPermission
        fields = ("code", "name", "description")
        read_only_fields = fields


class OrganizationRoleSummarySerializer(serializers.ModelSerializer):
    permissions = AccessPermissionSummarySerializer(many=True, read_only=True)

    class Meta:
        model = Role
        fields = ("id", "code", "name", "is_system", "permissions")
        read_only_fields = fields


class OrganizationMemberUserSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    firstName = serializers.CharField(source="first_name", read_only=True)
    lastName = serializers.CharField(source="last_name", read_only=True)
    phone = serializers.CharField(read_only=True)
    isActive = serializers.BooleanField(source="is_active", read_only=True)


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    user = OrganizationMemberUserSerializer(read_only=True)
    role = OrganizationRoleSummarySerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ("id", "user", "role", "is_active", "joined_at")
        read_only_fields = fields


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ("id", "name", "created_at")
        read_only_fields = ("id", "created_at")

    def validate_name(self, value):
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("Organization name cannot be blank.")
        return normalized

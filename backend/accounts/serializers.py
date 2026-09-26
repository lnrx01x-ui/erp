from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from organizations.models import Membership

from .models import User


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        trim_whitespace=False,
        write_only=True,
        style={"input_type": "password"},
    )


class CurrentUserSerializer(serializers.ModelSerializer):
    firstName = serializers.CharField(source="first_name", required=False, allow_blank=True)
    lastName = serializers.CharField(source="last_name", required=False, allow_blank=True)
    dateJoined = serializers.DateTimeField(source="date_joined", read_only=True)
    memberships = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "firstName",
            "lastName",
            "phone",
            "dateJoined",
            "memberships",
        )
        read_only_fields = ("id", "email", "dateJoined", "memberships")

    def get_memberships(self, user):
        memberships = (
            Membership.objects.filter(user=user, is_active=True)
            .select_related("organization", "role")
            .prefetch_related("role__permissions")
        )
        return [
            {
                "organizationId": str(membership.organization_id),
                "organizationName": membership.organization.name,
                "roleCode": membership.role.code,
                "roleName": membership.role.name,
                "permissions": sorted(
                    permission.code for permission in membership.role.permissions.all()
                ),
            }
            for membership in memberships
        ]

    def validate_phone(self, value):
        return value.strip()


class PasswordChangeSerializer(serializers.Serializer):
    currentPassword = serializers.CharField(
        trim_whitespace=False,
        write_only=True,
        style={"input_type": "password"},
    )
    newPassword = serializers.CharField(
        trim_whitespace=False,
        write_only=True,
        style={"input_type": "password"},
    )
    confirmNewPassword = serializers.CharField(
        trim_whitespace=False,
        write_only=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        user = self.context["request"].user
        current_password = attrs["currentPassword"]
        new_password = attrs["newPassword"]

        if not user.check_password(current_password):
            raise serializers.ValidationError(
                {"currentPassword": "Current password is incorrect."}
            )
        if new_password != attrs["confirmNewPassword"]:
            raise serializers.ValidationError(
                {"confirmNewPassword": "New passwords do not match."}
            )
        if user.check_password(new_password):
            raise serializers.ValidationError(
                {"newPassword": "Choose a password different from the current password."}
            )

        try:
            validate_password(new_password, user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"newPassword": error.messages}) from error
        return attrs

from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from audit.models import AuditEvent
from organizations.models import Membership, Organization
from organizations.services import create_organization_for_owner

from .models import User


class RegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    firstName = serializers.CharField(max_length=150)
    lastName = serializers.CharField(max_length=150, required=False, allow_blank=True)
    organizationName = serializers.CharField(max_length=160)
    businessType = serializers.ChoiceField(
        choices=Organization.BusinessType.choices,
        required=False,
        default=Organization.BusinessType.COMPANY,
    )
    countryCode = serializers.ChoiceField(
        choices=Organization.CountryCode.choices,
        required=False,
        default=Organization.CountryCode.EGYPT,
    )
    password = serializers.CharField(
        trim_whitespace=False,
        write_only=True,
        style={"input_type": "password"},
    )
    confirmPassword = serializers.CharField(
        trim_whitespace=False,
        write_only=True,
        style={"input_type": "password"},
    )

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("هذا البريد الإلكتروني مسجل بالفعل.")
        return email

    def validate_firstName(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("الاسم الأول مطلوب.")
        return name

    def validate_lastName(self, value):
        return value.strip()

    def validate_organizationName(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("اسم النشاط مطلوب.")
        return name

    def validate(self, attrs):
        if attrs["password"] != attrs["confirmPassword"]:
            raise serializers.ValidationError(
                {"confirmPassword": "كلمتا المرور غير متطابقتين."}
            )

        user = User(
            email=attrs["email"],
            first_name=attrs["firstName"],
            last_name=attrs.get("lastName", ""),
        )
        try:
            validate_password(attrs["password"], user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from error
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirmPassword")
        password = validated_data.pop("password")
        organization_name = validated_data.pop("organizationName")
        user = User.objects.create_user(
            email=validated_data["email"],
            password=password,
            is_active=False,
            email_verified=False,
            first_name=validated_data["firstName"],
            last_name=validated_data.get("lastName", ""),
        )
        create_organization_for_owner(
            name=organization_name,
            actor=user,
            business_type=validated_data["businessType"],
            country_code=validated_data["countryCode"],
        )
        AuditEvent.objects.create(
            actor=user,
            action="user.registered",
            entity_type="user",
            entity_id=str(user.id),
            metadata={
                "email": user.email,
                "organization_name": organization_name,
                "business_type": validated_data["businessType"],
                "country_code": validated_data["countryCode"],
            },
        )
        return user


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
                "businessType": membership.organization.business_type,
                "countryCode": membership.organization.country_code,
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


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    newPassword = serializers.CharField(
        trim_whitespace=False,
        write_only=True,
        style={"input_type": "password"},
    )
    confirmPassword = serializers.CharField(
        trim_whitespace=False,
        write_only=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        if attrs["newPassword"] != attrs["confirmPassword"]:
            raise serializers.ValidationError(
                {"confirmPassword": "كلمتا المرور غير متطابقتين."}
            )
        return attrs


class EmailVerificationConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()


class EmailVerificationResendSerializer(serializers.Serializer):
    email = serializers.EmailField()

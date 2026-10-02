import uuid

from django.conf import settings
from django.db import models


class Organization(models.Model):
    class BusinessType(models.TextChoices):
        COMPANY = "company", "Company"
        RESTAURANT = "restaurant", "Restaurant"

    class CountryCode(models.TextChoices):
        EGYPT = "EG", "Egypt"
        SAUDI_ARABIA = "SA", "Saudi Arabia"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    business_type = models.CharField(
        max_length=16,
        choices=BusinessType.choices,
        default=BusinessType.COMPANY,
    )
    country_code = models.CharField(
        max_length=2,
        choices=CountryCode.choices,
        default=CountryCode.EGYPT,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")

    def __str__(self):
        return self.name


class AccessPermission(models.Model):
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=160)
    description = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ("code",)

    def __str__(self):
        return self.code


class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="roles",
    )
    name = models.CharField(max_length=100)
    code = models.SlugField(max_length=100)
    is_system = models.BooleanField(default=False)
    permissions = models.ManyToManyField(
        AccessPermission,
        related_name="roles",
        blank=True,
    )

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="unique_role_code_per_organization",
            ),
        ]

    def __str__(self):
        return f"{self.organization}: {self.name}"


class Membership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("joined_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "user"),
                name="unique_user_membership_per_organization",
            ),
        ]
        indexes = [
            models.Index(fields=("user", "is_active"), name="membership_user_active_idx"),
        ]

    def save(self, *args, **kwargs):
        role_organization_id = Role.objects.filter(pk=self.role_id).values_list(
            "organization_id",
            flat=True,
        ).first()
        if role_organization_id is None or role_organization_id != self.organization_id:
            raise ValueError("A membership role must belong to the same organization.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} @ {self.organization}"

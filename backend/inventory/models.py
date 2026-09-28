import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


class Warehouse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="warehouses",
    )
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=64, blank=True)
    address = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "organization",
                name="unique_warehouse_name_per_org",
            ),
            models.UniqueConstraint(
                fields=("organization", "code"),
                condition=~Q(code=""),
                name="unique_warehouse_code_per_org",
            ),
        ]

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        self.code = self.code.strip().upper()
        self.address = self.address.strip()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class StockMovementQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Stock movements cannot be modified.")

    def delete(self):
        raise ValidationError("Stock movements cannot be deleted.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Stock movements cannot be modified.")


class StockMovement(models.Model):
    class Direction(models.TextChoices):
        IN = "in", "Stock in"
        OUT = "out", "Stock out"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="stock_movements",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.RESTRICT,
        related_name="stock_movements",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.RESTRICT,
        related_name="stock_movements",
    )
    direction = models.CharField(max_length=3, choices=Direction.choices)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    note = models.CharField(max_length=500, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager.from_queryset(StockMovementQuerySet)()

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="stock_movement_quantity_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization", "warehouse", "product"),
                name="stock_org_wh_product_idx",
            ),
            models.Index(
                fields=("organization", "-created_at"),
                name="stock_org_created_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Stock movements cannot be modified.")
        if self.quantity is None or self.quantity <= 0:
            raise ValidationError({"quantity": "Movement quantity must be greater than zero."})
        if self.direction not in self.Direction.values:
            raise ValidationError({"direction": "Invalid stock movement direction."})
        if self.warehouse_id and self.organization_id and not Warehouse.objects.filter(
            pk=self.warehouse_id,
            organization_id=self.organization_id,
        ).exists():
            raise ValidationError({"warehouse": "Warehouse must belong to this organization."})
        if self.product_id and self.organization_id:
            from products.models import Product

            if not Product.objects.filter(
                pk=self.product_id,
                organization_id=self.organization_id,
            ).exists():
                raise ValidationError({"product": "Product must belong to this organization."})
        self.note = self.note.strip()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Stock movements cannot be deleted.")

    def __str__(self):
        return f"{self.direction} {self.quantity} {self.product}"

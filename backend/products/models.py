import uuid

from django.db import models
from django.db.models import Q


class Product(models.Model):
    class Unit(models.TextChoices):
        PIECE = "piece", "Piece"
        KILOGRAM = "kg", "Kilogram"
        GRAM = "g", "Gram"
        LITER = "l", "Liter"
        METER = "m", "Meter"
        BOX = "box", "Box"
        SERVICE = "service", "Service"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="products",
    )
    name = models.CharField(max_length=160)
    sku = models.CharField(max_length=64, blank=True)
    description = models.CharField(max_length=1000, blank=True)
    unit = models.CharField(
        max_length=16,
        choices=Unit.choices,
        default=Unit.PIECE,
    )
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.CheckConstraint(
                condition=Q(sale_price__gte=0),
                name="product_sale_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(cost_price__gte=0),
                name="product_cost_price_nonnegative",
            ),
            models.UniqueConstraint(
                fields=("organization", "sku"),
                condition=~Q(sku=""),
                name="unique_product_sku_per_organization",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization", "name"),
                name="product_org_name_idx",
            ),
            models.Index(
                fields=("organization", "is_active"),
                name="product_org_active_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        self.sku = self.sku.strip().upper()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name

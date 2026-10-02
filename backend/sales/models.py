import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from customers.models import Customer


class ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Issued sales records cannot be modified.")

    def delete(self):
        raise ValidationError("Issued sales records cannot be deleted.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Issued sales records cannot be modified.")


class Invoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="sales_invoices",
    )
    number = models.CharField(max_length=32)
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="sales_invoices",
    )
    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        on_delete=models.PROTECT,
        related_name="sales_invoices",
    )
    issue_date = models.DateField(default=timezone.localdate)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_sales_invoices",
    )
    actor_email_snapshot = models.EmailField(blank=True, default="")
    issued_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager.from_queryset(ImmutableQuerySet)()

    class Meta:
        ordering = ("-issued_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "number"),
                name="unique_sales_invoice_number_per_org",
            ),
            models.CheckConstraint(
                condition=Q(total__gte=0),
                name="sales_invoice_total_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization", "-issued_at"),
                name="sales_invoice_org_issued_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Issued invoices cannot be modified.")
        if self.customer_id and self.organization_id and not Customer.objects.filter(
            pk=self.customer_id,
            organization_id=self.organization_id,
        ).exists():
            raise ValidationError({"customer": "Customer must belong to this organization."})
        if self.warehouse_id and self.organization_id:
            from inventory.models import Warehouse

            if not Warehouse.objects.filter(
                pk=self.warehouse_id,
                organization_id=self.organization_id,
            ).exists():
                raise ValidationError({"warehouse": "Warehouse must belong to this organization."})
        if self.actor_id:
            self.actor_email_snapshot = self.actor.email
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Issued invoices cannot be deleted.")

    def __str__(self):
        return self.number


class InvoiceLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="sales_invoice_lines",
    )
    product_name = models.CharField(max_length=160)
    position = models.PositiveIntegerField()
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

    objects = models.Manager.from_queryset(ImmutableQuerySet)()

    class Meta:
        ordering = ("position",)
        constraints = [
            models.UniqueConstraint(
                fields=("invoice", "position"),
                name="unique_sales_invoice_line_position",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="sales_invoice_line_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0),
                name="sales_invoice_line_unit_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(line_total__gte=0),
                name="sales_invoice_line_total_nonnegative",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Issued invoice lines cannot be modified.")
        if self.product_id and self.invoice_id:
            from products.models import Product

            if not Product.objects.filter(
                pk=self.product_id,
                organization_id=self.invoice.organization_id,
            ).exists():
                raise ValidationError({"product": "Product must belong to this organization."})
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Issued invoice lines cannot be deleted.")

    def __str__(self):
        return f"{self.product_name} ({self.quantity})"


class PaymentCollection(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        BANK = "bank", "Bank transfer"
        CARD = "card", "Card"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="sales_payment_collections",
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=8, choices=Method.choices)
    note = models.CharField(max_length=500, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_payment_collections",
    )
    actor_email_snapshot = models.EmailField(blank=True, default="")
    collected_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager.from_queryset(ImmutableQuerySet)()

    class Meta:
        ordering = ("-collected_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="sales_payment_amount_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization", "invoice", "-collected_at"),
                name="sales_payment_org_invoice_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Payment collections cannot be modified.")
        if self.invoice_id and self.organization_id:
            if self.invoice.organization_id != self.organization_id:
                raise ValidationError({"invoice": "Invoice must belong to this organization."})
        if self.amount is None or self.amount <= 0:
            raise ValidationError({"amount": "Collection amount must be greater than zero."})
        if self.actor_id:
            self.actor_email_snapshot = self.actor.email
        self.note = self.note.strip()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Payment collections cannot be deleted.")

    def __str__(self):
        return f"{self.amount} for {self.invoice.number}"

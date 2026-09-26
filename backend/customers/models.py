import uuid

from django.db import models


class Customer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="customers",
    )
    name = models.CharField(max_length=160)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(max_length=254, blank=True)
    address = models.CharField(max_length=500, blank=True)
    notes = models.CharField(max_length=1000, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")
        indexes = [
            models.Index(
                fields=("organization", "name"),
                name="customer_org_name_idx",
            ),
            models.Index(
                fields=("organization", "is_active"),
                name="customer_org_active_idx",
            ),
        ]

    def __str__(self):
        return self.name

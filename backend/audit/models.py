import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class AuditEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Audit events cannot be modified.")

    def delete(self):
        raise ValidationError("Audit events cannot be deleted.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Audit events cannot be modified.")


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=120)
    entity_type = models.CharField(max_length=120)
    entity_id = models.CharField(max_length=120)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager.from_queryset(AuditEventQuerySet)()

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=("organization", "-created_at"),
                name="audit_org_created_idx",
            ),
            models.Index(fields=("entity_type", "entity_id"), name="audit_entity_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Audit events cannot be modified.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit events cannot be deleted.")

    def __str__(self):
        return f"{self.action} ({self.created_at:%Y-%m-%d %H:%M:%S})"

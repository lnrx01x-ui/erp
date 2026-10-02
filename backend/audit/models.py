import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class AuditEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        nullable_reference_fields = {"organization_id", "actor_id"}
        if (
            kwargs
            and set(kwargs).issubset(nullable_reference_fields)
            and all(value is None for value in kwargs.values())
        ):
            return super().update(**kwargs)
        raise ValidationError("Audit events cannot be modified.")

    def delete(self):
        raise ValidationError("Audit events cannot be deleted.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Audit events cannot be modified.")


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    organization_id_snapshot = models.CharField(max_length=36, blank=True, default="")
    organization_name_snapshot = models.CharField(max_length=160, blank=True, default="")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    actor_email_snapshot = models.EmailField(blank=True, default="")
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
        if self.organization_id:
            self.organization_id_snapshot = str(self.organization_id)
            self.organization_name_snapshot = self.organization.name
        if self.actor_id:
            self.actor_email_snapshot = self.actor.email
        return super().save(*args, **kwargs)

    @property
    def organization_display(self):
        if self.organization_id:
            return self.organization.name
        return self.organization_name_snapshot or self.organization_id_snapshot

    @property
    def actor_display(self):
        if self.actor_id:
            return self.actor.email
        return self.actor_email_snapshot or "مستخدم غير معروف"

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit events cannot be deleted.")

    def __str__(self):
        return f"{self.action} ({self.created_at:%Y-%m-%d %H:%M:%S})"

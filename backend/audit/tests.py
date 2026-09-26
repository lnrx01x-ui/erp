from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import User
from audit.models import AuditEvent
from organizations.services import create_organization_for_owner


class AuditEventTests(TestCase):
    def test_audit_events_cannot_be_updated_or_deleted(self):
        user = User.objects.create_user(
            email="owner@example.test",
            password="A-safe-test-password-123",
        )
        organization = create_organization_for_owner(name="Example Company", actor=user)
        event = AuditEvent.objects.get(organization=organization)

        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            AuditEvent.objects.filter(pk=event.pk).update(action="changed")
        with self.assertRaises(ValidationError):
            AuditEvent.objects.filter(pk=event.pk).delete()

        event.refresh_from_db()
        self.assertEqual(event.action, "organization.created")

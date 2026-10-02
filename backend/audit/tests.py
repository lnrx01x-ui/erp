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

    def test_actor_and_company_identity_survive_account_and_company_deletion(self):
        user = User.objects.create_user(
            email="historical-actor@example.test",
            password="Historical-actor-test-password-2026!",
        )
        organization = create_organization_for_owner(
            name="Historical company",
            actor=user,
        )
        event = AuditEvent.objects.create(
            organization=organization,
            actor=user,
            action="test.activity",
            entity_type="test",
            entity_id="history",
        )
        user.delete()
        organization.delete()

        event.refresh_from_db()
        self.assertIsNone(event.actor_id)
        self.assertIsNone(event.organization_id)
        self.assertEqual(event.actor_display, "historical-actor@example.test")
        self.assertEqual(event.organization_display, "Historical company")

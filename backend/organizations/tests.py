from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from audit.models import AuditEvent
from organizations.models import Membership


class OrganizationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="owner@example.test",
            password="A-safe-test-password-123",
        )

    def test_organization_creation_assigns_owner_and_audit_event(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(
            "/api/v1/organizations/",
            {"name": "  Example Company  "},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Example Company")
        membership = Membership.objects.get(user=self.user)
        self.assertEqual(str(membership.organization_id), response.data["id"])
        self.assertEqual(membership.role.code, "owner")
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=membership.organization,
                actor=self.user,
                action="organization.created",
            ).exists()
        )

    def test_organization_list_is_scoped_to_active_memberships(self):
        self.client.force_authenticate(self.user)
        first = self.client.post(
            "/api/v1/organizations/",
            {"name": "First Company"},
            format="json",
        )
        other_user = get_user_model().objects.create_user(
            email="other@example.test",
            password="Another-safe-password-123",
        )
        self.client.force_authenticate(other_user)
        second = self.client.post(
            "/api/v1/organizations/",
            {"name": "Second Company"},
            format="json",
        )

        self.client.force_authenticate(self.user)
        response = self.client.get("/api/v1/organizations/")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [first.data["id"]])

        Membership.objects.filter(user=self.user).update(is_active=False)
        inactive_response = self.client.get("/api/v1/organizations/")

        self.assertEqual(inactive_response.status_code, 200)
        self.assertEqual(inactive_response.data, [])

    def test_organization_api_requires_authentication(self):
        response = self.client.get("/api/v1/organizations/")

        self.assertEqual(response.status_code, 403)

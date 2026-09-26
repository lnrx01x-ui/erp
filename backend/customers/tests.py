from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from audit.models import AuditEvent
from organizations.models import AccessPermission, Membership, Role
from organizations.services import create_organization_for_owner


class CustomerAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="owner@example.test",
            password="A-safe-test-password-123",
        )
        self.organization = create_organization_for_owner(
            name="Example Company",
            actor=self.user,
        )
        self.client.force_authenticate(self.user)
        self.url = f"/api/v1/organizations/{self.organization.id}/customers/"

    def test_owner_can_create_and_list_customers_with_audit_event(self):
        response = self.client.post(
            self.url,
            {
                "name": "  شركة النور  ",
                "phone": "  +201000000000 ",
                "email": " INFO@EXAMPLE.COM ",
                "address": " Cairo ",
                "notes": " VIP ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "شركة النور")
        self.assertEqual(response.data["phone"], "+201000000000")
        self.assertEqual(response.data["email"], "info@example.com")
        self.assertEqual(response.data["address"], "Cairo")

        listed = self.client.get(self.url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([customer["id"] for customer in listed.data], [response.data["id"]])

        audit_event = AuditEvent.objects.get(
            action="customer.created",
            entity_id=response.data["id"],
        )
        self.assertEqual(audit_event.organization, self.organization)
        self.assertEqual(audit_event.actor, self.user)

    def test_customer_data_is_isolated_between_organizations(self):
        self.client.post(
            self.url,
            {"name": "Private customer"},
            format="json",
        )
        other_user = get_user_model().objects.create_user(
            email="other@example.test",
            password="Another-safe-password-123",
        )
        other_organization = create_organization_for_owner(
            name="Other Company",
            actor=other_user,
        )

        self.client.force_authenticate(other_user)
        other_url = f"/api/v1/organizations/{other_organization.id}/customers/"
        response = self.client.get(other_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        denied = self.client.post(self.url, {"name": "Unauthorized"}, format="json")
        self.assertEqual(denied.status_code, 403)

    def test_read_permission_does_not_allow_customer_creation(self):
        membership = Membership.objects.get(user=self.user, organization=self.organization)
        read_only_role = Role.objects.create(
            organization=self.organization,
            name="Read only",
            code="read-only",
        )
        read_only_role.permissions.add(
            AccessPermission.objects.get(code="customers.read")
        )
        membership.role = read_only_role
        membership.save()

        list_response = self.client.get(self.url)
        create_response = self.client.post(
            self.url,
            {"name": "Not allowed"},
            format="json",
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(create_response.status_code, 403)

    def test_customer_api_requires_authentication(self):
        self.client.force_authenticate(None)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

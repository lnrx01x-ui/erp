from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from audit.models import AuditEvent
from customers.models import Customer
from inventory.models import Warehouse
from organizations.models import AccessPermission, Membership, Role
from organizations.services import create_organization_for_owner
from sales.models import Invoice


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

    def test_owner_can_update_and_permanently_delete_unreferenced_customer(self):
        created = self.client.post(
            self.url,
            {"name": "Before", "phone": "+201000000000"},
            format="json",
        )
        detail_url = f"{self.url}{created.data['id']}/"

        updated = self.client.patch(
            detail_url,
            {"name": "After", "address": "Cairo"},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["name"], "After")
        self.assertEqual(updated.data["address"], "Cairo")
        self.assertTrue(
            AuditEvent.objects.filter(
                action="customer.updated",
                entity_id=created.data["id"],
                metadata__changes__name__old="Before",
                metadata__changes__name__new="After",
            ).exists()
        )

        deleted = self.client.delete(detail_url)

        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(Customer.objects.filter(pk=created.data["id"]).exists())
        self.assertEqual(self.client.get(self.url).data, [])
        self.assertTrue(
            AuditEvent.objects.filter(
                action="customer.deleted",
                entity_id=created.data["id"],
            ).exists()
        )

    def test_customer_with_invoice_history_cannot_be_deleted(self):
        created = self.client.post(
            self.url,
            {"name": "Invoiced customer"},
            format="json",
        )
        customer = Customer.objects.get(pk=created.data["id"])
        warehouse = Warehouse.objects.create(
            organization=self.organization,
            name="Main warehouse",
        )
        Invoice.objects.create(
            organization=self.organization,
            number="INV-HISTORY-1",
            customer=customer,
            warehouse=warehouse,
            total="10.00",
        )

        response = self.client.delete(f"{self.url}{customer.id}/")

        self.assertEqual(response.status_code, 409)
        self.assertTrue(Customer.objects.filter(pk=customer.pk).exists())

    def test_customer_update_and_delete_require_manage_permission(self):
        created = self.client.post(
            self.url,
            {"name": "Protected customer"},
            format="json",
        )
        membership = Membership.objects.get(
            user=self.user,
            organization=self.organization,
        )
        read_only_role = Role.objects.create(
            organization=self.organization,
            name="Customer reader",
            code="customer-reader",
        )
        read_only_role.permissions.add(
            AccessPermission.objects.get(code="customers.read")
        )
        membership.role = read_only_role
        membership.save()

        detail_url = f"{self.url}{created.data['id']}/"
        update_response = self.client.patch(
            detail_url,
            {"name": "Not allowed"},
            format="json",
        )
        delete_response = self.client.delete(detail_url)

        self.assertEqual(update_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.assertTrue(
            Customer.objects.filter(pk=created.data["id"], is_active=True).exists()
        )

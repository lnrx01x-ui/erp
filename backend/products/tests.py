from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from audit.models import AuditEvent
from organizations.models import AccessPermission, Membership, Role
from organizations.services import create_organization_for_owner
from products.models import Product


class ProductAPITests(TestCase):
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
        self.url = f"/api/v1/organizations/{self.organization.id}/products/"

    def test_owner_can_create_and_list_products_with_audit_event(self):
        response = self.client.post(
            self.url,
            {
                "name": "  Coffee Beans ",
                "sku": " cb-001 ",
                "description": "  Arabica coffee  ",
                "unit": "kg",
                "sale_price": "12.50",
                "cost_price": "8.25",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Coffee Beans")
        self.assertEqual(response.data["sku"], "CB-001")
        self.assertEqual(response.data["sale_price"], "12.50")
        self.assertEqual(response.data["cost_price"], "8.25")

        listed = self.client.get(self.url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([product["id"] for product in listed.data], [response.data["id"]])

        audit_event = AuditEvent.objects.get(
            action="product.created",
            entity_id=response.data["id"],
        )
        self.assertEqual(audit_event.organization, self.organization)
        self.assertEqual(audit_event.actor, self.user)
        self.assertEqual(audit_event.metadata["sku"], "CB-001")

    def test_duplicate_sku_is_rejected_case_insensitively(self):
        first = self.client.post(
            self.url,
            {"name": "First", "sku": "SKU-1"},
            format="json",
        )
        duplicate = self.client.post(
            self.url,
            {"name": "Second", "sku": " sku-1 "},
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("sku", duplicate.data)

    def test_same_sku_can_be_used_by_another_organization(self):
        other_user = get_user_model().objects.create_user(
            email="other@example.test",
            password="Another-safe-password-123",
        )
        other_organization = create_organization_for_owner(
            name="Other Company",
            actor=other_user,
        )
        self.client.post(
            self.url,
            {"name": "First company item", "sku": "ITEM-1"},
            format="json",
        )

        self.client.force_authenticate(other_user)
        other_url = f"/api/v1/organizations/{other_organization.id}/products/"
        response = self.client.post(
            other_url,
            {"name": "Other company item", "sku": "ITEM-1"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)

    def test_negative_prices_and_unknown_units_are_rejected(self):
        negative_price = self.client.post(
            self.url,
            {"name": "Invalid", "sale_price": "-1.00"},
            format="json",
        )
        invalid_unit = self.client.post(
            self.url,
            {"name": "Invalid unit", "unit": "unknown"},
            format="json",
        )

        self.assertEqual(negative_price.status_code, 400)
        self.assertEqual(invalid_unit.status_code, 400)
        self.assertEqual(Product.objects.count(), 0)

    def test_product_data_is_isolated_between_organizations(self):
        self.client.post(self.url, {"name": "Private product"}, format="json")
        other_user = get_user_model().objects.create_user(
            email="other@example.test",
            password="Another-safe-password-123",
        )
        other_organization = create_organization_for_owner(
            name="Other Company",
            actor=other_user,
        )

        self.client.force_authenticate(other_user)
        other_url = f"/api/v1/organizations/{other_organization.id}/products/"
        response = self.client.get(other_url)
        denied = self.client.post(
            self.url,
            {"name": "Unauthorized"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        self.assertEqual(denied.status_code, 403)

    def test_read_permission_does_not_allow_product_creation(self):
        membership = Membership.objects.get(user=self.user, organization=self.organization)
        read_only_role = Role.objects.create(
            organization=self.organization,
            name="Product reader",
            code="product-reader",
        )
        read_only_role.permissions.add(
            AccessPermission.objects.get(code="products.read")
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

    def test_product_api_requires_authentication(self):
        self.client.force_authenticate(None)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_prices_are_stored_as_exact_decimal_values(self):
        response = self.client.post(
            self.url,
            {"name": "Exact price", "sale_price": "0.10", "cost_price": "0.03"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        product = Product.objects.get(pk=response.data["id"])
        self.assertEqual(product.sale_price, Decimal("0.10"))
        self.assertEqual(product.cost_price, Decimal("0.03"))

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from audit.models import AuditEvent
from organizations.models import AccessPermission, Membership, Role
from organizations.services import create_organization_for_owner
from products.models import Product, ProductCategory


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
        self.categories_url = (
            f"/api/v1/organizations/{self.organization.id}/product-categories/"
        )

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
        self.assertIsNone(response.data["category"])

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

    def test_owner_can_update_product_fields_and_optional_category(self):
        category = ProductCategory.objects.create(
            organization=self.organization,
            name="Beverages",
        )
        product = Product.objects.create(
            organization=self.organization,
            name="Coffee",
            sku="OLD-1",
            description="Old description",
            unit=Product.Unit.PIECE,
            sale_price=Decimal("5.00"),
            cost_price=Decimal("2.00"),
        )

        response = self.client.patch(
            f"{self.url}{product.id}/",
            {
                "name": "  Ground Coffee ",
                "sku": " new-1 ",
                "category": str(category.id),
                "description": "  Arabica blend ",
                "unit": "kg",
                "sale_price": "12.50",
                "cost_price": "8.25",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Ground Coffee")
        self.assertEqual(response.data["sku"], "NEW-1")
        self.assertEqual(str(response.data["category"]), str(category.id))
        self.assertEqual(response.data["description"], "Arabica blend")
        self.assertEqual(response.data["unit"], "kg")
        self.assertEqual(response.data["sale_price"], "12.50")
        self.assertEqual(response.data["cost_price"], "8.25")

        product.refresh_from_db()
        self.assertEqual(product.category, category)
        event = AuditEvent.objects.get(
            action="product.updated",
            entity_id=str(product.id),
        )
        self.assertEqual(event.organization, self.organization)
        self.assertEqual(event.actor, self.user)
        self.assertEqual(event.metadata["category_id"], str(category.id))
        self.assertEqual(event.metadata["changes"]["name"]["old"], "Coffee")
        self.assertEqual(event.metadata["changes"]["name"]["new"], "Ground Coffee")

    def test_product_category_can_be_cleared_during_update(self):
        category = ProductCategory.objects.create(
            organization=self.organization,
            name="Beverages",
        )
        product = Product.objects.create(
            organization=self.organization,
            category=category,
            name="Coffee",
        )

        response = self.client.patch(
            f"{self.url}{product.id}/",
            {"category": None},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["category"])
        product.refresh_from_db()
        self.assertIsNone(product.category)

    def test_read_permission_does_not_allow_product_update(self):
        product = Product.objects.create(
            organization=self.organization,
            name="Protected product",
            sale_price=Decimal("5.00"),
        )
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

        response = self.client.patch(
            f"{self.url}{product.id}/",
            {"name": "Unauthorized update"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        product.refresh_from_db()
        self.assertEqual(product.name, "Protected product")

    def test_product_update_is_scoped_to_the_active_organization(self):
        product = Product.objects.create(
            organization=self.organization,
            name="Private product",
        )
        other_user = get_user_model().objects.create_user(
            email="other@example.test",
            password="unused-test-password",
        )
        other_organization = create_organization_for_owner(
            name="Other Company",
            actor=other_user,
        )
        self.client.force_authenticate(other_user)

        foreign_organization_response = self.client.patch(
            f"/api/v1/organizations/{self.organization.id}/products/{product.id}/",
            {"name": "Unauthorized"},
            format="json",
        )
        foreign_product_response = self.client.patch(
            f"/api/v1/organizations/{other_organization.id}/products/{product.id}/",
            {"name": "Unauthorized"},
            format="json",
        )

        self.assertEqual(foreign_organization_response.status_code, 403)
        self.assertEqual(foreign_product_response.status_code, 404)
        product.refresh_from_db()
        self.assertEqual(product.name, "Private product")

    def test_product_update_rejects_duplicate_sku_without_changing_the_row(self):
        Product.objects.create(
            organization=self.organization,
            name="Existing product",
            sku="USED-1",
        )
        product = Product.objects.create(
            organization=self.organization,
            name="Editable product",
            sku="EDIT-1",
            sale_price=Decimal("10.00"),
        )

        response = self.client.patch(
            f"{self.url}{product.id}/",
            {"sku": " used-1 ", "sale_price": "-1"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        product.refresh_from_db()
        self.assertEqual(product.sku, "EDIT-1")
        self.assertEqual(product.sale_price, Decimal("10.00"))

    def test_owner_can_permanently_delete_unreferenced_product(self):
        product = Product.objects.create(
            organization=self.organization,
            name="Historical product",
            sku="HISTORY-1",
        )

        response = self.client.delete(f"{self.url}{product.id}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())
        self.assertEqual(self.client.get(self.url).data, [])
        self.assertTrue(
            AuditEvent.objects.filter(
                action="product.deleted",
                entity_id=str(product.id),
                organization=self.organization,
            ).exists()
        )

    def test_product_delete_requires_manage_permission(self):
        product = Product.objects.create(
            organization=self.organization,
            name="Protected product",
        )
        membership = Membership.objects.get(
            user=self.user,
            organization=self.organization,
        )
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

        response = self.client.delete(f"{self.url}{product.id}/")

        self.assertEqual(response.status_code, 403)
        product.refresh_from_db()
        self.assertTrue(product.is_active)

    def test_product_with_inventory_history_cannot_be_deleted(self):
        from inventory.models import StockMovement, Warehouse

        product = Product.objects.create(
            organization=self.organization,
            name="Stocked product",
        )
        warehouse = Warehouse.objects.create(
            organization=self.organization,
            name="Main warehouse",
        )
        movement = StockMovement.objects.create(
            organization=self.organization,
            warehouse=warehouse,
            product=product,
            direction=StockMovement.Direction.IN,
            quantity=Decimal("2.000"),
            actor=self.user,
        )

        response = self.client.delete(f"{self.url}{product.id}/")

        self.assertEqual(response.status_code, 409)
        self.assertTrue(StockMovement.objects.filter(pk=movement.pk).exists())
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())

    def test_owner_can_create_and_list_company_categories_with_audit_event(self):
        response = self.client.post(
            self.categories_url,
            {"name": "  Beverages  "},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Beverages")

        listed = self.client.get(self.categories_url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([item["id"] for item in listed.data], [response.data["id"]])
        event = AuditEvent.objects.get(
            action="product_category.created",
            entity_id=response.data["id"],
        )
        self.assertEqual(event.organization, self.organization)
        self.assertEqual(event.actor, self.user)

    def test_category_names_are_unique_per_company_case_insensitively(self):
        first = self.client.post(
            self.categories_url,
            {"name": "Beverages"},
            format="json",
        )
        duplicate = self.client.post(
            self.categories_url,
            {"name": " beverages "},
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("name", duplicate.data)

    def test_category_can_be_assigned_to_product_and_returned_in_product_list(self):
        category_response = self.client.post(
            self.categories_url,
            {"name": "Beverages"},
            format="json",
        )

        response = self.client.post(
            self.url,
            {"name": "Coffee", "category": category_response.data["id"]},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            str(response.data["category"]),
            category_response.data["id"],
        )
        listed = self.client.get(self.url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(
            str(listed.data[0]["category"]),
            category_response.data["id"],
        )

    def test_product_cannot_use_another_companys_category(self):
        other_user = get_user_model().objects.create_user(
            email="other@example.test",
            password="unused-test-password",
        )
        other_organization = create_organization_for_owner(
            name="Other Company",
            actor=other_user,
        )
        other_category = ProductCategory.objects.create(
            organization=other_organization,
            name="Private category",
        )

        response = self.client.post(
            self.url,
            {"name": "Invalid assignment", "category": str(other_category.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("category", response.data)
        self.assertFalse(Product.objects.filter(name="Invalid assignment").exists())

    def test_same_category_name_can_be_used_by_another_company(self):
        first = self.client.post(
            self.categories_url,
            {"name": "Shared name"},
            format="json",
        )
        other_user = get_user_model().objects.create_user(
            email="other@example.test",
            password="unused-test-password",
        )
        other_organization = create_organization_for_owner(
            name="Other Company",
            actor=other_user,
        )
        self.client.force_authenticate(other_user)
        other_url = (
            f"/api/v1/organizations/{other_organization.id}/product-categories/"
        )

        second = self.client.post(
            other_url,
            {"name": "Shared name"},
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(first.data["id"], second.data["id"])

    def test_categories_are_isolated_between_companies(self):
        own_category = self.client.post(
            self.categories_url,
            {"name": "Own category"},
            format="json",
        )
        other_user = get_user_model().objects.create_user(
            email="other@example.test",
            password="unused-test-password",
        )
        other_organization = create_organization_for_owner(
            name="Other Company",
            actor=other_user,
        )
        other_category_url = (
            f"/api/v1/organizations/{other_organization.id}/product-categories/"
        )
        denied_read = self.client.get(other_category_url)
        self.client.force_authenticate(other_user)

        listed = self.client.get(other_category_url)
        denied_create = self.client.post(
            self.categories_url,
            {"name": "Unauthorized"},
            format="json",
        )

        self.assertEqual(own_category.status_code, 201)
        self.assertEqual(denied_read.status_code, 403)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.data, [])
        self.assertEqual(denied_create.status_code, 403)

    def test_product_read_permission_does_not_allow_category_creation(self):
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

        listed = self.client.get(self.categories_url)
        created = self.client.post(
            self.categories_url,
            {"name": "Not allowed"},
            format="json",
        )

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(created.status_code, 403)
        self.assertEqual(ProductCategory.objects.count(), 0)

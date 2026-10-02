from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from audit.models import AuditEvent
from organizations.models import AccessPermission, Membership, Role
from organizations.services import create_organization_for_owner
from products.models import Product

from .models import StockMovement, Warehouse


class InventoryAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            email="owner@example.test",
            password="A-safe-test-password-123!",
        )
        self.organization = create_organization_for_owner(
            name="Example Company",
            actor=self.owner,
        )
        self.client.force_authenticate(self.owner)
        self.warehouses_url = (
            f"/api/v1/organizations/{self.organization.id}/warehouses/"
        )
        self.movements_url = (
            f"/api/v1/organizations/{self.organization.id}/stock-movements/"
        )
        self.balances_url = (
            f"/api/v1/organizations/{self.organization.id}/stock-balances/"
        )
        self.product = Product.objects.create(
            organization=self.organization,
            name="Coffee Beans",
            sku="CB-001",
        )

    def create_warehouse(self, name="Main Store", code="MAIN"):
        response = self.client.post(
            self.warehouses_url,
            {"name": name, "code": code},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def post_movement(self, warehouse_id, direction, quantity, product_id=None):
        return self.client.post(
            self.movements_url,
            {
                "warehouse": warehouse_id,
                "product": product_id or str(self.product.id),
                "direction": direction,
                "quantity": str(quantity),
            },
            format="json",
        )

    def test_warehouse_create_list_update_and_delete(self):
        created = self.create_warehouse("  Main Store  ", " main ")

        self.assertEqual(created["name"], "Main Store")
        self.assertEqual(created["code"], "MAIN")
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                actor=self.owner,
                action="warehouse.created",
                entity_id=created["id"],
            ).exists()
        )

        listed = self.client.get(self.warehouses_url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([item["id"] for item in listed.data], [created["id"]])

        detail_url = f"{self.warehouses_url}{created['id']}/"
        updated = self.client.patch(detail_url, {"address": "North side"}, format="json")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["address"], "North side")
        self.assertTrue(
            AuditEvent.objects.filter(
                action="warehouse.updated",
                entity_id=created["id"],
            ).exists()
        )

        deleted = self.client.delete(detail_url)
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(Warehouse.objects.filter(pk=created["id"]).exists())
        self.assertTrue(
            AuditEvent.objects.filter(
                action="warehouse.deleted",
                entity_id=created["id"],
            ).exists()
        )

    def test_warehouse_code_and_name_are_unique_within_company(self):
        self.create_warehouse("Main Store", "MAIN")

        duplicate_name = self.client.post(
            self.warehouses_url,
            {"name": " main store ", "code": "SECOND"},
            format="json",
        )
        duplicate_code = self.client.post(
            self.warehouses_url,
            {"name": "Overflow", "code": " main "},
            format="json",
        )

        self.assertEqual(duplicate_name.status_code, 400)
        self.assertEqual(duplicate_code.status_code, 400)
        self.assertEqual(Warehouse.objects.filter(organization=self.organization).count(), 1)

    def test_warehouse_cannot_be_deleted_when_it_has_stock_history(self):
        warehouse = self.create_warehouse()
        movement = self.post_movement(warehouse["id"], "in", "1")

        response = self.client.delete(
            f"{self.warehouses_url}{warehouse['id']}/"
        )

        self.assertEqual(response.status_code, 409)
        self.assertTrue(Warehouse.objects.filter(pk=warehouse["id"]).exists())
        self.assertTrue(StockMovement.objects.filter(pk=movement.data["id"]).exists())

    def test_warehouse_can_be_updated_and_deleted_when_unused(self):
        warehouse = self.create_warehouse("Old name", "OLD")
        detail_url = f"{self.warehouses_url}{warehouse['id']}/"

        updated = self.client.patch(
            detail_url,
            {"name": "Updated name", "address": "Cairo"},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["name"], "Updated name")
        self.assertEqual(updated.data["address"], "Cairo")

        deleted = self.client.delete(detail_url)

        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(Warehouse.objects.filter(pk=warehouse["id"]).exists())

    def test_stock_in_out_and_balance_are_ledger_based(self):
        warehouse = self.create_warehouse()

        incoming = self.post_movement(warehouse["id"], "in", "12.500")
        self.assertEqual(incoming.status_code, 201, incoming.data)
        self.assertEqual(incoming.data["quantity"], "12.500")
        self.assertEqual(incoming.data["actor"], self.owner.id)
        self.assertEqual(
            StockMovement.objects.get(pk=incoming.data["id"]).actor_email_snapshot,
            self.owner.email,
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action="stock_movement.created",
                entity_id=incoming.data["id"],
            ).exists()
        )

        outgoing = self.post_movement(warehouse["id"], "out", "2.250")
        self.assertEqual(outgoing.status_code, 201, outgoing.data)
        self.assertEqual(StockMovement.objects.count(), 2)

        balances = self.client.get(self.balances_url)
        self.assertEqual(balances.status_code, 200)
        self.assertEqual(len(balances.data), 1)
        self.assertEqual(balances.data[0]["quantity"], "10.250")
        self.assertEqual(balances.data[0]["warehouse_id"], warehouse["id"])
        self.assertEqual(balances.data[0]["product_id"], str(self.product.id))

        filtered = self.client.get(f"{self.balances_url}?warehouse_id={warehouse['id']}")
        self.assertEqual(filtered.data, balances.data)

    def test_negative_or_zero_movement_and_negative_stock_are_rejected(self):
        warehouse = self.create_warehouse()

        negative = self.post_movement(warehouse["id"], "in", "-1")
        zero = self.post_movement(warehouse["id"], "in", "0")
        unknown_direction = self.post_movement(warehouse["id"], "sideways", "1")
        stock_out = self.post_movement(warehouse["id"], "out", "0.001")

        self.assertEqual(negative.status_code, 400)
        self.assertEqual(zero.status_code, 400)
        self.assertEqual(unknown_direction.status_code, 400)
        self.assertEqual(stock_out.status_code, 400)
        self.assertEqual(StockMovement.objects.count(), 0)
        self.assertEqual(self.client.get(self.balances_url).data, [])

    def test_stock_out_cannot_exceed_existing_balance(self):
        warehouse = self.create_warehouse()
        self.assertEqual(self.post_movement(warehouse["id"], "in", "5").status_code, 201)

        response = self.post_movement(warehouse["id"], "out", "5.001")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(StockMovement.objects.count(), 1)
        self.assertEqual(self.client.get(self.balances_url).data[0]["quantity"], "5.000")

    def test_movements_are_append_only(self):
        warehouse = self.create_warehouse()
        response = self.post_movement(warehouse["id"], "in", "1")
        movement = StockMovement.objects.get(pk=response.data["id"])

        with self.assertRaises(ValidationError):
            movement.save()
        with self.assertRaises(ValidationError):
            StockMovement.objects.filter(pk=movement.pk).update(quantity=Decimal("2"))
        with self.assertRaises(ValidationError):
            StockMovement.objects.filter(pk=movement.pk).delete()
        with self.assertRaises(ValidationError):
            movement.delete()

        self.assertEqual(
            self.client.patch(
                f"{self.movements_url}{movement.pk}/",
                {"quantity": "2"},
                format="json",
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete(f"{self.movements_url}{movement.pk}/").status_code,
            404,
        )
        movement.refresh_from_db()
        self.assertEqual(movement.quantity, Decimal("1.000"))

    def test_warehouse_with_movements_cannot_be_deleted(self):
        warehouse = self.create_warehouse()
        self.post_movement(warehouse["id"], "in", "1")

        response = self.client.delete(f"{self.warehouses_url}{warehouse['id']}/")

        self.assertEqual(response.status_code, 409)
        self.assertTrue(Warehouse.objects.filter(pk=warehouse["id"]).exists())

    def test_active_membership_and_inventory_permissions_are_required(self):
        membership = Membership.objects.get(
            organization=self.organization,
            user=self.owner,
        )
        reader_role = Role.objects.create(
            organization=self.organization,
            name="Inventory reader",
            code="inventory-reader",
        )
        reader_role.permissions.add(AccessPermission.objects.get(code="inventory.read"))
        membership.role = reader_role
        membership.save()
        self.client.force_authenticate(self.owner)

        self.assertEqual(self.client.get(self.warehouses_url).status_code, 200)
        self.assertEqual(self.client.get(self.movements_url).status_code, 200)
        self.assertEqual(self.client.get(self.balances_url).status_code, 200)
        self.assertEqual(
            self.client.post(
                self.warehouses_url,
                {"name": "Unauthorized"},
                format="json",
            ).status_code,
            403,
        )
        warehouse = Warehouse.objects.create(
            organization=self.organization,
            name="Protected",
            code="PROTECTED",
        )
        warehouse_url = f"{self.warehouses_url}{warehouse.id}/"
        self.assertEqual(
            self.client.patch(
                warehouse_url,
                {"name": "Unauthorized update"},
                format="json",
            ).status_code,
            403,
        )
        self.assertEqual(self.client.delete(warehouse_url).status_code, 403)

        membership.is_active = False
        membership.save()
        self.assertEqual(self.client.get(self.warehouses_url).status_code, 403)

    def test_cross_company_data_and_references_are_isolated(self):
        warehouse = self.create_warehouse()
        other_user = get_user_model().objects.create_user(
            email="other@example.test",
            password="A-safe-test-password-123!",
        )
        other_organization = create_organization_for_owner(
            name="Other Company",
            actor=other_user,
        )
        other_product = Product.objects.create(
            organization=other_organization,
            name="Other coffee",
            sku="OTHER",
        )
        other_warehouse_url = (
            f"/api/v1/organizations/{other_organization.id}/warehouses/"
        )
        other_movements_url = (
            f"/api/v1/organizations/{other_organization.id}/stock-movements/"
        )
        other_balances_url = (
            f"/api/v1/organizations/{other_organization.id}/stock-balances/"
        )

        self.assertEqual(self.client.get(other_warehouse_url).status_code, 403)
        self.assertEqual(self.client.get(other_movements_url).status_code, 403)
        self.assertEqual(self.client.get(other_balances_url).status_code, 403)
        self.assertEqual(
            self.post_movement(
                warehouse["id"],
                "in",
                "1",
                product_id=str(other_product.id),
            ).status_code,
            400,
        )

        self.client.force_authenticate(other_user)
        self.assertEqual(self.client.get(other_warehouse_url).data, [])
        self.assertEqual(self.client.get(other_movements_url).data, [])
        self.assertEqual(self.client.get(other_balances_url).data, [])
        self.assertEqual(
            self.client.post(
                other_movements_url,
                {
                    "warehouse": warehouse["id"],
                    "product": str(other_product.id),
                    "direction": "in",
                    "quantity": "1",
                },
                format="json",
            ).status_code,
            400,
        )

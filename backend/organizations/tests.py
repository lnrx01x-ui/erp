from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from audit.models import AuditEvent
from customers.models import Customer
from inventory.models import StockMovement, Warehouse
from organizations.models import Membership, Organization, Role
from organizations.services import create_organization_for_owner
from products.models import Product, ProductCategory
from sales.models import Invoice, InvoiceLine, PaymentCollection


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


class OrganizationMembershipAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            email="owner@example.test",
            password="A-safe-test-password-123",
        )
        self.organization = create_organization_for_owner(
            name="Example Company",
            actor=self.owner,
        )
        self.employee = user_model.objects.create_user(
            email="employee@example.test",
            password="Another-safe-password-123",
            first_name="Jamie",
            last_name="Employee",
            phone="+201000000000",
        )
        self.employee_role = Role.objects.get(
            organization=self.organization,
            code="employee",
        )
        self.employee_membership = Membership.objects.create(
            organization=self.organization,
            user=self.employee,
            role=self.employee_role,
        )
        self.members_url = (
            f"/api/v1/organizations/{self.organization.id}/members/"
        )
        self.roles_url = f"/api/v1/organizations/{self.organization.id}/roles/"
        self.client.force_authenticate(self.owner)

    def test_manager_sees_only_organization_members_with_roles_and_permissions(self):
        response = self.client.get(self.members_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        employee = next(
            item
            for item in response.data
            if item["user"]["id"] == str(self.employee.id)
        )
        self.assertEqual(employee["user"]["email"], self.employee.email)
        self.assertEqual(employee["user"]["firstName"], "Jamie")
        self.assertEqual(employee["user"]["lastName"], "Employee")
        self.assertEqual(employee["user"]["phone"], "+201000000000")
        self.assertTrue(employee["user"]["isActive"])
        self.assertEqual(employee["role"]["code"], "employee")
        self.assertEqual(employee["role"]["name"], "Employee")
        self.assertEqual(employee["role"]["permissions"], [])
        self.assertTrue(employee["is_active"])

    def test_member_list_includes_inactive_membership_and_marks_it_inactive(self):
        self.employee_membership.is_active = False
        self.employee_membership.save()

        response = self.client.get(self.members_url)

        self.assertEqual(response.status_code, 200)
        employee = next(
            item
            for item in response.data
            if item["user"]["id"] == str(self.employee.id)
        )
        self.assertFalse(employee["is_active"])

    def test_manager_sees_only_roles_and_permissions_for_the_requested_company(self):
        response = self.client.get(self.roles_url)

        self.assertEqual(response.status_code, 200)
        role_codes = {item["code"] for item in response.data}
        self.assertEqual(role_codes, {"owner", "administrator", "employee"})
        owner = next(item for item in response.data if item["code"] == "owner")
        self.assertTrue(owner["is_system"])
        permission_codes = {permission["code"] for permission in owner["permissions"]}
        self.assertIn("users.manage", permission_codes)
        self.assertIn("roles.manage", permission_codes)
        self.assertTrue(all("name" in permission for permission in owner["permissions"]))

    def test_company_member_cannot_read_another_companys_members_or_roles(self):
        outsider = get_user_model().objects.create_user(
            email="outsider@example.test",
            password="Different-safe-password-123",
        )
        other_organization = create_organization_for_owner(
            name="Other Company",
            actor=outsider,
        )
        other_membership_url = (
            f"/api/v1/organizations/{other_organization.id}/members/"
        )
        other_roles_url = (
            f"/api/v1/organizations/{other_organization.id}/roles/"
        )

        member_response = self.client.get(other_membership_url)
        roles_response = self.client.get(other_roles_url)

        self.assertEqual(member_response.status_code, 403)
        self.assertEqual(roles_response.status_code, 403)

        own_members = self.client.get(self.members_url)
        self.assertEqual(
            {item["user"]["email"] for item in own_members.data},
            {self.owner.email, self.employee.email},
        )

    def test_membership_and_role_catalog_require_their_scoped_permissions(self):
        self.client.force_authenticate(self.employee)

        members_response = self.client.get(self.members_url)
        roles_response = self.client.get(self.roles_url)

        self.assertEqual(members_response.status_code, 403)
        self.assertEqual(roles_response.status_code, 403)

    def test_membership_and_role_catalog_are_read_only(self):
        member_create = self.client.post(
            self.members_url,
            {"email": "new@example.test"},
            format="json",
        )
        role_create = self.client.post(
            self.roles_url,
            {"name": "New role"},
            format="json",
        )

        self.assertEqual(member_create.status_code, 405)
        self.assertEqual(role_create.status_code, 405)
        self.assertEqual(Membership.objects.count(), 2)
        self.assertEqual(Role.objects.filter(organization=self.organization).count(), 3)

    def test_membership_and_role_catalog_require_authentication(self):
        self.client.force_authenticate(None)

        members_response = self.client.get(self.members_url)
        roles_response = self.client.get(self.roles_url)

        self.assertEqual(members_response.status_code, 403)
        self.assertEqual(roles_response.status_code, 403)


class OrganizationDeletionAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = get_user_model().objects.create_user(
            email="company-owner@example.test",
            password="Safe-password-2026!",
        )
        self.organization = create_organization_for_owner(
            name="Company to remove",
            actor=self.owner,
        )
        self.url = f"/api/v1/organizations/{self.organization.id}/"
        self.client.force_authenticate(self.owner)

    def test_deleting_company_removes_only_its_records_and_preserves_user(self):
        other_organization = create_organization_for_owner(
            name="Company to keep",
            actor=self.owner,
        )
        category = ProductCategory.objects.create(
            organization=self.organization,
            name="Hardware",
        )
        product = Product.objects.create(
            organization=self.organization,
            category=category,
            name="Demo product",
            sku="DELETE-TEST",
        )
        warehouse = Warehouse.objects.create(
            organization=self.organization,
            name="Delete test warehouse",
        )
        customer = Customer.objects.create(
            organization=self.organization,
            name="Delete test customer",
        )
        StockMovement.objects.create(
            organization=self.organization,
            warehouse=warehouse,
            product=product,
            direction=StockMovement.Direction.IN,
            quantity=Decimal("5.000"),
            actor=self.owner,
        )
        invoice = Invoice.objects.create(
            organization=self.organization,
            number="DELETE-TEST-001",
            customer=customer,
            warehouse=warehouse,
            total=Decimal("10.00"),
            actor=self.owner,
        )
        InvoiceLine.objects.create(
            invoice=invoice,
            product=product,
            product_name=product.name,
            position=1,
            quantity=Decimal("1.000"),
            unit_price=Decimal("10.00"),
            line_total=Decimal("10.00"),
        )
        PaymentCollection.objects.create(
            organization=self.organization,
            invoice=invoice,
            amount=Decimal("10.00"),
            method=PaymentCollection.Method.CASH,
            actor=self.owner,
        )

        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            Organization.objects.filter(pk=self.organization.pk).exists()
        )
        for model in (
            Membership,
            Role,
            ProductCategory,
            Product,
            Warehouse,
            Customer,
            StockMovement,
            InvoiceLine,
            PaymentCollection,
            Invoice,
            AuditEvent,
        ):
            self.assertFalse(
                model.objects.filter(organization=self.organization).exists()
                if model is not InvoiceLine
                else model.objects.filter(invoice__organization=self.organization).exists()
            )

        self.assertTrue(get_user_model().objects.filter(pk=self.owner.pk).exists())
        self.assertTrue(
            Membership.objects.filter(
                user=self.owner,
                organization=other_organization,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(organization=other_organization).exists()
        )

    def test_company_without_manage_permission_cannot_be_deleted(self):
        employee = get_user_model().objects.create_user(
            email="company-employee@example.test",
            password="Safe-password-2026!",
        )
        employee_role = Role.objects.get(
            organization=self.organization,
            code="employee",
        )
        Membership.objects.create(
            organization=self.organization,
            user=employee,
            role=employee_role,
        )
        self.client.force_authenticate(employee)

        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            Organization.objects.filter(pk=self.organization.pk).exists()
        )

    def test_user_cannot_delete_another_company(self):
        other_owner = get_user_model().objects.create_user(
            email="other-company-owner@example.test",
            password="Safe-password-2026!",
        )
        other_organization = create_organization_for_owner(
            name="Other owner's company",
            actor=other_owner,
        )
        self.client.force_authenticate(self.owner)

        response = self.client.delete(
            f"/api/v1/organizations/{other_organization.id}/"
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            Organization.objects.filter(pk=other_organization.pk).exists()
        )

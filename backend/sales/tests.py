from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate

from audit.models import AuditEvent
from customers.models import Customer
from inventory.models import StockMovement, Warehouse
from organizations.models import AccessPermission, Membership, Organization, Role
from organizations.services import create_organization_for_owner
from organizations.admin import MembershipAdmin, RoleAdmin
from products.models import Product, ProductCategory

from .models import Invoice, InvoiceLine, PaymentCollection
from .views import (
    OrganizationInvoiceDetailView,
    OrganizationInvoiceListCreateView,
    OrganizationInvoicePaymentListCreateView,
)


class SalesAPITests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            email="sales-owner@example.test",
            password="not-a-real-password",
        )
        self.organization = create_organization_for_owner(
            name="Sales Company",
            actor=self.owner,
        )
        self.customer = Customer.objects.create(
            organization=self.organization,
            name="Walk-in Customer",
        )
        self.warehouse = Warehouse.objects.create(
            organization=self.organization,
            name="Main Warehouse",
        )
        self.product = Product.objects.create(
            organization=self.organization,
            name="Coffee",
            sku="COFFEE",
        )
        self.service = Product.objects.create(
            organization=self.organization,
            name="Delivery Service",
            sku="DELIVERY",
            unit=Product.Unit.SERVICE,
        )

    def call_view(self, view, method, *, user=None, data=None, **kwargs):
        user = user or self.owner
        organization_id = kwargs.pop("organization_id", self.organization.id)
        if method == "get":
            request = self.factory.get("/api/v1/sales-test/", data or {})
        else:
            request = self.factory.post(
                "/api/v1/sales-test/",
                data or {},
                format="json",
            )
        force_authenticate(request, user=user)
        response = view.as_view()(
            request,
            organization_id=organization_id,
            **kwargs,
        )
        return response

    def issue_invoice(self, lines, **overrides):
        payload = {
            "customer": str(self.customer.id),
            "warehouse": str(self.warehouse.id),
            "lines": lines,
        }
        payload.update(overrides)
        return self.call_view(
            OrganizationInvoiceListCreateView,
            "post",
            data=payload,
        )

    def collect(self, invoice_id, amount, method="cash", note=""):
        return self.call_view(
            OrganizationInvoicePaymentListCreateView,
            "post",
            invoice_id=invoice_id,
            data={"amount": str(amount), "method": method, "note": note},
        )

    def add_stock(self, product, quantity, warehouse=None):
        return StockMovement.objects.create(
            organization=self.organization,
            warehouse=warehouse or self.warehouse,
            product=product,
            direction=StockMovement.Direction.IN,
            quantity=quantity,
            actor=self.owner,
        )

    def test_issue_calculates_totals_persists_lines_and_decrements_stock(self):
        self.add_stock(self.product, Decimal("10"))

        response = self.issue_invoice(
            [
                {
                    "product": str(self.product.id),
                    "quantity": "2.500",
                    "unit_price": "10.25",
                },
                {
                    "product": str(self.service.id),
                    "quantity": "1.000",
                    "unit_price": "100.99",
                },
            ],
            total="0.01",
        )

        self.assertEqual(response.status_code, 201, response.data)
        invoice = Invoice.objects.get(pk=response.data["id"])
        self.assertRegex(invoice.number, r"^INV-\d{8}-\d{6}$")
        self.assertEqual(invoice.total, Decimal("126.62"))
        self.assertEqual(invoice.actor, self.owner)
        self.assertEqual(invoice.actor_email_snapshot, self.owner.email)
        self.assertEqual(invoice.lines.count(), 2)
        self.assertEqual(
            list(invoice.lines.values_list("line_total", flat=True)),
            [Decimal("25.63"), Decimal("100.99")],
        )
        self.assertEqual(response.data["total"], "126.62")
        self.assertEqual(response.data["balance_due"], Decimal("126.62"))
        second = self.issue_invoice(
            [
                {
                    "product": str(self.service.id),
                    "quantity": "1.000",
                    "unit_price": "1.00",
                }
            ]
        )
        self.assertEqual(second.status_code, 201, second.data)
        self.assertNotEqual(response.data["number"], second.data["number"])
        self.assertTrue(second.data["number"].endswith("000002"))
        self.assertEqual(
            StockMovement.objects.filter(
                organization=self.organization,
                warehouse=self.warehouse,
                product=self.product,
                direction=StockMovement.Direction.OUT,
            ).values_list("quantity", flat=True).get(),
            Decimal("2.500"),
        )
        self.assertFalse(
            StockMovement.objects.filter(
                product=self.service,
                direction=StockMovement.Direction.OUT,
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                actor=self.owner,
                action="sales_invoice.issued",
                entity_id=str(invoice.id),
            ).exists()
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                action="stock_movement.created",
                metadata__invoice_id=str(invoice.id),
            ).count(),
            1,
        )

    def test_insufficient_stock_rejects_issue_without_persisting_anything(self):
        self.add_stock(self.product, Decimal("1.000"))

        response = self.issue_invoice(
            [
                {
                    "product": str(self.product.id),
                    "quantity": "1.001",
                    "unit_price": "4.00",
                }
            ]
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Invoice.objects.count(), 0)
        self.assertEqual(InvoiceLine.objects.count(), 0)
        self.assertEqual(
            StockMovement.objects.filter(direction=StockMovement.Direction.OUT).count(),
            0,
        )
        self.assertFalse(AuditEvent.objects.filter(action="sales_invoice.issued").exists())

    def test_service_invoice_payment_collections_and_overpayment(self):
        created = self.issue_invoice(
            [
                {
                    "product": str(self.service.id),
                    "quantity": "1.000",
                    "unit_price": "100.00",
                }
            ]
        )
        invoice_id = created.data["id"]

        first = self.collect(invoice_id, "40.00", "cash", "counter")
        second = self.collect(invoice_id, "60.00", "bank")
        overpayment = self.collect(invoice_id, "0.01", "card")

        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(overpayment.status_code, 400)
        self.assertEqual(PaymentCollection.objects.count(), 2)
        self.assertEqual(first.data["note"], "counter")
        self.assertEqual(
            AuditEvent.objects.filter(action="sales_payment.collected").count(),
            2,
        )
        detail = self.call_view(
            OrganizationInvoiceDetailView,
            "get",
            pk=invoice_id,
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["amount_collected"], Decimal("100.00"))
        self.assertEqual(detail.data["balance_due"], Decimal("0.00"))
        self.assertEqual(len(detail.data["payments"]), 2)

    def test_payment_requires_positive_amount_and_supported_method(self):
        invoice = self.issue_invoice(
            [
                {
                    "product": str(self.service.id),
                    "quantity": "1.000",
                    "unit_price": "20.00",
                }
            ]
        )

        zero = self.collect(invoice.data["id"], "0.00")
        invalid_method = self.collect(invoice.data["id"], "1.00", "cheque")

        self.assertEqual(zero.status_code, 400)
        self.assertEqual(invalid_method.status_code, 400)
        self.assertEqual(PaymentCollection.objects.count(), 0)

    def test_reads_and_writes_require_separate_sales_permissions_and_active_membership(self):
        invoice = self.issue_invoice(
            [
                {
                    "product": str(self.service.id),
                    "quantity": "1.000",
                    "unit_price": "2.00",
                }
            ]
        )
        employee = get_user_model().objects.create_user(
            email="sales-employee@example.test",
            password="not-a-real-password",
        )
        read_role = Role.objects.create(
            organization=self.organization,
            name="Sales reader",
            code="sales-reader",
        )
        read_role.permissions.add(
            AccessPermission.objects.get(code="sales.read"),
        )
        employee_membership = Membership.objects.create(
            organization=self.organization,
            user=employee,
            role=read_role,
        )
        list_response = self.call_view(
            OrganizationInvoiceListCreateView,
            "get",
            user=employee,
        )
        create_response = self.call_view(
            OrganizationInvoiceListCreateView,
            "post",
            user=employee,
            data={
                "customer": str(self.customer.id),
                "warehouse": str(self.warehouse.id),
                "lines": [
                    {
                        "product": str(self.service.id),
                        "quantity": "1.000",
                        "unit_price": "1.00",
                    }
                ],
            },
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual([item["id"] for item in list_response.data], [invoice.data["id"]])
        self.assertEqual(create_response.status_code, 403)

        employee_membership.is_active = False
        employee_membership.save()
        inactive_response = self.call_view(
            OrganizationInvoiceListCreateView,
            "get",
            user=employee,
        )
        self.assertEqual(inactive_response.status_code, 403)

    def test_cross_company_access_and_references_are_rejected(self):
        other_owner = get_user_model().objects.create_user(
            email="other-sales-owner@example.test",
            password="not-a-real-password",
        )
        other_organization = create_organization_for_owner(
            name="Other Sales Company",
            actor=other_owner,
        )
        other_customer = Customer.objects.create(
            organization=other_organization,
            name="Other Customer",
        )
        other_warehouse = Warehouse.objects.create(
            organization=other_organization,
            name="Other Warehouse",
        )
        other_product = Product.objects.create(
            organization=other_organization,
            name="Other Product",
        )
        foreign_customer = self.call_view(
            OrganizationInvoiceListCreateView,
            "post",
            user=self.owner,
            organization_id=other_organization.id,
            data={
                "customer": str(other_customer.id),
                "warehouse": str(self.warehouse.id),
                "lines": [
                    {
                        "product": str(self.service.id),
                        "quantity": "1.000",
                        "unit_price": "1.00",
                    }
                ],
            },
        )
        self.assertEqual(foreign_customer.status_code, 403)

        self.assertEqual(
            self.issue_invoice(
                [
                    {
                        "product": str(self.service.id),
                        "quantity": "1.000",
                        "unit_price": "1.00",
                    }
                ],
                customer=str(other_customer.id),
            ).status_code,
            400,
        )
        self.assertEqual(
            self.issue_invoice(
                [
                    {
                        "product": str(self.service.id),
                        "quantity": "1.000",
                        "unit_price": "1.00",
                    }
                ],
                warehouse=str(other_warehouse.id),
            ).status_code,
            400,
        )
        self.assertEqual(
            self.issue_invoice(
                [
                    {
                        "product": str(other_product.id),
                        "quantity": "1.000",
                        "unit_price": "1.00",
                    }
                ]
            ).status_code,
            400,
        )
        self.assertEqual(Invoice.objects.count(), 0)

        invoice = self.issue_invoice(
            [
                {
                    "product": str(self.service.id),
                    "quantity": "1.000",
                    "unit_price": "1.00",
                }
            ]
        )
        foreign_detail = self.call_view(
            OrganizationInvoiceDetailView,
            "get",
            user=other_owner,
            organization_id=other_organization.id,
            pk=invoice.data["id"],
        )
        foreign_payments = self.call_view(
            OrganizationInvoicePaymentListCreateView,
            "get",
            user=other_owner,
            organization_id=other_organization.id,
            invoice_id=invoice.data["id"],
        )
        self.assertEqual(foreign_detail.status_code, 404)
        self.assertEqual(foreign_payments.status_code, 404)

    def test_invoice_lines_and_payments_are_append_only(self):
        self.add_stock(self.product, Decimal("1.000"))
        response = self.issue_invoice(
            [
                {
                    "product": str(self.product.id),
                    "quantity": "1.000",
                    "unit_price": "2.00",
                }
            ]
        )
        invoice = Invoice.objects.get(pk=response.data["id"])
        line = invoice.lines.get()

        invoice.total = Decimal("500.00")
        with self.assertRaises(DjangoValidationError):
            invoice.save()
        with self.assertRaises(DjangoValidationError):
            invoice.delete()
        with self.assertRaises(DjangoValidationError):
            line.save()
        with self.assertRaises(DjangoValidationError):
            InvoiceLine.objects.filter(pk=line.pk).update(line_total=Decimal("1.00"))
        with self.assertRaises(DjangoValidationError):
            line.delete()

        payment_response = self.collect(invoice.id, "1.00")
        payment = PaymentCollection.objects.get(pk=payment_response.data["id"])
        self.assertEqual(payment.actor_email_snapshot, self.owner.email)
        payment.amount = Decimal("2.00")
        with self.assertRaises(DjangoValidationError):
            payment.save()
        with self.assertRaises(DjangoValidationError):
            payment.delete()


class PlatformAdminTests(TestCase):
    def test_superuser_can_view_all_companies_accounts_and_read_only_sales(self):
        superuser = get_user_model().objects.create_superuser(
            email="platform-admin@example.test",
            password="Admin-test-password-2026!",
        )
        client = Client()
        client.force_login(superuser)

        for model in (
            get_user_model(),
            Organization,
            Membership,
            Role,
            Customer,
            Product,
            Warehouse,
            StockMovement,
            ProductCategory,
            Invoice,
            InvoiceLine,
            PaymentCollection,
        ):
            with self.subTest(model=model.__name__):
                response = client.get(
                    reverse(
                        f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist"
                    )
                )
                self.assertEqual(response.status_code, 200)
        self.assertTrue(admin.site.is_registered(Invoice))
        self.assertTrue(admin.site.is_registered(Invoice))
        request = RequestFactory().get("/admin/")
        request.user = superuser
        invoice_admin = admin.site._registry[Invoice]
        self.assertFalse(invoice_admin.has_add_permission(request))
        self.assertFalse(invoice_admin.has_delete_permission(request))
        self.assertTrue(superuser.is_platform_owner)

    def test_dashboard_shows_global_metrics_and_recent_activity(self):
        platform_owner = get_user_model().objects.create_superuser(
            email="platform-owner@example.test",
            password="Platform-owner-password-2026!",
        )
        company_user = get_user_model().objects.create_user(
            email="company-owner@example.test",
            password="Company-owner-password-2026!",
        )
        organization = create_organization_for_owner(
            name="Dashboard Company",
            actor=company_user,
        )
        warehouse = Warehouse.objects.create(
            organization=organization,
            name="Main",
        )
        invoice = Invoice.objects.create(
            organization=organization,
            number="INV-DASH-1",
            customer=self._customer(organization),
            warehouse=warehouse,
            total=Decimal("123.45"),
            actor=company_user,
        )
        PaymentCollection.objects.create(
            organization=organization,
            invoice=invoice,
            amount=Decimal("23.45"),
            method=PaymentCollection.Method.CASH,
            actor=company_user,
        )
        AuditEvent.objects.create(
            organization=organization,
            actor=company_user,
            action="test.activity",
            entity_type="test",
            entity_id="dashboard",
        )
        client = Client()
        client.force_login(platform_owner)

        response = client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        dashboard = response.context["platform_dashboard"]
        self.assertEqual(dashboard["organization_count"], 1)
        self.assertEqual(dashboard["user_count"], 2)
        self.assertEqual(dashboard["invoice_count"], 1)
        self.assertEqual(dashboard["invoice_total"], Decimal("123.45"))
        self.assertEqual(dashboard["collection_total"], Decimal("23.45"))
        self.assertTrue(
            any(event.action == "test.activity" for event in dashboard["recent_events"])
        )

    def test_staff_user_without_platform_owner_role_cannot_open_admin(self):
        staff_user = get_user_model().objects.create_user(
            email="company-staff@example.test",
            password="Company-staff-password-2026!",
            is_staff=True,
        )
        self.assertFalse(staff_user.is_platform_owner)
        client = Client()
        client.force_login(staff_user)

        response = client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 403)

    def test_platform_admin_role_and_membership_changes_are_audited(self):
        platform_owner = get_user_model().objects.create_superuser(
            email="owner@example.test",
            password="Platform-owner-password-2026!",
        )
        company_user = get_user_model().objects.create_user(
            email="member@example.test",
            password="Company-member-password-2026!",
        )
        organization = create_organization_for_owner(
            name="Role Audit Company",
            actor=company_user,
        )
        membership = Membership.objects.get(
            organization=organization,
            user=company_user,
        )
        owner_role = organization.roles.get(code="owner")
        reader_role = Role.objects.create(
            organization=organization,
            name="Reader",
            code="reader",
        )
        request = RequestFactory().post("/admin/")
        request.user = platform_owner

        membership.role = reader_role
        membership.is_active = False
        MembershipAdmin(Membership, admin.site).save_model(
            request,
            membership,
            form=None,
            change=True,
        )
        membership_event = AuditEvent.objects.get(
            action="membership.updated",
            entity_id=str(membership.id),
        )
        self.assertEqual(
            membership_event.metadata["changes"],
            {
                "role": {"old": owner_role.code, "new": reader_role.code},
                "is_active": {"old": True, "new": False},
            },
        )

        role = organization.roles.get(code="administrator")
        role.name = "Operations"
        role_admin = RoleAdmin(Role, admin.site)
        role_admin.save_model(request, role, form=None, change=True)
        role.permissions.clear()
        role.permissions.add(AccessPermission.objects.get(code="customers.read"))

        class Form:
            instance = role

            @staticmethod
            def save_m2m():
                return None

        role_admin.save_related(request, Form(), [], change=True)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="role.updated",
                entity_id=str(role.id),
                metadata__changes__name__old="Administrator",
                metadata__changes__name__new="Operations",
            ).exists()
        )
        permission_event = AuditEvent.objects.get(
            action="role.permissions_changed",
            entity_id=str(role.id),
        )
        self.assertIn("customers.read", permission_event.metadata["permissions"]["new"])
        self.assertNotEqual(
            permission_event.metadata["permissions"]["old"],
            permission_event.metadata["permissions"]["new"],
        )

    @staticmethod
    def _customer(organization):
        return Customer.objects.create(
            organization=organization,
            name="Dashboard customer",
        )

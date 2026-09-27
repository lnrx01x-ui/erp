from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from audit.models import AuditEvent
from organizations.models import Membership, Role
from organizations.services import create_organization_for_owner


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

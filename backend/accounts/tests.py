from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from organizations.models import Membership
from organizations.services import create_organization_for_owner


class AuthenticationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = get_user_model().objects.create_user(
            email="owner@example.test",
            password="A-safe-test-password-123",
        )

    def get_csrf_token(self):
        response = self.client.get("/api/v1/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        return response.data["csrfToken"]

    def test_login_requires_csrf_and_returns_authenticated_user(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "A-safe-test-password-123"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

        csrf_token = self.get_csrf_token()
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "A-safe-test-password-123"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_ORIGIN="http://localhost:5173",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["email"], self.user.email)
        self.assertTrue(response.data["csrfToken"])

        current_user = self.client.get("/api/v1/auth/me/")
        self.assertEqual(current_user.status_code, 200)
        self.assertEqual(current_user.data["id"], str(self.user.id))

    def test_login_rejects_an_untrusted_origin(self):
        csrf_token = self.get_csrf_token()
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "A-safe-test-password-123"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_ORIGIN="http://untrusted.example",
        )

        self.assertEqual(response.status_code, 403)

    def test_invalid_credentials_do_not_authenticate(self):
        csrf_token = self.get_csrf_token()
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "incorrect-password"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["detail"], "Email or password is incorrect.")
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 403)

    def test_logout_requires_csrf_and_ends_the_session(self):
        csrf_token = self.get_csrf_token()
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "A-safe-test-password-123"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(login_response.status_code, 200)

        response = self.client.post(
            "/api/v1/auth/logout/",
            {},
            format="json",
            HTTP_X_CSRFTOKEN=login_response.data["csrfToken"],
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 403)

    def test_current_user_returns_profile_and_only_active_memberships(self):
        organization = create_organization_for_owner(
            name="Example Company",
            actor=self.user,
        )
        other_user = get_user_model().objects.create_user(
            email="other@example.test",
            password="Another-safe-password-123",
        )
        create_organization_for_owner(
            name="Other Company",
            actor=other_user,
        )
        self.client.force_authenticate(self.user)

        response = self.client.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(self.user.id))
        self.assertEqual(response.data["email"], self.user.email)
        self.assertEqual(response.data["phone"], "")
        self.assertIn("dateJoined", response.data)
        self.assertEqual(
            response.data["memberships"],
            [
                {
                    "organizationId": str(organization.id),
                    "organizationName": "Example Company",
                    "roleCode": "owner",
                    "roleName": "Owner",
                    "permissions": sorted(
                        organization.roles.get(code="owner").permissions.values_list(
                            "code",
                            flat=True,
                        )
                    ),
                }
            ],
        )

        Membership.objects.filter(user=self.user, organization=organization).update(
            is_active=False
        )
        inactive_response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(inactive_response.data["memberships"], [])

    def test_profile_patch_updates_only_allowed_basic_fields(self):
        self.client.force_authenticate(self.user)

        response = self.client.patch(
            "/api/v1/auth/me/",
            {
                "firstName": "Mahmoud",
                "lastName": "Esmail",
                "phone": " +201000000000 ",
                "email": "changed@example.test",
                "is_staff": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["firstName"], "Mahmoud")
        self.assertEqual(response.data["lastName"], "Esmail")
        self.assertEqual(response.data["phone"], "+201000000000")
        self.assertEqual(response.data["email"], self.user.email)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)

    def test_profile_patch_rejects_phone_values_over_field_limit(self):
        self.client.force_authenticate(self.user)

        response = self.client.patch(
            "/api/v1/auth/me/",
            {"phone": "1" * 41},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("phone", response.data)

    def test_password_change_uses_validators_and_preserves_current_session(self):
        second_client = APIClient(enforce_csrf_checks=True)
        second_csrf_token = second_client.get("/api/v1/auth/csrf/").data["csrfToken"]
        second_login = second_client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "A-safe-test-password-123"},
            format="json",
            HTTP_X_CSRFTOKEN=second_csrf_token,
        )
        self.assertEqual(second_login.status_code, 200)

        csrf_token = self.get_csrf_token()
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "A-safe-test-password-123"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(login_response.status_code, 200)
        csrf_token = login_response.data["csrfToken"]

        weak_password = self.client.post(
            "/api/v1/auth/password/change/",
            {
                "currentPassword": "A-safe-test-password-123",
                "newPassword": "password",
                "confirmNewPassword": "password",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(weak_password.status_code, 400)
        self.assertIn("newPassword", weak_password.data)

        response = self.client.post(
            "/api/v1/auth/password/change/",
            {
                "currentPassword": "A-safe-test-password-123",
                "newPassword": "An-even-safer-password-456",
                "confirmNewPassword": "An-even-safer-password-456",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 200)
        self.assertEqual(second_client.get("/api/v1/auth/me/").status_code, 403)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("An-even-safer-password-456"))
        self.assertTrue(self.user.has_usable_password())

    def test_password_change_rejects_wrong_current_reused_and_mismatched_passwords(self):
        self.client.force_authenticate(self.user)

        wrong_current = self.client.post(
            "/api/v1/auth/password/change/",
            {
                "currentPassword": "wrong-password",
                "newPassword": "Another-safe-password-456",
                "confirmNewPassword": "Another-safe-password-456",
            },
            format="json",
        )
        reused = self.client.post(
            "/api/v1/auth/password/change/",
            {
                "currentPassword": "A-safe-test-password-123",
                "newPassword": "A-safe-test-password-123",
                "confirmNewPassword": "A-safe-test-password-123",
            },
            format="json",
        )
        mismatch = self.client.post(
            "/api/v1/auth/password/change/",
            {
                "currentPassword": "A-safe-test-password-123",
                "newPassword": "Another-safe-password-456",
                "confirmNewPassword": "Different-safe-password-456",
            },
            format="json",
        )

        self.assertEqual(wrong_current.status_code, 400)
        self.assertEqual(reused.status_code, 400)
        self.assertEqual(mismatch.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("A-safe-test-password-123"))

    def test_password_change_requires_authentication(self):
        response = self.client.post(
            "/api/v1/auth/password/change/",
            {
                "currentPassword": "A-safe-test-password-123",
                "newPassword": "Another-safe-password-456",
                "confirmNewPassword": "Another-safe-password-456",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_profile_and_password_changes_require_csrf_for_session_requests(self):
        csrf_token = self.get_csrf_token()
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "A-safe-test-password-123"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(login_response.status_code, 200)

        profile_without_csrf = self.client.patch(
            "/api/v1/auth/me/",
            {"firstName": "Changed"},
            format="json",
        )
        password_without_csrf = self.client.post(
            "/api/v1/auth/password/change/",
            {
                "currentPassword": "A-safe-test-password-123",
                "newPassword": "An-even-safer-password-456",
                "confirmNewPassword": "An-even-safer-password-456",
            },
            format="json",
        )

        self.assertEqual(profile_without_csrf.status_code, 403)
        self.assertEqual(password_without_csrf.status_code, 403)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "")
        self.assertTrue(self.user.check_password("A-safe-test-password-123"))

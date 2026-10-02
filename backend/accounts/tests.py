from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core import mail
from django.test import override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.test import TestCase
from rest_framework.test import APIClient
from urllib.parse import parse_qs, urlparse

from accounts.tokens import email_verification_token_generator
from audit.models import AuditEvent
from organizations.models import Membership
from organizations.services import create_organization_for_owner


class AuthenticationAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = get_user_model().objects.create_user(
            email="owner@example.test",
            password="A-safe-test-password-123",
        )

    def get_csrf_token(self):
        response = self.client.get("/api/v1/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        return response.data["csrfToken"]

    def test_session_status_is_safe_for_authenticated_and_anonymous_sessions(self):
        anonymous = self.client.get("/api/v1/auth/session/")
        self.assertEqual(anonymous.status_code, 200)
        self.assertEqual(anonymous.data, {"authenticated": False})

        self.client.force_authenticate(self.user)
        authenticated = self.client.get("/api/v1/auth/session/")
        self.assertEqual(authenticated.status_code, 200)
        self.assertEqual(authenticated.data, {"authenticated": True})

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
        self.assertEqual(
            self.client.get("/api/v1/auth/session/").data,
            {"authenticated": True},
        )

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

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="no-reply@example.test",
        PUBLIC_APP_URL="https://beta.example.test",
    )
    def test_registration_creates_pending_user_and_sends_verification_email(self):
        csrf_token = self.get_csrf_token()
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "  New.Owner@Example.Test ",
                "firstName": "New",
                "lastName": "Owner",
                "organizationName": "My Restaurant",
                "businessType": "restaurant",
                "countryCode": "SA",
                "password": "Strong-Nasaq-Account-2026!",
                "confirmPassword": "Strong-Nasaq-Account-2026!",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_ORIGIN="http://localhost:5173",
        )

        self.assertEqual(response.status_code, 201, response.data)
        user_model = get_user_model()
        user = user_model.objects.get(email="new.owner@example.test")
        self.assertTrue(user.check_password("Strong-Nasaq-Account-2026!"))
        self.assertFalse(user.is_active)
        self.assertFalse(user.email_verified)
        self.assertIn("افتح رسالة التفعيل", response.data["detail"])
        membership = Membership.objects.get(user=user, is_active=True)
        self.assertEqual(membership.organization.name, "My Restaurant")
        self.assertEqual(membership.organization.business_type, "restaurant")
        self.assertEqual(membership.organization.country_code, "SA")
        self.assertEqual(membership.role.code, "owner")
        self.assertTrue(
            AuditEvent.objects.filter(
                actor=user,
                action="user.registered",
                entity_type="user",
                entity_id=str(user.id),
            ).exists()
        )
        self.assertEqual(
            self.client.get("/api/v1/auth/session/").data,
            {"authenticated": False},
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(user.email, mail.outbox[0].to)
        verification_url = next(
            line
            for line in mail.outbox[0].body.splitlines()
            if "#email_verification=1" in line
        )
        token_data = parse_qs(urlparse(verification_url).fragment)
        self.assertEqual(token_data["email_verification"], ["1"])

        verify = self.client.post(
            "/api/v1/auth/email/verify/",
            {
                "uid": token_data["uid"][0],
                "token": token_data["token"][0],
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_ORIGIN="http://localhost:5173",
        )
        self.assertEqual(verify.status_code, 200, verify.data)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.email_verified)
        self.assertTrue(
            AuditEvent.objects.filter(
                actor=user,
                action="user.email_verified",
            ).exists()
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="no-reply@example.test",
        PUBLIC_APP_URL="https://beta.example.test",
    )
    def test_new_user_must_verify_email_before_login(self):
        registration = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "new.owner@example.test",
                "firstName": "New",
                "organizationName": "My Restaurant",
                "password": "Strong-Nasaq-Account-2026!",
                "confirmPassword": "Strong-Nasaq-Account-2026!",
            },
            format="json",
            HTTP_X_CSRFTOKEN=self.get_csrf_token(),
            HTTP_ORIGIN="http://localhost:5173",
        )
        self.assertEqual(registration.status_code, 201, registration.data)
        user = get_user_model().objects.get(email="new.owner@example.test")

        csrf_token = self.get_csrf_token()
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {
                "email": "NEW.OWNER@EXAMPLE.TEST",
                "password": "Strong-Nasaq-Account-2026!",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_ORIGIN="http://localhost:5173",
        )
        self.assertEqual(login_response.status_code, 401)

        verification = self.client.post(
            "/api/v1/auth/email/verify/",
            {
                "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": email_verification_token_generator.make_token(user),
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_ORIGIN="http://localhost:5173",
        )
        self.assertEqual(verification.status_code, 200, verification.data)

        login_response = self.client.post(
            "/api/v1/auth/login/",
            {
                "email": "NEW.OWNER@EXAMPLE.TEST",
                "password": "Strong-Nasaq-Account-2026!",
            },
            format="json",
            HTTP_X_CSRFTOKEN=self.get_csrf_token(),
            HTTP_ORIGIN="http://localhost:5173",
        )
        self.assertEqual(login_response.status_code, 200, login_response.data)
        self.assertEqual(
            login_response.data["user"]["email"],
            "new.owner@example.test",
        )

        organizations = self.client.get("/api/v1/organizations/")
        self.assertEqual(organizations.status_code, 200, organizations.data)
        self.assertEqual(len(organizations.data), 1)

        logout_response = self.client.post(
            "/api/v1/auth/logout/",
            format="json",
            HTTP_X_CSRFTOKEN=login_response.data["csrfToken"],
            HTTP_ORIGIN="http://localhost:5173",
        )
        self.assertEqual(logout_response.status_code, 204)

    def test_registration_requires_csrf(self):
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "csrf@example.test",
                "firstName": "CSRF",
                "organizationName": "CSRF Restaurant",
                "password": "Strong-Nasaq-Account-2026!",
                "confirmPassword": "Strong-Nasaq-Account-2026!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(get_user_model().objects.filter(email="csrf@example.test").exists())

    def test_registration_rejects_untrusted_origin(self):
        csrf_token = self.get_csrf_token()
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "untrusted@example.test",
                "firstName": "Untrusted",
                "organizationName": "Untrusted Company",
                "password": "Strong-Nasaq-Account-2026!",
                "confirmPassword": "Strong-Nasaq-Account-2026!",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_ORIGIN="http://untrusted.example",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            get_user_model().objects.filter(email="untrusted@example.test").exists()
        )

    def test_registration_is_rate_limited(self):
        cache.clear()
        csrf_token = self.get_csrf_token()
        responses = [
            self.client.post(
                "/api/v1/auth/register/",
                {},
                format="json",
                HTTP_X_CSRFTOKEN=csrf_token,
            )
            for _ in range(6)
        ]

        self.assertEqual([response.status_code for response in responses[:5]], [400] * 5)
        self.assertEqual(responses[5].status_code, 429)

    def test_registration_rejects_duplicate_email_weak_password_and_mismatch(self):
        csrf_token = self.get_csrf_token()
        valid_data = {
            "email": self.user.email.upper(),
            "firstName": "Duplicate",
            "organizationName": "Duplicate Restaurant",
            "password": "Strong-Nasaq-Account-2026!",
            "confirmPassword": "Strong-Nasaq-Account-2026!",
        }
        duplicate = self.client.post(
            "/api/v1/auth/register/",
            valid_data,
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        weak_password = self.client.post(
            "/api/v1/auth/register/",
            {
                **valid_data,
                "email": "weak@example.test",
                "password": "short",
                "confirmPassword": "short",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        mismatched_password = self.client.post(
            "/api/v1/auth/register/",
            {
                **valid_data,
                "email": "mismatch@example.test",
                "confirmPassword": "Different-Password-2026!",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(weak_password.status_code, 400)
        self.assertEqual(mismatched_password.status_code, 400)
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(Membership.objects.count(), 0)

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
        self.assertEqual(
            self.client.get("/api/v1/auth/session/").data,
            {"authenticated": False},
        )

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
                    "businessType": "company",
                    "countryCode": "EG",
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

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="no-reply@example.test",
        PUBLIC_APP_URL="https://beta.example.test",
    )
    def test_password_reset_is_generic_and_sends_single_use_link(self):
        from django.core import mail

        csrf_token = self.get_csrf_token()
        unknown = self.client.post(
            "/api/v1/auth/password/reset/",
            {"email": "unknown@example.test"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_ORIGIN="http://localhost:5173",
        )
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

        request = self.client.post(
            "/api/v1/auth/password/reset/",
            {"email": self.user.email},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_ORIGIN="http://localhost:5173",
        )
        self.assertEqual(request.status_code, 200)
        self.assertEqual(request.data, unknown.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://beta.example.test/#password_reset=1", mail.outbox[0].body)

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        confirm = self.client.post(
            "/api/v1/auth/password/reset/confirm/",
            {
                "uid": uid,
                "token": token,
                "newPassword": "A-new-safe-password-789",
                "confirmPassword": "A-new-safe-password-789",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_ORIGIN="http://localhost:5173",
        )
        self.assertEqual(confirm.status_code, 200, confirm.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("A-new-safe-password-789"))
        self.assertTrue(
            AuditEvent.objects.filter(
                actor=self.user,
                action="user.password_reset",
            ).exists()
        )

        reused_token = self.client.post(
            "/api/v1/auth/password/reset/confirm/",
            {
                "uid": uid,
                "token": token,
                "newPassword": "Another-new-safe-password-890",
                "confirmPassword": "Another-new-safe-password-890",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_ORIGIN="http://localhost:5173",
        )
        self.assertEqual(reused_token.status_code, 400)

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

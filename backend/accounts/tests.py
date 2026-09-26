from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient


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

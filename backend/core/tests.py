from django.test import TestCase
from rest_framework.test import APIClient


class HealthAPITests(TestCase):
    def test_health_endpoint_is_public_and_reports_api_status(self):
        response = APIClient().get("/api/v1/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"status": "ok"})

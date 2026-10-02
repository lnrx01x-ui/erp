from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone


def platform_dashboard(request):
    if (
        request.path != "/admin/"
        or not request.user.is_authenticated
        or not request.user.is_active
        or not request.user.is_superuser
        or not request.user.is_platform_owner
    ):
        return {}

    from accounts.models import User
    from audit.models import AuditEvent
    from organizations.models import Organization
    from sales.models import Invoice, PaymentCollection

    since = timezone.now() - timedelta(days=30)
    return {
        "platform_dashboard": {
            "organization_count": Organization.objects.count(),
            "new_organization_count": Organization.objects.filter(
                created_at__gte=since,
            ).count(),
            "user_count": User.objects.count(),
            "new_user_count": User.objects.filter(date_joined__gte=since).count(),
            "invoice_count": Invoice.objects.count(),
            "invoice_total": (
                Invoice.objects.aggregate(total=Sum("total"))["total"]
                or 0
            ),
            "collection_total": (
                PaymentCollection.objects.aggregate(
                    total=Sum("amount")
                )["total"]
                or 0
            ),
            "recent_events": AuditEvent.objects.select_related(
                "actor",
                "organization",
            )[:20],
        }
    }

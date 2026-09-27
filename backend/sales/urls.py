from django.urls import path

from .views import (
    OrganizationInvoiceDetailView,
    OrganizationInvoiceListCreateView,
    OrganizationInvoicePaymentListCreateView,
)


urlpatterns = [
    path(
        "organizations/<uuid:organization_id>/sales-invoices/",
        OrganizationInvoiceListCreateView.as_view(),
        name="organization-sales-invoice-list",
    ),
    path(
        "organizations/<uuid:organization_id>/sales-invoices/<uuid:pk>/",
        OrganizationInvoiceDetailView.as_view(),
        name="organization-sales-invoice-detail",
    ),
    path(
        "organizations/<uuid:organization_id>/sales-invoices/<uuid:invoice_id>/payments/",
        OrganizationInvoicePaymentListCreateView.as_view(),
        name="organization-sales-invoice-payment-list",
    ),
]

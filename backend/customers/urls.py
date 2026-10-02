from django.urls import path

from .views import OrganizationCustomerDetailView, OrganizationCustomerListCreateView


urlpatterns = [
    path(
        "organizations/<uuid:organization_id>/customers/",
        OrganizationCustomerListCreateView.as_view(),
        name="organization-customer-list",
    ),
    path(
        "organizations/<uuid:organization_id>/customers/<uuid:pk>/",
        OrganizationCustomerDetailView.as_view(),
        name="organization-customer-detail",
    ),
]

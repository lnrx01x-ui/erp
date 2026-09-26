from django.urls import path

from .views import OrganizationCustomerListCreateView


urlpatterns = [
    path(
        "organizations/<uuid:organization_id>/customers/",
        OrganizationCustomerListCreateView.as_view(),
        name="organization-customer-list",
    ),
]

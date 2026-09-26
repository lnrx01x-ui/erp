from django.urls import path

from .views import OrganizationProductListCreateView


urlpatterns = [
    path(
        "organizations/<uuid:organization_id>/products/",
        OrganizationProductListCreateView.as_view(),
        name="organization-product-list",
    ),
]

from django.urls import path

from .views import (
    OrganizationProductCategoryListCreateView,
    OrganizationProductDetailView,
    OrganizationProductListCreateView,
)


urlpatterns = [
    path(
        "organizations/<uuid:organization_id>/product-categories/",
        OrganizationProductCategoryListCreateView.as_view(),
        name="organization-product-category-list",
    ),
    path(
        "organizations/<uuid:organization_id>/products/",
        OrganizationProductListCreateView.as_view(),
        name="organization-product-list",
    ),
    path(
        "organizations/<uuid:organization_id>/products/<uuid:pk>/",
        OrganizationProductDetailView.as_view(),
        name="organization-product-detail",
    ),
]

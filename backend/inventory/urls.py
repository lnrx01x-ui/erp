from django.urls import path

from .views import (
    OrganizationStockBalanceListView,
    OrganizationStockMovementListCreateView,
    OrganizationWarehouseDetailView,
    OrganizationWarehouseListCreateView,
)


urlpatterns = [
    path(
        "organizations/<uuid:organization_id>/warehouses/",
        OrganizationWarehouseListCreateView.as_view(),
        name="organization-warehouse-list",
    ),
    path(
        "organizations/<uuid:organization_id>/warehouses/<uuid:pk>/",
        OrganizationWarehouseDetailView.as_view(),
        name="organization-warehouse-detail",
    ),
    path(
        "organizations/<uuid:organization_id>/stock-movements/",
        OrganizationStockMovementListCreateView.as_view(),
        name="organization-stock-movement-list",
    ),
    path(
        "organizations/<uuid:organization_id>/stock-balances/",
        OrganizationStockBalanceListView.as_view(),
        name="organization-stock-balance-list",
    ),
]

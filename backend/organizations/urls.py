from django.urls import path

from .views import (
    OrganizationDeleteView,
    OrganizationListCreateView,
    OrganizationMembershipListView,
    OrganizationRoleListView,
)


urlpatterns = [
    path("organizations/", OrganizationListCreateView.as_view(), name="organization-list"),
    path(
        "organizations/<uuid:organization_id>/",
        OrganizationDeleteView.as_view(),
        name="organization-delete",
    ),
    path(
        "organizations/<uuid:organization_id>/members/",
        OrganizationMembershipListView.as_view(),
        name="organization-members",
    ),
    path(
        "organizations/<uuid:organization_id>/roles/",
        OrganizationRoleListView.as_view(),
        name="organization-roles",
    ),
]

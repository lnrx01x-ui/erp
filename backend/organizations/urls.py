from django.urls import path

from .views import (
    OrganizationListCreateView,
    OrganizationMembershipListView,
    OrganizationRoleListView,
)


urlpatterns = [
    path("organizations/", OrganizationListCreateView.as_view(), name="organization-list"),
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

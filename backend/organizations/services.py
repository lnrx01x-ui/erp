from django.db import transaction
from django.utils.text import slugify

from audit.models import AuditEvent

from .models import AccessPermission, Membership, Organization, Role


PERMISSIONS = (
    ("organization.manage", "Manage organization"),
    ("users.manage", "Manage users"),
    ("roles.manage", "Manage roles"),
    ("customers.read", "View customers"),
    ("customers.manage", "Manage customers"),
    ("products.read", "View products"),
    ("products.manage", "Manage products"),
    ("sales.read", "View sales"),
    ("sales.manage", "Manage sales"),
    ("purchases.read", "View purchases"),
    ("purchases.manage", "Manage purchases"),
    ("inventory.read", "View inventory"),
    ("inventory.manage", "Manage inventory"),
    ("accounting.read", "View accounting"),
    ("accounting.manage", "Manage accounting"),
    ("audit.read", "View audit events"),
)


@transaction.atomic
def create_organization_for_owner(*, name, actor):
    organization = Organization.objects.create(name=name.strip())
    permission_objects = [
        AccessPermission.objects.get_or_create(code=code, defaults={"name": label})[0]
        for code, label in PERMISSIONS
    ]

    owner_role = Role.objects.create(
        organization=organization,
        name="Owner",
        code="owner",
        is_system=True,
    )
    owner_role.permissions.set(permission_objects)
    administrator_role = Role.objects.create(
        organization=organization,
        name="Administrator",
        code="administrator",
        is_system=True,
    )
    administrator_role.permissions.set(
        permission for permission in permission_objects if permission.code != "organization.manage"
    )
    Role.objects.create(
        organization=organization,
        name="Employee",
        code="employee",
        is_system=True,
    )
    Membership.objects.create(
        organization=organization,
        user=actor,
        role=owner_role,
    )
    AuditEvent.objects.create(
        organization=organization,
        actor=actor,
        action="organization.created",
        entity_type="organization",
        entity_id=str(organization.id),
        metadata={"name": organization.name},
    )
    return organization

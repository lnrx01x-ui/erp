# M1 — Current architecture baseline

This document records the architecture that exists today. It is a description
of the working baseline, not a proposal to replace it. M1 established the
baseline without runtime changes. M2 added only the user profile and password
foundation documented here; the original session authentication and CSRF
behavior remain intact.

## System shape

The application is a modular monolith with two local development processes:

```text
Browser
  React + TypeScript + Vite (localhost:5173)
       │ same-origin /api requests through the Vite development proxy
       ▼
  Django + Django REST Framework (localhost:8000)
       │ Django ORM and migrations
       ▼
  SQLite (local default) or PostgreSQL (DATABASE_URL)
```

Backend responsibilities are divided into Django apps:

| App | Current responsibility |
| --- | --- |
| `accounts` | UUID, email-based identity and basic profile; CSRF bootstrap and session login, logout, current-user, and password-change APIs |
| `organizations` | Tenant records, memberships, organization roles, permission catalog, and organization API |
| `customers` | Customer records scoped to an organization |
| `products` | Product/service catalog scoped to an organization |
| `audit` | Organization-scoped audit events |
| `core` | Public health endpoint |

The frontend is a single React application. Its Vite proxy forwards `/api`
requests to Django during local development. The frontend is not a second
authorization boundary; Django is authoritative for identity, membership,
permissions, validation, and tenant scope.

## Existing database model

```text
User ──< Membership >── Organization ──< Role >──< AccessPermission
                            │
                            ├──< Customer
                            ├──< Product
                            └──< AuditEvent >── User (actor, nullable)
```

- A user can have memberships in multiple organizations.
- A user profile has an optional phone field; first/last name and date joined
  use existing Django user fields. Email remains the unique login identity.
- A membership is unique per `(organization, user)`, can be deactivated, and
  points to a role belonging to that organization.
- A role's permission codes come from a shared permission catalog; the role
  itself belongs to one organization.
- Customer and product records each have a required organization foreign key.
- Product SKU is unique within an organization when non-empty. Sale and cost
  amounts use fixed-precision decimals and database non-negative constraints.
- The audit actor is nullable so events can remain attributable when an account
  is removed. The organization is protected from deletion while audit events
  refer to it.
- Django migrations are the schema history. SQLite is the local default;
  PostgreSQL is selected through `DATABASE_URL`.

In the current implementation, `Organization` is the tenant/company boundary.
Branches and warehouses are not separate database entities yet. Currency,
tax policy, product stock balances, sales, purchases, and accounting entries
are also not modeled yet.

## Authentication and request authorization

1. Django authenticates users by unique, normalized email and stores browser
   authentication in a Django session.
2. The frontend obtains a CSRF token before login and sends `X-CSRFToken` with
   login and other state-changing requests. Django's CSRF middleware remains
   enabled.
3. Passwords use Django's configured password hashers. A password change
   verifies the current password, runs the configured Django validators, and
   rejects reusing the current password. Rotating the current session auth hash
   preserves the current session while invalidating sessions with stale hashes.
4. Organization listing uses the authenticated user's active memberships.
   Organization creation assigns the creator the owner role in the same
   transaction that creates its roles and audit event.
5. Customer and product endpoints require an active membership in the URL's
   organization and the matching organization-role permission.
6. Tenant-scoped reads filter by both organization ID and the requesting
   user's active membership. The organization ID supplied in a URL is a
   selector, not proof of authorization.
7. Customer/product creation derives the organization from the authenticated
   membership, validates input on the server, and writes an audit event in the
   same database transaction.
8. The current-user response includes only the caller's active memberships and
   the assigned role and permission codes. Authorized members can read the
   selected organization's memberships with `users.manage` and role catalog
   with `roles.manage`; these endpoints do not support writes.

Tenant isolation is currently enforced by Django view querysets and permission
checks. PostgreSQL Row-Level Security is **not** enabled. Do not add a
tenant-scoped endpoint without an active-membership check, an organization
filter on every read, and a server-derived organization on writes.

## API contract in the baseline

All application API routes use `/api/v1/`.

| Route | Behavior |
| --- | --- |
| `GET /health/` | Public liveness response |
| `GET /auth/csrf/` | Initialize a CSRF-protected browser session |
| `POST /auth/login/` | CSRF-protected email/password session login |
| `POST /auth/logout/` | CSRF-protected session logout |
| `GET /auth/me/` | Return the authenticated profile and active memberships |
| `PATCH /auth/me/` | Update first name, last name, and phone; identity and access fields remain read-only |
| `POST /auth/password/change/` | Verify current password and validators before changing password |
| `GET /organizations/` | List organizations with the user's active memberships |
| `POST /organizations/` | Create an organization and its initial owner/membership |
| `GET /organizations/{id}/customers/` | List customers with `customers.read` |
| `POST /organizations/{id}/customers/` | Create a customer with `customers.manage` |
| `GET /organizations/{id}/products/` | List products with `products.read` |
| `POST /organizations/{id}/products/` | Create a product with `products.manage` |
| `GET /organizations/{id}/members/` | List memberships, assigned roles, and permissions with `users.manage` |
| `GET /organizations/{id}/roles/` | List organization roles and permission descriptions with `roles.manage` |

There is no public self-registration endpoint. The first local user is created
with Django's `createsuperuser` command.

## Data change and compatibility rules

The established local database and its data are part of the baseline.

- Do not delete, reset, recreate, or replace the database to develop a feature.
- Treat migrations already applied to a user's database as immutable history.
- For required schema changes, add an additive, forward migration. Backfill
  existing rows before making a populated column mandatory; use a reversible
  operation where practical.
- Do not rename/remove API fields, change session/CSRF behavior, or modify
  existing role semantics as incidental cleanup.
- Keep business rules in the backend. A successful screen render alone does
  not make a feature complete.
- Each feature should include database constraints where appropriate, API and
  permission tests, tenant-isolation tests, and a frontend build.
- Run the existing backend suite before and after the feature tests. Investigate
  any baseline regression before continuing.

## Known boundaries (not claims of production readiness)

- The audit model rejects ordinary ORM updates/deletes and the Django admin is
  read-only for events. This is application-level protection, not an
  immutable database ledger; a database administrator can still alter rows.
- There are currently no customer or product update/archive endpoints,
  employee invitation flow, role/membership write-management API, sales,
  purchase, stock, accounting, or reporting workflows.
- Product prices have two decimal places, but a company currency and exchange
  rate model have not been decided.
- PostgreSQL is supported by settings and the Psycopg dependency, but current
  tests run on SQLite; production behavior, backup/restore, deployment,
  monitoring, and a full security review remain future work.
- Permissions are organization-scoped at the role/membership layer. The
  permission definitions are shared records and are not separate per tenant.

## M1 baseline and M2 outcome

M1 records the working architecture and non-negotiable compatibility rules.
The first M2 slice adds optional phone data through an additive migration,
editable basic profile fields, active-membership context, and validated
password changes. The next slice adds read-only organization membership and
role/permission listings, guarded by the existing organization-scoped
permissions. It does not replace session authentication, change the membership
or role models, or provide invitations and write-management actions. Further
work is paused for review. Before a later sales workflow, agree whether its
first version is a quotation, an order, or an issued invoice; those are
different business documents and have different stock and accounting
consequences.

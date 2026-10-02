# نسق — Architecture and current delivery scope

This document records the architecture that exists today. It is a description
of the working baseline and the current MVP, not a proposal to replace it. M1
established the baseline without runtime changes. M2 added the user profile,
password, and read-only membership foundations; later MVP slices added
products, inventory, sales invoices, and collections. Session authentication
and CSRF behavior remain intact.

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
| `accounts` | UUID, email-based identity and basic profile; explicit platform-owner flag; CSRF bootstrap and session login, logout, current-user, and password-change APIs |
| `organizations` | Tenant records, memberships, organization roles, permission catalog, and organization API |
| `customers` | Customer records scoped to an organization |
| `products` | Product/service catalog scoped to an organization |
| `inventory` | Warehouses, append-only stock movements, calculated balances |
| `sales` | Issued sales invoices, immutable invoice lines, and collections |
| `audit` | Append-only organization-scoped and platform-wide audit events |
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
                            ├──< ProductCategory ──< Product
                            ├──< Product (optional category)
                            ├──< Warehouse ──< StockMovement >── Product
                            ├──< Invoice ──< InvoiceLine >── Product
                            │       └──< PaymentCollection
                            └──< AuditEvent >── User (actor, nullable)
```

- A user can have memberships in multiple organizations.
- Each organization is explicitly typed as a general company or restaurant and
  configured for Egypt or Saudi Arabia. This classifies onboarding only; local
  tax/e-invoicing rules and restaurant-specific operations are not implemented
  by these fields.
- A user profile has an optional phone field; first/last name and date joined
  use existing Django user fields. Email remains the unique login identity.
- A membership is unique per `(organization, user)`, can be deactivated, and
  points to a role belonging to that organization.
- A role's permission codes come from a shared permission catalog; the role
  itself belongs to one organization.
- Customer and product records each have a required organization foreign key.
- Product categories belong to one organization and have case-insensitively
  unique names within that organization. A product's category is optional so
  existing and newly created uncategorized products remain valid.
- Warehouses belong to one organization. Stock movements are append-only,
  require positive quantities and same-company warehouse/product references;
  balances are calculated from the movement ledger and stock cannot go below
  zero.
- Issued invoices and their lines are immutable; their totals are calculated
  server-side. Issuing an invoice records stock-out movements for stocked
  products, while service lines do not affect inventory.
- Payment collections are append-only and cannot exceed the invoice's
  remaining balance. Customer, warehouse, product, invoice, and collection
  references are scoped to the same organization.
- Product SKU is unique within an organization when non-empty. Sale and cost
  amounts use fixed-precision decimals and database non-negative constraints.
- The audit actor is nullable so events can remain attributable when an account
  is removed. Audit events retain organization ID/name snapshots and are
  detached from a company if it is deleted; actor email snapshots remain when
  an account is deleted. Ordinary audit changes/deletes are blocked, while
  deletion may only null the organization/actor foreign keys.
- Django migrations are the schema history. SQLite is the local default;
  PostgreSQL is selected through `DATABASE_URL`.

In the current implementation, `Organization` is the tenant/company boundary.
Warehouses are organization-scoped, but branches are not separate database
entities. Currency configuration, tax policy, purchases, and accounting entries
are not modeled yet.

## Authentication and request authorization

1. Django authenticates users by unique, normalized email and stores browser
   authentication in a Django session.
   Platform operators have an independent `is_platform_owner` account flag;
   it is not a company role and does not grant membership-based API access.
   `createsuperuser` sets this flag and the initial migration promotes existing
   superusers. The admin middleware denies non-platform-owner accounts access
   to `/admin/`.
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
5. Customer, product, inventory, and sales endpoints require an active
   membership in the URL's organization and the matching organization-role
   permission.
6. Tenant-scoped reads filter by both organization ID and the requesting
   user's active membership. The organization ID supplied in a URL is a
   selector, not proof of authorization.
7. Resource creation derives the organization from the authenticated
   membership, validates input on the server, and writes audit events within
   the same database transaction. Invoice issue and collection also update
   their related ledgers atomically.
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
| `GET /auth/session/` | Return only whether the current session is authenticated |
| `POST /auth/login/` | CSRF-protected email/password session login |
| `POST /auth/logout/` | CSRF-protected session logout |
| `GET /auth/me/` | Return the authenticated profile and active memberships |
| `PATCH /auth/me/` | Update first name, last name, and phone; identity and access fields remain read-only |
| `POST /auth/password/change/` | Verify current password and validators before changing password |
| `GET /organizations/` | List organizations with the user's active memberships |
| `POST /organizations/` | Create an organization and its initial owner/membership |
| `PATCH /organizations/{id}/` | Update the company name with `organization.manage` |
| `DELETE /organizations/{id}/` | Permanently delete a company only when it has no invoices or stock movements; audit snapshots remain |
| `GET /organizations/{id}/customers/` | List customers with `customers.read` |
| `POST /organizations/{id}/customers/` | Create a customer with `customers.manage` |
| `PATCH /organizations/{id}/customers/{customer_id}/` | Update a customer with `customers.manage` |
| `DELETE /organizations/{id}/customers/{customer_id}/` | Permanently delete an unreferenced customer; returns `409` when invoices protect it |
| `GET /organizations/{id}/products/` | List products with `products.read` |
| `POST /organizations/{id}/products/` | Create a product with `products.manage` |
| `PATCH /organizations/{id}/products/{product_id}/` | Update a product in the organization with `products.manage` |
| `DELETE /organizations/{id}/products/{product_id}/` | Permanently delete an unreferenced product; returns `409` when invoices or stock movements protect it |
| `GET /organizations/{id}/product-categories/` | List organization product categories with `products.read` |
| `POST /organizations/{id}/product-categories/` | Create an organization product category with `products.manage` |
| `GET /organizations/{id}/warehouses/` | List warehouses with `inventory.read` |
| `POST /organizations/{id}/warehouses/` | Create a warehouse with `inventory.manage` |
| `GET /organizations/{id}/stock-movements/` | List stock ledger entries with `inventory.read` |
| `POST /organizations/{id}/stock-movements/` | Record a stock-in or stock-out movement with `inventory.manage` |
| `GET /organizations/{id}/stock-balances/` | Calculate warehouse/product balances with `inventory.read` |
| `GET /organizations/{id}/sales-invoices/` | List issued invoices, lines, collections, and balances with `sales.read` |
| `POST /organizations/{id}/sales-invoices/` | Issue an invoice, calculate its total, and record stock-out with `sales.manage` |
| `GET /organizations/{id}/sales-invoices/{invoice_id}/` | Read a company-scoped invoice with `sales.read` |
| `GET /organizations/{id}/sales-invoices/{invoice_id}/payments/` | List collections with `sales.read` |
| `POST /organizations/{id}/sales-invoices/{invoice_id}/payments/` | Record a collection not exceeding the remaining due with `sales.manage` |
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
  read-only for events. Company deletion detaches audit events while retaining
  immutable organization ID/name and actor email snapshots. The platform
  dashboard summarizes all tenants and shows recent activity; admin lists
  expose all accounts, companies, memberships, roles, customers, products,
  warehouses, invoices, collections, stock movements, and audit events.
  Financial records, stock ledger rows, and audit events are read-only in
  admin. This is application-level protection, not an immutable database
  ledger; a database administrator can still alter rows.
- Customer and product records can be permanently deleted only when no
  protected business history references them. Organization deletion is blocked
  when invoices or stock movements exist.
- There are currently no employee invitation flow, role/membership
  write-management API, restaurant POS/table/menu/recipe/kitchen/shift modules,
  purchases, accounting postings, VAT/e-invoicing, refunds, or reconciliation.
  Sales reporting is limited to issued invoice totals and their collections.
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
or role models, or provide invitations and write-management actions. The
current MVP issues invoices directly; quotations and order lifecycles remain
out of scope because they have different stock and accounting consequences.

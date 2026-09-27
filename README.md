# ERP

A private, modular-monolith ERP foundation using Django REST Framework, PostgreSQL, React, and TypeScript.

## Current scope

- Custom email-based user model.
- Basic user profile with first/last name and optional phone.
- CSRF-protected profile updates and password changes using Django's password validators.
- Organizations with organization-scoped roles and permissions.
- Active memberships as the tenant boundary.
- Organization-scoped API listing and organization creation.
- Organization-scoped customer listing and creation with tenant permissions.
- Organization-scoped product catalogs with unique per-company SKUs, unit of measure, and decimal prices.
- Read-only organization member listings with assigned roles and permissions, plus a read-only role catalog.
- Append-only audit events for organization creation.
- CSRF-protected session login/logout, current-user, and password-change endpoints.
- A React dashboard for signing in, managing organizations, customers, products, and account settings, and viewing organization members and roles.
- SQLite fallback for zero-cost local development; PostgreSQL is the intended database and can be selected with `DATABASE_URL`.

This is a starting foundation, not a production-ready ERP. Public registration, operational modules, deployment, backups, and a production security review are not included yet.

## Architecture

The verified baseline, current data model, tenant authorization boundary, and
safe-change rules are documented in [M1 — Current architecture baseline](./docs/architecture.md).

```text
frontend/  React + TypeScript + Vite
    │      /api is proxied to Django during local development
backend/   Django REST API
    ├── accounts        Custom user identity and session authentication
    ├── organizations   Tenants, memberships, roles, permissions
    ├── customers       Organization-scoped customer directory
    ├── products        Organization-scoped product/service catalog
    ├── audit            Append-only audit events
    └── core             Health endpoint and shared API setup
    │
    └── PostgreSQL (target) / SQLite (local fallback)
```

The app is a modular monolith. Tenant-aware APIs must scope every read and write through the authenticated user's active membership; a client-supplied organization ID alone is never authorization.

## Local development

### Backend

Requires Python 3.10 or later.

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r ..\requirements.txt
py manage.py migrate
py manage.py createsuperuser
py manage.py runserver
```

The API health endpoint is `http://127.0.0.1:8000/api/v1/health/`. Django admin is at `http://127.0.0.1:8000/admin/`. Local development uses SQLite unless `DATABASE_URL` points to PostgreSQL. When changing the frontend origin or Vite port, update `DJANGO_CSRF_TRUSTED_ORIGINS` to the exact local browser origin and restart Django.

To use PostgreSQL, create a database and set `DATABASE_URL`, for example:

```powershell
$env:DATABASE_URL = "postgresql://erp:your-local-password@localhost:5432/erp"
```

Copy `.env.example` as a reference. Django settings currently read environment variables directly; they do not load a `.env` file automatically. Never use the example development secret outside local development.

### Frontend

Requires Node.js 20.19+ or 22.12+.

```powershell
cd frontend
npm install
npm run dev
```

Vite proxies `/api` requests to `http://127.0.0.1:8000`.

## API

- `GET /api/v1/health/` — liveness check.
- `GET /api/v1/auth/csrf/` — initialize a CSRF-protected browser session.
- `POST /api/v1/auth/login/` — log in with email and password plus an `X-CSRFToken` header.
- `POST /api/v1/auth/logout/` — end the authenticated session plus an `X-CSRFToken` header.
- `GET /api/v1/auth/me/` — return the current authenticated user's profile and active organization memberships with assigned roles and permissions.
- `PATCH /api/v1/auth/me/` — update first name, last name, and phone; email and access fields are read-only.
- `POST /api/v1/auth/password/change/` — change password after verifying the current password and configured Django validators; preserves the current session and invalidates sessions with stale password hashes.
- `GET /api/v1/organizations/` — organizations for the authenticated user's active memberships only.
- `POST /api/v1/organizations/` — create an organization; the authenticated creator is assigned its owner role and membership.
- `GET /api/v1/organizations/{organization_id}/customers/` — list customers if the active organization role grants `customers.read`.
- `POST /api/v1/organizations/{organization_id}/customers/` — create a customer and audit event if the active organization role grants `customers.manage`.
- `GET /api/v1/organizations/{organization_id}/products/` — list products if the active organization role grants `products.read`.
- `POST /api/v1/organizations/{organization_id}/products/` — create a product and audit event if the active organization role grants `products.manage`.
- `GET /api/v1/organizations/{organization_id}/members/` — list organization memberships, assigned roles, and permissions if the active role grants `users.manage`.
- `GET /api/v1/organizations/{organization_id}/roles/` — list that organization's roles and permission descriptions if the active role grants `roles.manage`.

The product catalog stores product/service details, SKU, unit, sale price, and cost price. Inventory quantities and movements are deliberately handled by the future inventory module.

API authentication uses Django sessions and CSRF protection for login and other state-changing requests. Passwords are hashed by Django and checked against the configured validators on password change. Create the first user with `createsuperuser`, then sign in through the frontend; user self-registration and membership write-management are intentionally not enabled. Profile endpoints never accept email, role, membership, or permission changes.

Organization member and role endpoints are read-only. They enforce the requested company's active-membership permission server-side; no invitations, membership changes, or role/permission edits are available.

## Dependency and IP hygiene

Review each direct and transitive dependency, version, license, and applicable notice before distribution. The current direct dependencies are Django, Django REST Framework, and Psycopg on the backend, and React, React DOM, Vite, TypeScript, and the React Vite plugin on the frontend. Keep dependency lockfiles and third-party notices current before any commercial release.

This project does not grant an open-source license to the ERP code. That does not change third-party license obligations or establish legal ownership by itself. Record contributor agreements and get local legal advice before an IP transfer.

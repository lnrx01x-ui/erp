# نسق | Nasaq

نسق منصة عربية لإدارة الأعمال، مبنية كتطبيق modular monolith باستخدام Django REST Framework وPostgreSQL وReact وTypeScript.

## Current scope

- Custom email-based user model.
- Basic user profile with first/last name and optional phone.
- CSRF-protected profile updates and password changes using Django's password validators.
- Organizations with organization-scoped roles and permissions.
- Organization setup records whether the business is a restaurant or a general company, and whether it operates in Egypt or Saudi Arabia.
- Active memberships as the tenant boundary.
- Organization-scoped API listing and organization creation.
- Organization-scoped customer listing and creation with tenant permissions.
- Organization-scoped product catalogs with unique per-company SKUs, unit of measure, and decimal prices.
- Optional organization-scoped product categories, assignable to products without changing existing uncategorized products.
- Organization-scoped warehouses and an append-only stock movement ledger with calculated balances.
- Organization-scoped sales invoices with server-calculated totals, stock deduction on issue, and append-only payment collections that reject overpayment.
- A basic sales report showing invoice totals, collected amounts, and outstanding balances.
- Read-only organization member listings with assigned roles and permissions, plus a read-only role catalog.
- Append-only audit events for organization creation, stock movements, invoice issue, and collections.
- CSRF-protected session login/logout, current-user, and password-change endpoints.
- CSRF-protected password-reset requests with single-use, expiring tokens and SMTP delivery.
- Public account registration that creates a typed company/restaurant in Egypt or Saudi Arabia; email verification is optional and disabled by default, while registration and verification resend remain rate-limited.
- A React dashboard for signing in, managing organizations, customers, products, inventory, sales invoices, collections, and account settings, and viewing organization members and roles.
- SQLite fallback for zero-cost local development; PostgreSQL is the intended database and can be selected with `DATABASE_URL`.

نسق موجّه لفرق الأعمال الصغيرة والمتوسطة. الميزات غير المدرجة ضمن النطاق الحالي لا تُعرض كأنها جاهزة، ويلزم قبل البيع التجاري إكمال التحقق القانوني والتشغيلي والأمني الموضح لاحقًا.

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
    ├── inventory       Organization warehouses, stock movements and balances
    ├── sales           Issued invoices, sales lines and collections
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

### Platform administrator

Create the platform administrator account interactively from the backend folder:

```powershell
py manage.py createsuperuser
```

Enter an email address and a strong, unique password at the private terminal
prompt; do not put the password in source control or chat. Sign in at
`http://127.0.0.1:8000/admin/`. `createsuperuser` creates a distinct Platform
Owner account (`is_platform_owner`), separate from every company membership
role. Existing superusers are marked as platform owners by the migration.
Authenticated staff who are not platform owners are denied access to `/admin/`.

The admin home shows platform-wide company/user counts, new registrations,
invoice totals, collections, and the latest audit events. The searchable
admin lists cover accounts (including membership/company roles, registration
creator, status, and last login), companies (creator and active member count),
memberships, roles, customers, products, warehouses, invoices, invoice lines,
collections, stock movements, and audit events. Financial documents, stock
ledger entries, and audit events are read-only. Platform edits to users,
companies, memberships, roles, customers, products, and warehouses create
audit entries; audit changes include old/new values where the operation
supports them. Audit events preserve actor and company identity snapshots if
either record is later deleted.

Only grant this account to a trusted platform operator and use the production
HTTPS admin URL after deployment. Platform totals currently aggregate stored
amounts without currency conversion; multi-currency reporting must wait for
currency configuration.

To use PostgreSQL, create a database and set `DATABASE_URL`, for example:

```powershell
$env:DATABASE_URL = "postgresql://erp:your-local-password@localhost:5432/erp"
```

Copy `.env.example` as a reference. Django settings read environment variables directly; they do not load a `.env` file automatically. Never use the example development secret outside local development.

### Frontend

Requires Node.js 20.19+ or 22.12+.

```powershell
cd frontend
npm install
npm run dev
```

Vite proxies `/api` requests to `http://127.0.0.1:8000`.

## Render + Supabase deployment

The repository root contains `render.yaml` for one Render web service. Django
serves the Vite-built React app from `/`, the API from `/api/v1/`, and hashed
frontend assets through WhiteNoise from `/static/`. This keeps session cookies
and CSRF same-origin; the Vite proxy is used only for local development.

For a Render Blueprint, create the service from this repository and fill the
values marked as unsynced in the Render dashboard. Or create a **Web Service**
manually with the repository root as its root directory and these commands:

**Build Command**

```sh
pip install -r requirements.txt && npm ci --prefix frontend && npm run build --prefix frontend && python backend/manage.py collectstatic --noinput
```

**Start Command**

```sh
cd backend && python manage.py migrate --noinput && python manage.py createcachetable django_cache && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

The start command runs from the repository root, changes into `backend/`, and
starts `config.wsgi:application` with Gunicorn. Do not change the working
directory to `backend/` in Render's Root Directory setting.

Set these values in Render's environment dashboard; never commit their real
values:

- `DJANGO_DEBUG=False` and `DJANGO_SECRET_KEY` (Render can generate the key).
- `DJANGO_REQUIRE_EMAIL_VERIFICATION=False` for immediate account activation
  without a verification email (the beta default).
- `DJANGO_ALLOWED_HOSTS` to the exact assigned Render hostname, without a
  scheme, for example `your-service.onrender.com`.
- `DJANGO_CSRF_TRUSTED_ORIGINS` and `PUBLIC_APP_URL` to the HTTPS site origin,
  for example `https://your-service.onrender.com`.
- `DJANGO_BEHIND_TRUSTED_HTTPS_PROXY=True`; Render terminates HTTPS before
  forwarding requests to the service.
- `DATABASE_URL` copied from the Supabase PostgreSQL connection settings.
  Keep SSL enabled; the application rejects a production URL with
  `sslmode=disable`.
- Working SMTP settings (`DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_HOST_USER`,
  `DJANGO_EMAIL_HOST_PASSWORD`, and `DJANGO_DEFAULT_FROM_EMAIL`) so account
  password-reset messages can be delivered. If the SMTP username is an email
  address, it is used as the default sender unless you set
  `DJANGO_DEFAULT_FROM_EMAIL` explicitly.

The database URL and SMTP credentials belong only in Render's secret
environment settings, not in `render.yaml`, `.env.example`, or Git. Check
Supabase's current connection guidance for the selected network/IP support and
pooler mode; use a connection string compatible with Django and Psycopg.

Render/Supabase free-plan availability, sleeping/cold starts, quotas, and
backup/restore guarantees depend on the providers' current terms. Confirm a
successful Supabase backup and perform a restore drill before storing real
business data. A successful deployment build alone does not prove SMTP,
database recovery, or production readiness.

## API

- `GET /api/v1/health/` — liveness check.
- `GET /api/v1/auth/csrf/` — initialize a CSRF-protected browser session.
- `GET /api/v1/auth/session/` — check whether the current browser session is authenticated without requesting protected profile data.
- `POST /api/v1/auth/login/` — log in with email and password plus an `X-CSRFToken` header.
- `POST /api/v1/auth/register/` — create a user and their first organization (`businessType`: `company` or `restaurant`; `countryCode`: `EG` or `SA`); by default, starts a session immediately, while optional email verification can be enabled; requires CSRF and is rate-limited.
- `POST /api/v1/auth/email/verify/` — activate the account using the expiring, single-use `uid` and `token` from the verification email.
- `POST /api/v1/auth/email/resend-verification/` — request another verification email; responds generically and is rate-limited.
- `POST /api/v1/auth/logout/` — end the authenticated session plus an `X-CSRFToken` header.
- `GET /api/v1/auth/me/` — return the current authenticated user's profile and active organization memberships with assigned roles and permissions.
- `PATCH /api/v1/auth/me/` — update first name, last name, and phone; email and access fields are read-only.
- `POST /api/v1/auth/password/change/` — change password after verifying the current password and configured Django validators; preserves the current session and invalidates sessions with stale password hashes.
- `POST /api/v1/auth/password/reset/` — request a password-reset email; replies generically whether or not the address is registered and is rate-limited.
- `POST /api/v1/auth/password/reset/confirm/` — set a new password using the expiring, single-use `uid` and `token` from the email.
- `GET /api/v1/organizations/` — organizations for the authenticated user's active memberships only.
- `POST /api/v1/organizations/` — create an organization (`business_type`: `company` or `restaurant`; `country_code`: `EG` or `SA`); the authenticated creator is assigned its owner role and membership.
- `PATCH /api/v1/organizations/{organization_id}/` — update the company name with `organization.manage`.
- `DELETE /api/v1/organizations/{organization_id}/` — permanently delete a company if it has no invoices or stock movements; audit events retain immutable organization snapshots.
- `GET /api/v1/organizations/{organization_id}/customers/` — list customers if the active organization role grants `customers.read`.
- `POST /api/v1/organizations/{organization_id}/customers/` — create a customer and audit event if the active organization role grants `customers.manage`.
- `PATCH /api/v1/organizations/{organization_id}/customers/{customer_id}/` — update a customer with `customers.manage`.
- `DELETE /api/v1/organizations/{organization_id}/customers/{customer_id}/` — permanently delete an unreferenced customer; linked invoices prevent deletion.
- `GET /api/v1/organizations/{organization_id}/products/` — list products if the active organization role grants `products.read`.
- `POST /api/v1/organizations/{organization_id}/products/` — create a product and audit event if the active organization role grants `products.manage`.
- `PATCH /api/v1/organizations/{organization_id}/products/{product_id}/` — update an existing company's product if the active role grants `products.manage`.
- `DELETE /api/v1/organizations/{organization_id}/products/{product_id}/` — permanently delete an unreferenced product; invoices and stock movements prevent deletion.
- `GET /api/v1/organizations/{organization_id}/product-categories/` — list company product categories if the active role grants `products.read`.
- `POST /api/v1/organizations/{organization_id}/product-categories/` — create a company product category and audit event if the active role grants `products.manage`.
- `GET /api/v1/organizations/{organization_id}/warehouses/` — list company warehouses if the active role grants `inventory.read`.
- `POST /api/v1/organizations/{organization_id}/warehouses/` — create a warehouse if the active role grants `inventory.manage`.
- `GET /api/v1/organizations/{organization_id}/stock-movements/` — list append-only stock movements if the active role grants `inventory.read`.
- `POST /api/v1/organizations/{organization_id}/stock-movements/` — record a positive stock-in or stock-out movement if the active role grants `inventory.manage`; stock-out cannot exceed the calculated balance.
- `GET /api/v1/organizations/{organization_id}/stock-balances/` — calculate balances from movement history if the active role grants `inventory.read`.
- `GET /api/v1/organizations/{organization_id}/sales-invoices/` — list issued invoices, lines, collections, and balances if the active role grants `sales.read`.
- `POST /api/v1/organizations/{organization_id}/sales-invoices/` — issue an invoice with server-calculated totals and stock deduction if the active role grants `sales.manage`.
- `GET /api/v1/organizations/{organization_id}/sales-invoices/{invoice_id}/` — read one company invoice and its collection balance if the active role grants `sales.read`.
- `GET /api/v1/organizations/{organization_id}/sales-invoices/{invoice_id}/payments/` — list append-only collections if the active role grants `sales.read`.
- `POST /api/v1/organizations/{organization_id}/sales-invoices/{invoice_id}/payments/` — collect against an invoice without exceeding its due balance if the active role grants `sales.manage`.
- `GET /api/v1/organizations/{organization_id}/members/` — list organization memberships, assigned roles, and permissions if the active role grants `users.manage`.
- `GET /api/v1/organizations/{organization_id}/roles/` — list that organization's roles and permission descriptions if the active role grants `roles.manage`.

The product catalog stores product/service details, optional category, SKU, unit, sale price, and cost price. Current inventory is calculated from append-only movements by product and warehouse.

### Demo walkthrough

1. Sign in with the local administrator account and create/select a company.
2. Add a customer, product (or service), and warehouse. A product category is optional.
3. In inventory, record an opening stock-in for the product.
4. Open sales, issue an invoice for the customer from that warehouse, and verify the stock balance decreases.
5. Record a partial collection, then collect the remaining balance. Confirm the invoice summary shows the updated collected and due amounts.
6. Attempting to collect more than the due balance is rejected by the server.

The first sales slice issues invoices directly; it does not include quotations, VAT/e-invoicing, refunds, credit notes, accounting postings, or payment reconciliation. Use fictitious or customer-approved data in demonstrations; no sample credentials or seeded customer data are included.

Amounts are displayed with Egyptian-pound formatting for the local MVP; per-company currency configuration and exchange rates are not implemented.

API authentication uses Django sessions and CSRF protection for login and other state-changing requests. Passwords are hashed by Django and checked against the configured validators during registration and password changes. By default, self-registered accounts are activated immediately without email verification; set `DJANGO_REQUIRE_EMAIL_VERIFICATION=True` to require confirmation. `createsuperuser` and accounts created by a platform owner are provisioned as verified. Membership write-management is not enabled. Profile endpoints never accept email, role, membership, or permission changes.

Self-registration is open to all users and creates a separate tenant for each new account. Password reset uses expiring, single-use tokens and still requires production SMTP. Email ownership verification can be enabled with `DJANGO_REQUIRE_EMAIL_VERIFICATION=True`; it is disabled by default for the beta.

Organization member and role endpoints are read-only. They enforce the requested company's active-membership permission server-side; no invitations, membership changes, or role/permission edits are available.

## Public deployment readiness

This repository is not deployed to a public host. Before an Internet launch:

1. Provision a web host with HTTPS and managed PostgreSQL. Serve the built frontend and `/api/` from the same HTTPS site, or configure the exact cross-origin cookies/CSRF origins. Never expose Django's development server or local SQLite database.
2. Add production environment variables in the host's secret manager: `DJANGO_DEBUG=False`, a newly generated `DJANGO_SECRET_KEY`, exact `DJANGO_ALLOWED_HOSTS`, HTTPS `DJANGO_CSRF_TRUSTED_ORIGINS`, HTTPS `PUBLIC_APP_URL`, and the managed PostgreSQL `DATABASE_URL`. Production rejects SQLite, wildcard hosts, non-HTTPS app URLs, and disabled PostgreSQL SSL.
3. Configure a production SMTP relay using `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT`, `DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD`, and `DJANGO_DEFAULT_FROM_EMAIL`; never use the console email backend in production. Verification and password-reset links use the configured HTTPS app URL and single-use tokens.
4. Run `python manage.py migrate` and `python manage.py createcachetable` during release setup. Production throttling uses Django's database cache so limits are shared across app workers; the cache table must exist before registration/login traffic.
5. Configure automatic encrypted PostgreSQL backups with a documented retention policy in the provider. Confirm a recent successful snapshot in its dashboard, restore it to a separate temporary database, run the app's data checks against that restored copy, then remove the temporary database. A backup is not verified until this restore drill succeeds.
6. Set `DJANGO_BEHIND_TRUSTED_HTTPS_PROXY=True` only if the hosting proxy strips/overwrites `X-Forwarded-Proto`; never trust a client-controlled forwarded header.
7. Run `python manage.py check --deploy` and validate sign-up, email verification, login, password reset, cross-company denial, backup restoration, and HTTPS cookies on the deployed beta before inviting users.

No backup, HTTPS certificate, SMTP delivery, database, domain, or beta deployment is provisioned or verifiable from this repository alone. The current beta allows open registration; limit access by only sharing the beta URL if you want a small tester group. Do not place production secrets in Git or send them in chat. The free local-development setup does not imply zero-cost public hosting.

## Dependency and IP hygiene

Review each direct and transitive dependency, version, license, and applicable notice before distribution. The current direct dependencies are Django, Django REST Framework, and Psycopg on the backend, and React, React DOM, Vite, TypeScript, and the React Vite plugin on the frontend. Keep dependency lockfiles and third-party notices current before any commercial release.

This project does not grant an open-source license to the ERP code. That does not change third-party license obligations or establish legal ownership by itself. Record contributor agreements and get local legal advice before an IP transfer.

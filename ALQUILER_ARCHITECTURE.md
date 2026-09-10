# ALQUILER — Architecture Blueprint

> **Authoritative architectural reference** for the Alquiler rental management SaaS platform.
> Created: 2026-09-09 | Last updated: 2026-09-09 (Phase 10C)

---

## 1. Product Overview

**Alquiler** is a Django 5.2 + DRF rental management SaaS backend built for the Nigerian (NGN) market. The platform serves three user roles:

- **Landlord** — Manages properties, units, tenants, leases, and rent collection
- **Tenant** — Views leases, makes payments, receives notifications
- **Platform Admin** — Oversees platform-wide metrics, user management, and system health

Tenant rent payments and SaaS subscription billing are entirely separate financial domains.

---

## 2. Complete System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Super User  │  │   Landlord   │  │    Tenant     │  │
│  │   Web App     │  │   Mobile App │  │    (TBD)      │  │
│  │   (Planned)   │  │   (Planned)  │  │              │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
└─────────┼──────────────────┼──────────────────┼──────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────┐
│                    API LAYER                             │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Django REST Framework (Token Auth)              │   │
│  │  drf-spectacular (OpenAPI 3.0)                   │   │
│  │  Rate Limiting (Scoped Throttling)               │   │
│  └──────────────────────┬───────────────────────────┘   │
└──────────────────────────┼───────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                 APPLICATION LAYER                        │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Django 5.2 (8 apps + config)                    │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐    │   │
│  │  │  core  │ │properties│ │tenants │ │ leases │    │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘    │   │
│  │  ┌────────┐ ┌────────┐ ┌──────────┐ ┌────────┐  │   │
│  │  │payments│ │notifications│ │subscriptions│ │dashboard│  │   │
│  │  └────────┘ └────────┘ └──────────┘ └────────┘  │   │
│  └──────────────────────┬───────────────────────────┘   │
└──────────────────────────┼───────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  PostgreSQL  │  │    Redis     │  │    gunicorn   │
│  16-alpine   │  │   7-alpine   │  │  (workers)    │
│  (Primary DB)│  │  (Cache/Future)│ │  (HTTP)       │
└──────────────┘  └──────────────┘  └──────────────┘
```

---

## 3. Backend Architecture

### 3.1 Django Apps

| App | Purpose | Models | Key Services |
|-----|---------|--------|--------------|
| `core` | Auth, user model, permissions, exceptions | User, AuditLog, NotificationPreference | send_email(), custom exception handler |
| `properties` | Property and unit management | Property, Unit | Subscription limit enforcement |
| `tenants` | Tenant invitations and profiles | TenantProfile, TenantInvitation | Invitation lifecycle |
| `leases` | Lease lifecycle and scheduling | Lease | create_lease, edit_lease, renew_lease, terminate_lease |
| `payments` | Payment recording and rent tracking | Payment, RentSchedule | generate_schedule, period_status, record/update/cancel_payment |
| `notifications` | Idempotent notification generation | Notification | generate_lease/rent_notifications, send_email |
| `subscriptions` | SaaS billing and plan management | Plan, Subscription | upgrade/downgrade/cancel, trial expiry, quota enforcement |
| `dashboard` | Analytics and CSV exports | (no models) | landlord_metrics, tenant_metrics, admin_metrics |
| `platform_admin` | Platform operations console | (no models) | AdminUserViewSet, AdminPropertyViewSet, AdminSubscriptionViewSet, AdminIssuesView |
| `config` | Settings and URL routing | (no models) | settings.py, urls.py |

### 3.2 Authentication & Authorization

- **Auth Method:** Token-based (DRF TokenAuthentication), email-based login
- **Token Expiry:** ExpiringTokenAuthentication (tokens expire after configurable period)
- **Roles:** LANDLORD, TENANT, PLATFORM_ADMIN (stored in DB, never client-declared)
- **Permissions:**
  - `IsPlatformAdmin` — PLATFORM_ADMIN only
  - `IsLandlord` — LANDLORD only
  - `IsTenant` — TENANT only
  - `IsLandlordOrAdmin` — LANDLORD or PLATFORM_ADMIN
- **Data Isolation:** All queries scoped to requesting user's role and ownership

### 3.3 Serialization & Validation

- DRF serializers with nested relationships
- Custom validation for business rules (lease overlap, payment consistency, subscription limits)
- `@extend_schema` decorators on all endpoints for OpenAPI documentation

### 3.4 Services Layer

Business logic extracted into service functions (not views):
- `leases/services.py` — Lease lifecycle operations
- `payments/services.py` — Payment recording and financial calculations
- `notifications/services.py` — Idempotent notification generation
- `subscriptions/services.py` — Subscription lifecycle and quota enforcement
- `dashboard/services.py` — Analytics aggregation and CSV export

---

## 4. Database Architecture

### 4.1 Entity-Relationship Diagram

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│     User     │────<│  AuditLog    │     │ Notification │
│              │     │              │     │   Preference │
│  id (PK)     │     │  user_id(FK) │     │  user_id(FK) │
│  email (UQ)  │     │  action      │     │  email_en    │
│  role        │     │  resource    │     │  in_app_en   │
│  status      │     │  timestamp   │     └──────────────┘
└──────┬───────┘     └──────────────┘
       │
       │ 1:1
       ├──────────────────────────────────────────────┐
       │                                              │
       ▼                                              ▼
┌──────────────┐                             ┌──────────────┐
│ TenantProfile│                             │ Subscription │
│              │                             │              │
│  user_id(FK) │                             │  landlord_id │
│  notes       │                             │  plan_id(FK) │
└──────────────┘                             │  status      │
                                             │  billing     │
┌──────────────┐                             └──────────────┘
│   Plan       │                                     │
│              │                                     │
│  tier        │                                     │
│  max_tenants │                                     │
│  max_props   │                                     │
│  price_ngn   │                                     │
└──────────────┘                                     │
       ▲                                             │
       └─────────────────────────────────────────────┘
       │
┌──────┴───────┐     ┌──────────────┐     ┌──────────────┐
│  Property    │────<│     Unit     │     │    Lease     │
│              │     │              │     │              │
│  landlord_id │     │  property_id │     │  landlord_id │
│  name        │     │  name        │     │  tenant_id   │
│  type        │     │  status      │     │  property_id │
│  status      │     └──────────────┘     │  unit_id     │
│  city/state  │                          │  start/expiry│
└──────────────┘                          │  rent_amount │
                                          │  frequency   │
                                          └──────┬───────┘
                                                 │
                    ┌────────────────────────────┼─────────────────┐
                    │                            │                 │
                    ▼                            ▼                 ▼
             ┌──────────────┐            ┌──────────────┐  ┌──────────────┐
             │ TenantInvit. │            │ RentSchedule │  │  Payment     │
             │              │            │              │  │              │
             │  landlord_id │            │  lease_id    │  │  lease_id    │
             │  email       │            │  period_start│  │  rent_period │
             │  token (UQ)  │            │  period_end  │  │  amount      │
             │  status      │            │  due_date    │  │  status      │
             │  property_id │            │  amount      │  │  method      │
             │  unit_id     │            └──────────────┘  └──────────────┘
             └──────────────┘
```

### 4.2 Key Relationships

| Relationship | Type | FK Field | Cascade |
|--------------|------|----------|---------|
| User → AuditLog | One-to-Many | `auditlog.user_id` | CASCADE |
| User → NotificationPreference | One-to-One | `notificationpreference.user_id` | CASCADE |
| User → TenantProfile | One-to-One | `tenantprofile.user_id` | CASCADE |
| User → Subscription | One-to-One | `subscription.landlord_id` | CASCADE |
| Plan → Subscription | One-to-Many | `subscription.plan_id` | PROTECT |
| Property → Unit | One-to-Many | `unit.property_id` | CASCADE |
| User → Property | One-to-Many | `property.landlord_id` | CASCADE |
| User → Lease | One-to-Many | `lease.landlord_id` | PROTECT |
| Lease → RentSchedule | One-to-Many | `rentschedule.lease_id` | CASCADE |
| Lease → Payment | One-to-Many | `payment.lease_id` | PROTECT |
| RentSchedule → Payment | One-to-Many | `payment.rent_period_id` | SET_NULL |

### 4.3 Constraints & Indexes

**Constraints:**
- `currency_iso3` — Currency must be valid 3-letter ISO code
- `rent_due_day_range` — Day must be 1-31
- `amount_gte_0` — Payment/rent amounts non-negative
- `expiry_gte_start` — Lease expiry must be after start date
- `period_end_gte_start` — RentSchedule period_end must be after period_start
- `unique_together (property, name)` — Unit names unique per property
- `unique_together (lease, due_date)` — One rent schedule per lease per due date

**Indexes:**
- `property (landlord + status)` — Fast landlord property listing
- `unit (property + status)` — Fast property unit listing
- `lease (landlord + status)` — Fast landlord lease listing
- `lease (tenant + status)` — Fast tenant lease listing
- `notification (recipient + is_read)` — Fast unread notification count
- `notification (recipient + notification_type)` — Fast type-filtered listing
- `notification (status + scheduled_for)` — Fast scheduled notification queries

---

## 5. Financial Architecture

### 5.1 Rent Schedules

- Generated from lease terms (rent_amount, rent_frequency, rent_due_day)
- Frequencies: MONTHLY, QUARTERLY, BI_ANNUALLY, ANNUALLY
- Due day clamped to month length (e.g., 31 → 28/29 for February)
- Idempotent generation (replaces existing schedules on lease edit)
- Partial periods at lease end are intentionally NOT created

### 5.2 Payments

- Manual recording (no Paystack integration yet)
- Methods: BANK_TRANSFER, CASH, CARD, OTHER
- Statuses: PAID, PENDING, FAILED, CANCELLED
- Amount ceiling: 50,000,000 NGN (serializer-level validation)
- Row-level locking for all mutations (prevents concurrent overwrites)

### 5.3 Financial Invariant

```python
paid_amount = SUM(Payment.amount WHERE rent_period=period AND status=PAID)
remaining_amount = max(period.amount - paid_amount, 0)
```

- **Never store a redundant balance field** — always compute from payment records
- Rent-period status is **derived** from the aggregate — never client-supplied
- All payment mutations use `select_for_update()` inside `transaction.atomic()`

### 5.4 Concurrency Handling

- Two-period locks acquired in ascending PK order to prevent deadlocks
- `update_payment()` with rent_period change: locks old and new periods, recalculates both
- `cancel_payment()` recalculates period aggregate after cancellation

### 5.5 Rent Period Status (Derived)

| Status | Condition |
|--------|-----------|
| UPCOMING | `due_date > today` |
| DUE | `due_date <= today` AND no payments |
| PARTIALLY_PAID | `0 < paid_amount < amount` |
| PAID | `paid_amount >= amount` |
| OVERDUE | `due_date < today` AND `paid_amount < amount` |

---

## 6. Subscription Architecture

### 6.1 Plans

| Tier | Max Tenants | Max Properties | Price (NGN) |
|------|-------------|----------------|-------------|
| FREE | 1 | 1 | 0 |
| PROFESSIONAL | 10 | 5 | 15,000 |
| BUSINESS | 50 | 20 | 45,000 |

### 6.2 Subscription Lifecycle

```
TRIAL ──────┬──> ACTIVE ──────┬──> PAST_DUE
            │                  │
            ├──> CANCELLED     ├──> CANCELLED
            │                  │
            └──> EXPIRED       └──> EXPIRED

ACTIVE ──> CANCELLED ──> ACTIVE (reactivate)
EXPIRED ──> ACTIVE (reactivate)
```

### 6.3 Enforcement Rules

- Subscription status checked before property/tenant/lease creation
- Only TRIAL and ACTIVE subscriptions can create resources
- Downgrade allowed (existing resources preserved, limits enforced on new creations)
- Plan deactivation is soft-delete (`is_active=False`)
- Plans with active subscriptions cannot be hard-deleted

### 6.4 Trial Management

- Configurable duration via `TRIAL_DURATION_DAYS` env var (default: 14)
- Paid-plan trials auto-expire to EXPIRED
- FREE plan trial never expires

---

## 7. Super User Web Application

**Status:** Phase 10B COMPLETE — Platform Analytics & Business Intelligence

### 7.1 Frontend Technology Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Framework | React | 19.x | UI library |
| Language | TypeScript | 6.x | Type safety |
| Bundler | Vite | 8.x | Build tool |
| Routing | react-router-dom | 7.x | Client-side routing |
| HTTP Client | Axios | 1.x | API communication |
| Icons | lucide-react | 1.x | UI icons |
| Charts | recharts | 2.x | Data visualization |
| CSS | Tailwind CSS | 4.x | Utility-first styling |
| Testing | Vitest + Testing Library | 5.x / 16.x | Unit/integration tests |

### 7.2 Frontend Architecture

```
frontend/
├── src/
│   ├── api/           # API client layer
│   │   ├── client.ts  # Axios instance with auth injection
│   │   ├── auth.ts    # Auth API calls
│   │   ├── dashboard.ts # Dashboard & admin API calls
│   │   └── types.ts   # TypeScript interfaces
│   ├── components/    # Reusable UI components
│   │   ├── Layout.tsx         # App shell (sidebar + header)
│   │   ├── ProtectedRoute.tsx # Auth guard + role enforcement
│   │   ├── LoadingSpinner.tsx
│   │   ├── EmptyState.tsx
│   │   ├── ErrorState.tsx
│   │   └── MetricCard.tsx
│   ├── contexts/      # React contexts
│   │   └── AuthContext.tsx    # Auth state + PLATFORM_ADMIN guard
│   ├── pages/         # Page components
│   │   ├── LoginPage.tsx
│   │   ├── DashboardPage.tsx  # Real admin metrics
│   │   ├── UsersPage.tsx      # Backend gap placeholder
│   │   ├── PropertiesPage.tsx # Backend gap placeholder
│   │   ├── LeasesPage.tsx     # Real lease data
│   │   ├── PaymentsPage.tsx   # Real payment data
│   │   ├── SubscriptionsPage.tsx # Real plan data
│   │   ├── NotificationsPage.tsx
│   │   ├── HealthPage.tsx
│   │   └── NotFoundPage.tsx
│   ├── test/          # Test files
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── vite.config.ts
├── vitest.config.ts
└── package.json
```

### 7.3 Platform Admin Dashboard

**Implemented (Phase 10B — comprehensive platform analytics):**

*KPIs:* User counts by role and status (active/suspended), property counts, unit occupancy (occupied/vacant/rate), lease status breakdown (active/expiring/expired/terminated/future), collected rent with period comparison and growth %, outstanding rent, overdue rent, subscription distribution by plan tier and status, system health.

*Charts:* User growth (12-month line), property/unit growth (12-month line), payment volume (12-month bar), subscription distribution (donut/pie).

*Features:* Date period filtering (All Time/7d/30d/90d/12m), manual refresh, loading/error states, responsive layout.

**Backend analytics:**
- `GET /api/v1/dashboard/admin/` — Comprehensive platform KPIs with date filtering
- `GET /api/v1/dashboard/admin/export/` — CSV export
- All queries use database aggregation (annotated SUM with FILTER — no N+1)
- Growth trends use `TruncMonth` for efficient monthly grouping

**Platform Operations Console (Phase 10C):**

The Super User dashboard was extended into a full Safe Platform Operations & Administration Console with read-only access to platform-wide data:

*Backend endpoints (all PLATFORM_ADMIN enforced, read-only):*
- `GET /api/v1/admin/users/` — User listing with search, role/status filters, pagination
- `GET /api/v1/admin/users/{id}/` — User detail with recent leases and payments
- `GET /api/v1/admin/properties/` — Property listing with search, landlord/type/status filters, unit occupancy annotations
- `GET /api/v1/admin/properties/{id}/` — Property detail with units list
- `GET /api/v1/admin/subscriptions/` — Subscription listing with search, plan/status filters
- `GET /api/v1/admin/issues/` — Operational issues aggregation (failed payments, overdue rent, expired leases, suspended users, expired/past-due subscriptions)

*Frontend pages:*
- `UsersPage` — User management with search, role/status filters, detail panel
- `PropertiesPage` — Property management with search, type/status filters, unit occupancy display
- `LeasesPage` — Lease listing with search, status filter, detail panel
- `PaymentsPage` — Payment listing with search, status filter, detail panel
- `SubscriptionsPage` — Subscription listing with search, plan/status filters, detail panel
- `IssuesPage` — Operational issues dashboard with severity filtering and summary cards

*Shared components:* `DataTable`, `SearchInput`, `FilterSelect`, `Pagination`, `StatusBadge`, `DetailPanel`

**Remaining Phase 10 work:**
- Plan management UI (create, update, deactivate)
- Recent activity feed
- Audit log listing

### 7.4 Security (Implemented)

- Token-based authentication with localStorage persistence
- PLATFORM_ADMIN role enforcement on frontend (backend is the real guard)
- Non-admin users redirected to login on role mismatch
- Token validated against backend on mount (getCurrentUser)
- Automatic token cleanup on 401 responses
- No secrets exposed in frontend code
- API proxy through Vite dev server (hides backend URL)
- All admin analytics endpoints require PLATFORM_ADMIN permission

### 7.5 Backend Gaps Identified

The following backend capabilities are still missing for full Super User functionality:

| Gap | Required For | Status |
|-----|-------------|--------|
| User suspend/reactivate | User management | Not implemented |
| Audit log listing endpoint | Activity feed | Not implemented |
| Recent activity feed | Dashboard | Not implemented |

*Note:* Occupied/vacant unit breakdown, overdue rent totals, growth metrics, subscription plan breakdown, and period collected rent comparison are all now implemented via the enhanced `admin_metrics` endpoint.

---

## 8. Landlord Mobile Application (Planned)

**Status:** PLANNED — Technology TBD

### 8.1 Core Features

- Property and unit management
- Tenant invitation and management
- Lease creation and renewal
- Payment recording and tracking
- Notification viewing and preferences
- Dashboard with collected rent/occupancy KPIs

### 8.2 Backend Support (Implemented)

- All landlord-scoped ViewSets with Token auth
- Data isolation (landlord sees only their data)
- Subscription limit enforcement
- CSV export capability

### 8.3 Technology Decision (Pending)

- **Options:** React Native, Flutter, native iOS/Android
- **Decision deferred** until backend is stable and API patterns are finalized

---

## 9. Tenant Experience

### 9.1 Backend Capabilities (Implemented)

| Capability | Endpoint | Status |
|------------|----------|--------|
| View own leases | `GET /api/v1/leases/` | ✅ Implemented |
| View payment schedule | `GET /api/v1/payments/schedule/` | ✅ Implemented |
| Record payments (self) | `POST /api/v1/payments/` | ✅ Implemented |
| View notifications | `GET /api/v1/notifications/` | ✅ Implemented |
| Mark notifications read | `POST /api/v1/notifications/{id}/mark-read/` | ✅ Implemented |
| Update preferences | `PATCH /api/v1/notifications/preferences/` | ✅ Implemented |
| Dashboard KPIs | `GET /api/v1/dashboard/tenant/` | ✅ Implemented |

### 9.2 Planned Client

- **Status:** PLANNED — Technology TBD
- **Options:** Web app, mobile app, or both
- **Decision deferred** until backend API is finalized

---

## 10. Notifications Architecture

### 10.1 Notification Types (15)

**Lease Reminders (7):**
- `LEASE_EXPIRY_30D` / `7D` / `DAY` — Before expiry
- `LEASE_EXPIRY_7D_AFTER` / `14D_AFTER` / `21D_AFTER` / `28D_AFTER` — After expiry

**Rent Reminders (6):**
- `RENT_UPCOMING_7D` / `3D` / `DAY` — Before due date
- `RENT_OVERDUE_3D` / `7D` / `14D` — After due date

**Invitation (2):**
- `INVITATION_SENT` / `INVITATION_ACCEPTED`

### 10.2 Idempotent Generation

- Deterministic keys from `recipient + type + channel + date + resource`
- `channel` parameter ensures IN_APP and EMAIL get distinct keys
- Date-only extraction ensures same-day runs produce identical keys
- `create_notification()` returns `_created` flag (bool) for callers

### 10.3 Preference Respect

- Email/in-app toggles checked before creating each notification
- Terminated leases excluded from rent notifications
- Only ACTIVE leases generate rent reminders
- Only unpaid/partially-paid periods generate rent reminders

### 10.4 Management Commands

- `send_rent_notifications` — supports `--today YYYY-MM-DD` and `--send-emails`
- `send_lease_notifications` — supports `--today YYYY-MM-DD` and `--send-emails`

---

## 11. Security Architecture

### 11.1 Authentication

- Token-based (DRF TokenAuthentication)
- Expiring tokens (configurable TTL)
- Email-based login (no username)

### 11.2 Rate Limiting

- `ConditionalScopedRateThrottle` — per-user, per-scope limits
- Throttled responses include `Retry-After` header (ceiling of seconds)

### 11.3 Security Headers (Planned)

- HSTS, CSRF, XSS protection, content-type sniffing prevention
- Configured in `config/settings.py` for production

### 11.4 CORS

- Configurable allowed origins via `CORS_ALLOWED_ORIGINS` env var
- Defaults to localhost for development

### 11.5 Error Handling

- Custom exception handler absorbs unexpected errors (no stack traces leaked)
- Consistent `{detail, code, errors?}` envelope
- DomainError, ForbiddenError, NotFoundError, ConflictError

---

## 12. Infrastructure

### 12.1 Docker Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| web | Custom Django | 8000 | Application server |
| db | postgres:16-alpine | 5432 | Primary database |
| redis | redis:7-alpine | 6379 | Cache / future queue |

### 12.2 Gunicorn Configuration

- Configurable via env vars: `GUNICORN_WORKERS`, `GUNICORN_TIMEOUT`, etc.
- Security limits: `GUNICORN_LIMIT_REQUEST_LINE`, `GUNICORN_LIMIT_REQUEST_FIELDS`
- Config file: `gunicorn.conf.py`

### 12.3 Health Checks

- **Endpoint:** `GET /api/v1/auth/health/`
- **Response:** `{"status": "healthy", "database": "ok"}`
- **Auth:** Unauthenticated (no token required)
- **Docker:** Health check every 30s, 10s timeout, 3 retries

### 12.4 Volumes

- `postgres_data` — Database persistence
- `redis_data` — Cache persistence
- `static_files` — Collected static files
- `media_files` — User uploads

### 12.5 Environment Configuration

- `.env.example` — Template with all required variables
- `.env` — Local overrides (not committed)
- Key vars: `DB_*`, `REDIS_URL`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CORS_*`

---

## 13. API Architecture

### 13.1 Versioning

- URL-based: `/api/v1/`
- All endpoints prefixed with `API_PREFIX` setting

### 13.2 Endpoint Summary

| Group | Endpoints | Auth Required |
|-------|-----------|---------------|
| Auth | 8 | Mixed |
| Properties | 5 | Landlord/Admin |
| Tenants | 5 | Landlord/Tenant |
| Leases | 6 | Landlord/Tenant |
| Payments | 6 | Landlord/Tenant |
| Payment Schedule | 1 | Landlord/Tenant |
| Notifications | 6 | Own only |
| Subscriptions | 7 | Landlord/Admin |
| Dashboard | 5 | Role-gated |
| Health | 1 | None |

### 13.3 Error Format

```json
{
  "detail": "Error message",
  "code": "error_code",
  "errors": {}  // Optional, for validation errors
}
```

### 13.4 Pagination

- `PageNumberPagination`
- Default page size: 20
- Max page size: 100
- Response: `{count, next, previous, results}`

### 13.5 OpenAPI Documentation

- Generated by `drf-spectacular`
- Schema: `/api/schema/`
- Swagger UI: `/api/docs/`
- Redoc: `/api/redoc/`
- Enum name overrides configured to prevent collisions

---

## 14. End-to-End Data Flows

### 14.1 Property Creation

```
Landlord → POST /api/v1/properties/
  → Subscription limit check (assert_can_add_property)
  → Property.objects.create()
  → Return PropertySerializer(instance)
```

### 14.2 Lease Creation

```
Landlord → POST /api/v1/leases/
  → Subscription limit check (assert_can_add_lease_tenant)
  → Overlap detection (has_conflicting_active_lease)
  → Unit availability check
  → Lease.objects.create()
  → generate_schedule() → RentSchedule rows
  → _sync_unit_occupancy() → Unit status → OCCUPIED
  → Return LeaseSerializer(instance)
```

### 14.3 Payment Recording

```
Landlord → POST /api/v1/payments/
  → PaymentCreateSerializer.validate()
  → record_payment()
    → select_for_update() on rent period
    → Payment.objects.create()
    → payment.full_clean()
    → payment.save()
  → Return PaymentSerializer(instance)
```

### 14.4 Notification Generation

```
Cron/Scheduler → send_rent_notifications --today YYYY-MM-DD
  → generate_rent_notifications()
    → For each ACTIVE lease
      → For each unpaid/partially-paid period
        → build_idempotency_key()
        → create_notification() (idempotent)
          → If _created: send_notification_email() (if preference enabled)
```

### 14.5 Analytics Dashboard

```
Landlord → GET /api/v1/dashboard/landlord/?start_date=X&end_date=Y
  → _validate_range() → _parse_date()
  → landlord_metrics()
    → Property/Unit counts, occupancy rate
    → Collected rent (PAID payments only)
    → Overdue/upcoming rent
    → Lease expiry alerts (next 30 days)
  → Return LandlordDashboardSerializer(data)
```

---

## 15. Technology Stack

### Backend

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Language | Python | 3.11+ | Runtime |
| Framework | Django | 5.2 | Web framework |
| API | Django REST Framework | 3.15+ | REST API |
| Schema | drf-spectacular | 0.28+ | OpenAPI 3.0 |
| Auth | DRF TokenAuthentication | — | Token-based auth |
| Config | django-environ | — | Env-driven settings |
| DB (dev) | SQLite | — | Local development |
| DB (prod) | PostgreSQL | 16 | Production database |
| Cache | Redis | 7 | Caching / future queue |
| HTTP Server | gunicorn | — | Production WSGI |
| Container | Docker | — | Containerization |
| Compose | Docker Compose | — | Multi-service orchestration |
| Timezone | Africa/Lagos | — | Nigerian timezone |
| Currency | NGN | ISO 4217 | Nigerian Naira |

### Frontend (Super User Web App)

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Language | TypeScript | 6.x | Type safety |
| Framework | React | 19.x | UI library |
| Bundler | Vite | 8.x | Build tool |
| Routing | react-router-dom | 7.x | Client-side routing |
| HTTP Client | Axios | 1.x | API communication |
| Icons | lucide-react | 1.x | UI icons |
| Charts | recharts | 2.x | Data visualization |
| CSS | Tailwind CSS | 4.x | Utility-first styling |
| Testing | Vitest | 5.x | Unit/integration tests |
| Test Utils | @testing-library/react | 16.x | Component testing |

---

## 16. Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| Token auth over JWT | Simpler implementation; DRF native support; sufficient for mobile clients |
| Derived rent status | Prevents stale state; single source of truth from payment records |
| No redundant balance fields | Financial invariant enforced by computation, not storage |
| Row-level locking | Prevents concurrent payment corruption |
| Deterministic idempotency keys | Prevents duplicate notifications from scheduler runs |
| Soft-delete plans | Preserve audit trail; plans with active subscriptions cannot be deleted |
| Separate financial domains | Rent payments ≠ SaaS billing; no coupling between systems |
| Subscription limits on creation | Downgrade doesn't remove existing resources; limits enforced on new only |
| Service functions over models | Business logic separated from ORM; easier to test and reason about |
| Backdated leases allowed | Landlords may record historical tenancies when adopting the platform |
| Overpayment allowed | Excess visible in UI; auto-credit intentionally unsupported |

---

## 17. Current State vs Target State

### Implemented

| Component | Status | Evidence |
|-----------|--------|----------|
| Core auth & permissions | ✅ | 8 endpoints, Token auth, role-based access |
| Property & Unit CRUD | ✅ | Landlord-scoped, subscription limits enforced |
| Tenant invitation flow | ✅ | Secure token, expiry, single-use, acceptance flow |
| Lease lifecycle | ✅ | 5 statuses, overlap detection, renewal, termination |
| Payment recording | ✅ | Manual recording, financial invariants, concurrency |
| Notification system | ✅ | 15 types, idempotent generation, management commands |
| Subscription billing | ✅ | 3 tiers, lifecycle management, trial expiry |
| Dashboard & analytics | ✅ | Landlord/Tenant/Admin dashboards, CSV exports, growth trends |
| OpenAPI documentation | ✅ | drf-spectacular, 45+ endpoints documented |
| Docker infrastructure | ✅ | Dockerfile, docker-compose, gunicorn, health checks |
| Security hardening | ✅ | Expiring tokens, throttling, error envelope, Retry-After |
| Payment amount ceiling | ✅ | 50M NGN serializer-level validation |
| Super User Web App (foundation) | ✅ | React+TS, auth, routing, dashboard shell (Phase 10A) |
| Super User analytics dashboard | ✅ | KPIs, charts, date filtering, period comparison (Phase 10B) |

### In Progress

| Component | Status | Notes |
|-----------|--------|-------|
| Super User Web App | Phase 10B ✅ | Comprehensive analytics dashboard with KPIs, charts, date filtering |

### Planned

| Component | Status | Notes |
|-----------|--------|-------|
| Super User Web App | Phase 10C+ | User mgmt, plan mgmt, activity feed |
| Landlord Mobile App | PLANNED | Technology TBD; backend endpoints ready |
| Tenant Client | PLANNED | Technology TBD; backend endpoints ready |
| Paystack Integration | PLANNED | Clean seams stubbed; no external dependency |
| CI/CD Pipeline | PLANNED | GitHub Actions; lint, test, build, deploy |
| Monitoring | PLANNED | Uptime monitoring, alerting |
| Structured Logging | PARTIAL | Production handler fixed; aggregation TBD |

### TBD

| Component | Status | Notes |
|-----------|--------|-------|
| Mobile App Technology | TBD | React Native, Flutter, or native |
| Tenant Client Type | TBD | Web app, mobile app, or both |
| Payment Gateway | TBD | Paystack integration pending business decision |
| Background Queue | TBD | Redis available; Celery/RQ not yet configured |

---

*This document is the authoritative architectural reference for the Alquiler platform.*
*All architectural decisions should be documented here when made.*

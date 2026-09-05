# PROJECT PHASES — Alquiler Rental Management SaaS

> **Permanent source of truth** for the 10-phase development roadmap.
> Created: 2026-09-04 | Last updated: 2026-09-04

---

## Project Overview

**Alquiler** is a Django 5.2 + DRF + drf-spectacular rental management SaaS backend
built for the Nigerian (NGN) market. The system serves three roles: Landlord, Tenant,
and Platform Admin. Tenant rent payments and SaaS subscription billing are entirely
separate financial domains.

- **Workdir:** `C:\Users\BIG DAVE\Documents\REX\RENT\Alquiler\backend`
- **Framework:** Django 5.2, DRF, drf-spectacular, django-environ
- **Auth:** Token-based (DRF TokenAuthentication), email-based login
- **Database:** SQLite (dev), PostgreSQL (production)
- **Currency:** NGN (Nigerian Naira)
- **Timezone:** Africa/Lagos
- **Current Status:** Phases 1–9 COMPLETE | 317 tests | 45 API paths | 0 Django issues

---

## Phase 1 — Core Foundation (COMPLETED)

> User model, authentication, authorization, exception handling, audit logging.

### What Was Built
- **User model** (`core/models.py`): email-based authentication, 3 roles (LANDLORD, TENANT, PLATFORM_ADMIN), AccountStatus (ACTIVE/SUSPENDED), NotificationPreference (email/in-app toggles), AuditLog, token generation utilities
- **Custom UserManager** (`core/managers.py`): `create_user()`, `create_superuser()`, `landlords()`, `tenants()`, `platform_admins()` querysets
- **Custom exception handler** (`core/exceptions.py`): DomainError, ForbiddenError, NotFoundError, ConflictError; consistent `{detail, code, errors?}` envelope; fallback absorbs unexpected errors (no stack traces leaked)
- **Role-based permissions** (`core/permissions.py`): IsPlatformAdmin, IsLandlord, IsTenant, IsLandlordOrAdmin — all derived from DB role, never client-declared
- **Standard pagination** (`core/pagination.py`): PageNumberPagination, page_size=20, max_page_size=100
- **Auth views** (`core/views.py`): register, login, logout, me, update_profile, change_password, password_reset_request, password_reset_confirm — all with `@extend_schema` decorators
- **Core URL routes** (`core/urls.py`): 8 endpoints under `/api/v1/auth/`
- **Settings** (`config/settings.py`): env-driven config, SQLite (dev) / PostgreSQL (prod), DRF defaults, SPECTACULAR_SETTINGS, CORS, email config, notification schedule config, invitation TTL

### Test Coverage
- Core auth tests (register, login, logout, me, profile, password): verified in full suite

### Completion Criteria
- [x] User can register as LANDLORD, login, logout, view/update profile, change password, reset password
- [x] Role-based access control enforced at DB level
- [x] Consistent error envelope across all endpoints
- [x] No internal details leaked to API clients
- [x] AuditLog model ready for cross-cutting logging

---

## Phase 2 — Properties (COMPLETED)

> Property and Unit CRUD with landlord-scoped data isolation.

### What Was Built
- **Property model** (`properties/models.py`): landlord FK (limit_choices_to LANDLORD), name, property_type (APARTMENT/HOUSE/DUPLEX/SHOP/OFFICE/WAREHOUSE/OTHER), address, city, state, country (default Nigeria), description, currency (NGN default), status (ACTIVE/ARCHIVED), unit_count/vacant_units/occupied_units computed properties, currency ISO3 constraint, landlord+status index
- **Unit model** (`properties/models.py`): property FK, name, description, status (VACANT/OCCUPIED), unique_together (property, name), property+status index, `set_status()` method
- **PropertyViewSet** (`properties/views.py`): full CRUD, search (name/city), filter (property_type/status), ordering (name/-name), pagination, subscription limit enforcement via `assert_can_add_property`
- **UnitViewSet** (`properties/views.py`): nested under properties, full CRUD, occupancy counts derived from lease relationships, subscription limit enforcement via `assert_can_add_tenant`
- **Serializers** (`properties/serializers.py`): PropertySerializer, UnitSerializer with nested property data
- **Subscription integration** (`subscriptions/services.py`): `ensure_landlord_subscription()`, `assert_can_add_property()`, `assert_can_add_tenant()`, `serialize_usage()`
- **Plan/Subscription models** (`subscriptions/models.py`): Plan (FREE/PROFESSIONAL/BUSINESS tiers), Subscription (TRIAL/ACTIVE/PAST_DUE/CANCELLED/EXPIRED)

### Test Coverage
- `properties/tests.py`: 15+ tests covering CRUD, data isolation, subscription limits, unit lifecycle

### Completion Criteria
- [x] Landlord can create, list, retrieve, update, archive properties
- [x] Landlord can create, list, update, delete units under their properties
- [x] Cross-landlord access returns 404
- [x] Subscription plan limits enforced (properties and tenants)
- [x] Unit status derived from lease relationships, not client-supplied

---

## Phase 3 — Tenants (COMPLETED)

> Tenant invitation flow, invitation acceptance, tenant profile.

### What Was Built
- **TenantProfile model** (`tenants/models.py`): OneToOne to User, notes field
- **TenantInvitation model** (`tenants/models.py`): landlord FK, email (indexed), first_name, last_name, phone, property FK, unit FK, token (64-char, unique, auto-generated), status (PENDING/ACCEPTED/REVOKED/EXPIRED/USED), expires_at (configurable TTL), accepted_by FK, accepted_at, is_expired(), is_usable()
- **InvitationViewSet** (`tenants/views.py`): landlord creates/revokes/resends invitations, token replaced on resend, status transitions enforced
- **Invitation acceptance flow**: token validation, expiry check, single-use enforcement, creates TENANT User + TenantProfile + marks invitation USED
- **TenantViewSet** (`tenants/views.py`): landlord lists tenants derived from leases (not invitations), tenant reads own profile
- **Data isolation**: landlord sees only their tenants, cross-landlord access 404s
- **Occupancy validation**: invitation to occupied unit refused

### Test Coverage
- `tenants/tests.py`: 48 tests covering invitation lifecycle, acceptance, data isolation, token security, status transitions, tenant profile access

### Completion Criteria
- [x] Landlord can invite tenant for a specific unit
- [x] Invitation is secure: unpredictable token, time-limited, single-use
- [x] Tenant accepts invitation → creates account + profile
- [x] Revoked/expired invitations cannot be accepted
- [x] Resend replaces token and expires old one
- [x] Tenant can access own profile, cross-tenant access blocked

---

## Phase 4 — Leases (COMPLETED)

> Lease lifecycle, renewal, rent schedule generation, unit status integration.

### What Was Built
- **Lease model** (`leases/models.py`): landlord FK, tenant FK, property FK, unit FK, start_date, expiry_date, rent_amount (Decimal), currency (NGN), rent_frequency (MONTHLY/QUARTERLY/BI_ANNUALLY/ANNUALLY), rent_due_day (1-31), status (FUTURE/ACTIVE/EXPIRING/EXPIRED/TERMINATED), previous_lease FK (self-referential for renewal chaining), notes, terminated_at, effective_status() (date-derived), refresh_status(), days_remaining()
- **Constraints**: expiry >= start, currency ISO3, rent_due_day 1-31, rent_amount >= 0
- **Indexes**: landlord+status, tenant+status, unit+start_date+expiry_date
- **LeaseViewSet** (`leases/views.py`): CRUD, status filter (derived, not stored), search by tenant name, renewal endpoint, termination endpoint
- **Lease services** (`leases/services.py`): create_lease (validates overlap, unit availability, subscription quota, generates rent schedule), edit_lease (only FUTURE leases, regenerates schedule), renew_lease (creates new lease, chains previous), terminate_lease (frees unit, sets TERMINATED)
- **Rent schedule generation** (`payments/services.py:64-101`): `generate_schedule()` creates RentSchedule rows per frequency, idempotent, clamps due_day to month length
- **Unit status integration**: ACTIVE lease → unit OCCUPIED, termination/expiry → unit VACANT

### Test Coverage
- `leases/tests.py`: 37 tests covering CRUD, overlap detection, status derivation, renewal, termination, schedule generation, data isolation

### Completion Criteria
- [x] Lease lifecycle (FUTURE → ACTIVE → EXPIRING → EXPIRED/TERMINATED)
- [x] Overlap detection prevents double-booking
- [x] Renewal creates new lease and chains to previous
- [x] Termination frees unit and is allowed after expiry
- [x] Rent schedule auto-generated on lease creation
- [x] Edit only allowed for FUTURE leases, regenerates schedule

---

## Phase 5 — Payments (COMPLETED)

> Manual payment recording, rent period status derivation, concurrency safety.

### What Was Built
- **Payment model** (`payments/models.py`): landlord FK (PROTECT), tenant FK (PROTECT), lease FK (PROTECT), rent_period FK (RentSchedule, nullable), amount (Decimal), currency (NGN), payment_date, payment_method (BANK_TRANSFER/CASH/CARD/OTHER), reference, notes, status (PAID/PENDING/FAILED/CANCELLED), gateway/gateway_reference/verified (future Paystack fields), recorded_by FK
- **RentSchedule model** (`payments/models.py`): lease FK, period_start, period_end, due_date, amount (Decimal), currency (NGN), notes; unique_together (lease, due_date); period_end >= period_start constraint
- **RentPeriodStatus** (derived): UPCOMING / DUE / PARTIALLY_PAID / PAID / OVERDUE — never stored, computed from payment records
- **Financial invariant**: `paid_amount = SUM(Payment.amount WHERE rent_period=period AND status=PAID)`. No redundant balance fields.
- **Payment services** (`payments/services.py`):
  - `generate_schedule()` — creates RentSchedule rows from lease terms
  - `period_status()` — derives lifecycle status from payment aggregate
  - `paid_amount()` / `remaining_amount()` — financial computations
  - `record_payment()` — creates payment with row-level locking
  - `update_payment()` — updates with deterministic lock ordering (ascending PK)
  - `cancel_payment()` — cancels with lock, recalculates aggregate
- **Concurrency**: `select_for_update()` inside `transaction.atomic()` for all payment mutations; two-period locks acquired in ascending PK order to prevent deadlocks
- **PaymentViewSet** (`payments/views.py`): list/retrieve/create/update/cancel, payment method filter, status filter, date range filter
- **PaymentScheduleViewSet** (`payments/views.py`): read-only rent schedule with derived status annotation
- **Serializers**: PaymentCreateSerializer (validates lease-tenant-period consistency), PaymentScheduleSerializer (derived status)

### Test Coverage
- `payments/tests.py`: 65 tests covering CRUD, financial invariants, concurrency, period status derivation, payment method/status filters, data isolation

### Completion Criteria
- [x] Manual payment recording with all payment methods
- [x] Rent period status derived from payment aggregate (never stored)
- [x] Concurrency-safe payment operations (row-level locking)
- [x] Deterministic lock ordering prevents deadlocks
- [x] Cancel payment recalculates period aggregate
- [x] Payment method, status, date range filters

---

## Phase 6 — Hardening & Fixes (COMPLETED)

> API documentation, migration fixes, constraint updates, schema hardening.

### What Was Built
- **Constraint fix**: `lease_rent_due_day_range` updated from `lte=28` to `lte=31` — allows all valid calendar days (migration `leases/0003`)
- **Migration fix**: `notifications/0002` created to add missing `rent_period` FK to Notification model — fixed 500 error on lease update cascade
- **ViewSet guards**: `swagger_fake_view` guard on all 7 ViewSet `get_queryset()` methods (properties, tenants, leases, payments)
- **Schema fixes**: `PaymentViewSet.serializer_class = PaymentSerializer` added; `PaymentCreateSerializer.__init__` swagger_fake_view guard; `@extend_schema` on all 8 core FBVs; `logout` view `request=None` fix; `@extend_schema_field` on 5 SerializerMethodField methods
- **Test updates**: `test_invalid_due_day_rejected` updated (rent_due_day=32); `test_non_tenant_account_rejected` updated; schema test updated to `get_schema(public=True)`
- **Debug cleanup**: removed `debug_test.py`, `debug_schema.py`, `debug_schema2.py`
- **Django system check**: PASS (0 issues)
- **makemigrations --check**: "No changes detected"
- **Full test suite**: 160 tests, 0 failures, 0 errors
- **OpenAPI schema**: 30 paths generated, 3 cosmetic enum collision warnings (non-blocking)

### Test Coverage
- All 160 tests passing including Phase 5 regression (14 behavioral categories verified)

### Completion Criteria
- [x] Django system check passes with 0 issues
- [x] No pending migrations
- [x] OpenAPI schema generates cleanly (30 paths)
- [x] All original failing tests now pass
- [x] Phase 5 regression fully verified
- [x] Debug files cleaned up

---

## Phase 7 — Notifications & Automated Reminders (COMPLETED)

> Email + in-app notifications, scheduled rent/lease reminders, idempotent generation.

### What Was Built

- **Notification model** (`notifications/models.py`): recipient FK (SET_NULL), notification_type (15 types), channel (EMAIL/IN_APP), status (PENDING/SENT/FAILED/CANCELLED), lease FK (SET_NULL), payment FK (SET_NULL), rent_period FK (SET_NULL), invitation FK (SET_NULL), title, message, scheduled_for, sent_at, error_message, is_read, idempotency_key (unique, deterministic), 3 composite indexes (recipient+is_read, recipient+notification_type, status+scheduled_for)
- **NotificationType choices**: LEASE_EXPIRY_30D/7D/DAY/7D_AFTER/14D_AFTER/21D_AFTER/28D_AFTER, RENT_UPCOMING_7D/3D/DAY, RENT_OVERDUE_3D/7D/14D, INVITATION_SENT, INVITATION_ACCEPTED, GENERAL
- **Notification services** (`notifications/services.py`):
  - `build_idempotency_key()` — deterministic key from recipient+type+channel+date+resource; `channel` parameter ensures IN_APP and EMAIL notifications for same recipient get distinct keys; `scheduled_date` extracted to date-only (via `.date()`) to ensure same-day runs produce identical keys
  - `create_notification()` — persists with idempotency (no-op if key exists); returns notification with `_created` attribute (bool) so callers distinguish new vs existing rows
  - `send_notification_email()` — dispatches via `core.services.send_email()`, tracks PENDING→SENT/FAILED
  - `_email_enabled()` / `_in_app_enabled()` — preference helpers
  - `generate_lease_notifications()` — 7 reminder rules (30d before through 28d after expiry), notifies both landlord and tenant, respects notification preferences, excludes terminated leases, idempotent
  - `generate_rent_notifications()` — 6 reminder rules (7d before through 14d overdue), only for unpaid/partially paid periods, only ACTIVE leases, idempotent
- **NotificationViewSet** (`notifications/views.py`): read-only, own notifications only, unread filter, `mark-read` action, `unread-count` action (returns `{"count": N}`), `mark-all-read` action (marks all unread as read), `preferences` action (GET/PATCH notification preferences)
- **NotificationPreferenceSerializer** (`notifications/serializers.py`): PATCH-able email_enabled / in_app_enabled fields
- **BulkMarkReadSerializer** (`notifications/serializers.py`): validates notification IDs belong to requesting user
- **Management commands**:
  - `notifications/management/commands/send_rent_notifications.py` — supports `--today YYYY-MM-DD` and `--send-emails` flags
  - `notifications/management/commands/send_lease_notifications.py` — supports `--today YYYY-MM-DD` and `--send-emails` flags
- **URLs wired**: `config/urls.py` includes `notifications.urls` under `API_PREFIX + 'notifications/'`

### Test Coverage
- `notifications/tests.py`: 63 tests covering idempotency key generation, create_notification idempotency, terminated-lease exclusion, notification generation for all 7 lease rules and 6 rent rules, preference-respecting behavior, email dispatch, mark-read actions, unread count, bulk mark-all-read, preference update, management commands (with/without --today, with/without --send-emails), repeated execution idempotency, data isolation

### Design Decisions
- **Idempotency**: deterministic keys prevent duplicate sends when scheduler runs multiple times; `channel` param ensures IN_APP and EMAIL get distinct keys; date-only extraction ensures same-day runs are identical
- **SET_NULL on FK**: notification history preserved even if referenced record is deleted
- **Financial truth**: rent notifications use `payments.services.period_status()` (never stored status)
- **Preference-respecting**: email/in-app toggles checked before creating each notification
- **Terminated lease exclusion**: `generate_rent_notifications()` excludes leases with `status=TERMINATED`

### Verification Results
- Django system check: PASS (0 issues)
- makemigrations --check: "No changes detected"
- OpenAPI schema: 36 paths (6 new notification endpoints added)
- All 223 tests passing (63 notifications + 52 payments + 39 properties + 29 tenants + 40 leases)
- Same 3 pre-existing cosmetic enum collision warnings (non-blocking)

### Completion Criteria
- [x] Notification model with idempotency key and 3 indexes
- [x] 15 notification types (7 lease + 6 rent + 2 invitation)
- [x] Idempotent `create_notification()` with `_created` flag
- [x] Terminated-lease rent notification exclusion
- [x] Preference-respecting email/in-app generation
- [x] NotificationViewSet with unread-count, mark-all-read, preferences actions
- [x] Management commands for cron/scheduler triggering
- [x] URLs wired into main app
- [x] 63 notification tests passing
- [x] Full regression: 223 tests, 0 failures

---

## Phase 8 — Subscriptions & SaaS Billing (COMPLETED)

> Subscription management, plan upgrades/downgrades, billing integration.

### What Was Built

- **Plan model** (`subscriptions/models.py`): tier (FREE/PROFESSIONAL/BUSINESS), name, description, max_active_tenants, max_properties, price_ngn, is_active, display_order
- **Subscription model** (`subscriptions/models.py`): landlord OneToOne FK, plan FK (PROTECT), status (TRIAL/ACTIVE/PAST_DUE/CANCELLED/EXPIRED), billing_cycle (MONTHLY/QUARTERLY/ANNUALLY), started_at, current_period_start/end, trial_end, cancelled_at, cancel_reason; properties: is_trial_expired, is_active_subscription, active_tenants_count, property_count, can_add_tenant, can_add_property
- **VALID_STATUS_TRANSITIONS** map: enforces legal state machine transitions (TRIAL→ACTIVE/CANCELLED/EXPIRED, ACTIVE→PAST_DUE/CANCELLED, CANCELLED→ACTIVE, EXPIRED→ACTIVE)
- **Subscription services** (`subscriptions/services.py`):
  - `upgrade_subscription()` — FREE→paid starts trial; paid→paid immediate; creates AuditLog
  - `downgrade_subscription()` — allowed even with excess usage; limits enforced on new creations only
  - `cancel_subscription()` — transitions to CANCELLED with reason; creates AuditLog
  - `reactivate_subscription()` — CANCELLED/EXPIRED→ACTIVE; creates AuditLog
  - `check_trial_expiry()` — paid-plan trials auto-expire to EXPIRED; FREE never expires
  - `get_available_plans()` — returns active plans ordered by display_order
  - Existing functions preserved: `ensure_landlord_subscription()`, `assert_can_add_property()`, `assert_can_add_tenant()`, `assert_can_add_lease_tenant()`
- **PlanSerializer** (`subscriptions/serializers.py`): all fields writable for admin
- **SubscriptionSerializer**: read-only with nested plan, usage counts, lifecycle flags
- **SubscriptionCreateSerializer**: validates plan_id + billing_cycle
- **SubscriptionCancelSerializer**: optional reason field
- **PlanViewSet** (`subscriptions/views.py`): list/retrieve (IsAuthenticated), create/update/deactivate (IsPlatformAdmin), soft-delete on deactivation
- **SubscriptionViewSet**: retrieve (own), create/upgrade, cancel, reactivate, usage, history (all IsLandlord, own-scoped)
- **URLs wired**: `config/urls.py` includes `subscriptions.urls` under `API_PREFIX + 'subscriptions/'`
- **Admin enhanced**: list_display, list_filter, list_editable, readonly_fields
- **Settings**: `TRIAL_DURATION_DAYS = env.int('TRIAL_DURATION_DAYS', default=14)` added to config/settings.py
- **Migrations**:
  - `0003_subscription_billing_cycle_and_more.py` — adds billing_cycle, cancel_reason fields
  - `0004_seed_paid_plans.py` — seeds PROFESSIONAL (15,000 NGN, 10 tenants, 5 properties) and BUSINESS (45,000 NGN, 50 tenants, 20 properties) plans

### Test Coverage
- `subscriptions/tests.py`: 58 tests covering plan CRUD, plan model seeding, subscription lifecycle (upgrade/downgrade/cancel/reactivate), trial expiry, usage/limit enforcement, downgrade with existing resources, billing history (AuditLog), API endpoints, data isolation

### Design Decisions
- **Paystack deferred**: no external payment integration; clean seams for future
- **Trial = paid plans only**: FREE plan trial never expires
- **Downgrade allowed**: existing resources preserved; limits enforced on new creations only
- **AuditLog for history**: no new SubscriptionHistory model; SUBSCRIPTION_CHANGED action reused
- **Soft-delete plans**: is_active=False; plans with active subscriptions cannot be hard-deleted
- **Status transitions validated**: VALID_STATUS_TRANSITIONS map prevents invalid state changes

### Verification Results
- Django system check: PASS (0 issues)
- makemigrations --check: No changes detected
- OpenAPI schema: 43 paths (7 new subscription endpoints)
- All 281 tests passing (58 subscriptions + 52 payments + 39 properties + 29 tenants + 40 leases + 63 notifications)
- Same 3 pre-existing cosmetic enum collision warnings (non-blocking)

### Completion Criteria
- [x] Landlord can view available plans
- [x] Landlord can subscribe, upgrade, downgrade, cancel
- [x] Plan limits enforced on property, tenant, and lease creation
- [x] Paystack billing integration stubbed (no external dependency)
- [x] Trial period auto-expires (paid plans only, configurable duration)
- [x] Admin can manage plans via API
- [x] Billing history accessible to landlord (via AuditLog)
- [x] 58 subscription tests passing
- [x] Full regression: 281 tests, 0 failures

---

## Phase 9 — Dashboard & Analytics (COMPLETED)

> KPI endpoints, landlord dashboard, tenant dashboard, platform admin overview, CSV exports.

### What Was Built
- **Services layer** (`dashboard/services.py`): `landlord_metrics()`, `tenant_metrics()`, `admin_metrics()`, `landlord_export_data()`, `_system_health()`, `_validate_range()`, `_parse_date()`
- **Serializers** (`dashboard/serializers.py`): LandlordDashboardSerializer, TenantDashboardSerializer, AdminDashboardSerializer (read-only)
- **Views** (`dashboard/views.py`): LandlordDashboardView, TenantDashboardView, AdminDashboardView, LandlordExportView, AdminExportView (all read-only, role-gated)
- **URLs** (`dashboard/urls.py`): 5 routes wired into `config/urls.py`

### What Was Delivered
- **Landlord Dashboard** (`/api/v1/dashboard/landlord/`):
  - Property count, unit count, occupancy rate
  - Revenue summary (PAID payments only), overdue rent, upcoming rent
  - Lease expiry alerts (next 30 days)
- **Tenant Dashboard** (`/api/v1/dashboard/tenant/`):
  - Active leases list, next rent due
  - Payment history (individual records, most recent first)
  - Unread notification count
- **Admin Dashboard** (`/api/v1/dashboard/admin/`):
  - User counts by role, subscription counts by status
  - Property/unit/lease totals, revenue summary
  - System health (database, migrations, Django check)
- **CSV Exports** (`/api/v1/dashboard/landlord/export/`, `/api/v1/dashboard/admin/export/`):
  - Landlord export: properties, units, leases, revenue, overdue, upcoming, expiry alerts
  - Admin export: users, subscriptions, platform totals, revenue, system health
- **Date-range filtering**: Optional `start_date`/`end_date` (YYYY-MM-DD) on all endpoints
- **Data isolation**: Landlord sees only their data; tenant sees only their data
- **Role gating**: IsLandlord, IsTenant, IsPlatformAdmin permissions enforced

### Completion Criteria
- [x] Landlord can view revenue and occupancy KPIs
- [x] Tenant can view lease and payment summary
- [x] Platform admin can view system-wide metrics
- [x] All dashboards respect data isolation (landlord sees only their data)
- [x] Date-range filtering works on all analytics
- [x] CSV export works for landlord and admin
- [x] 36 tests, all passing

---

## Phase 10 — Production Hardening (PLANNED)

> Docker, CI/CD, monitoring, logging, rate limiting, performance optimization.

### Planned Scope
- **Docker**: Dockerfile, docker-compose.yml (django + postgres + redis + nginx)
- **CI/CD**: GitHub Actions pipeline (lint, test, build, deploy)
- **Monitoring**: health check endpoint, uptime monitoring
- **Logging**: structured logging, log aggregation
- **Rate limiting**: DRF throttle classes per endpoint/role
- **Performance**: database query optimization, caching, select_related/prefetch_related audit
- **Security**: HTTPS enforcement, HSTS, CSRF, rate limiting, input sanitization
- **OpenAPI hardening**: schema cleanup, enum collision resolution, authentication annotations
- **Database**: PostgreSQL production config, connection pooling, backups
- **Deployment**: Render/Railway/Fly.io deployment config

### Current State
- `config/urls.py:44` references "Phase 10" for OpenAPI hardening
- OpenAPI schema generates but has 3 cosmetic enum collision warnings
- SPECTACULAR_SETTINGS configured but minimal
- No Docker, CI/CD, or monitoring infrastructure

### Completion Criteria
- [ ] Application runs in Docker (dev and production)
- [ ] CI pipeline runs tests on every PR
- [ ] Health check endpoint returns system status
- [ ] Structured logging configured
- [ ] Rate limiting on auth and write endpoints
- [ ] All database queries optimized (N+1 audit)
- [ ] HTTPS enforced in production
- [ ] OpenAPI schema is clean (0 warnings)
- [ ] Deployment documented and tested

---

## Dependency Table

| Phase | Depends On | Provides |
|-------|-----------|----------|
| Phase 1 | — | User model, auth, permissions, exceptions |
| Phase 2 | Phase 1 | Property/Unit models, subscription limits |
| Phase 3 | Phase 1, 2 | Tenant invitation, profile, acceptance flow |
| Phase 4 | Phase 1, 2, 3 | Lease lifecycle, schedule generation |
| Phase 5 | Phase 1, 2, 4 | Payment recording, period status derivation |
| Phase 6 | Phase 1-5 | API docs, hardening, constraint fixes |
| Phase 7 | Phase 1, 4, 5 | Notification models, services, scheduled reminders |
| Phase 8 | Phase 1, 2 | Subscription CRUD, billing, plan management |
| Phase 9 | Phase 1-5, 8 | Dashboard KPIs, analytics, export |
| Phase 10 | Phase 1-9 | Docker, CI/CD, monitoring, production deployment |

---

## Current Status Summary

| Phase | Status | Tests | Notes |
|-------|--------|-------|-------|
| Phase 1 | COMPLETED | ✅ | Core foundation solid |
| Phase 2 | COMPLETED | 15+ | Property/Unit CRUD verified |
| Phase 3 | COMPLETED | 48 | Invitation flow verified |
| Phase 4 | COMPLETED | 37 | Lease lifecycle verified |
| Phase 5 | COMPLETED | 65 | Payment invariants verified |
| Phase 6 | COMPLETED | 160 total | All hardening done |
| Phase 7 | COMPLETED | 63 | Notifications and reminders verified |
| Phase 8 | COMPLETED | 58 | Subscription lifecycle verified |
| Phase 9 | COMPLETED | 36 | Dashboard KPIs, exports, data isolation verified |
| Phase 10 | PLANNED | 0 | No infrastructure yet |

---

## Financial Invariant (Critical)

```
paid_amount = SUM(Payment.amount WHERE rent_period=period AND status=PAID)
```

- **Never store a redundant balance field.** Always compute from payment records.
- Rent-period status is **derived** from the aggregate — never client-supplied.
- All payment mutations use `select_for_update()` inside `transaction.atomic()`.
- Two-period locks acquired in ascending PK order to prevent deadlocks.

---

## Change Control Rules

1. **This file is the authoritative source of truth** for phase definitions and status.
2. Phase status must only be updated after all completion criteria are met.
3. Changes to phase scope require explicit approval and a note in the changelog below.
4. Phase numbers are fixed — do not renumber existing phases.
5. New phases are appended (next available: Phase 11).

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-09-04 | Initial creation — reconstructed Phases 1-6 from codebase, defined Phase 7, planned Phases 8-10 | opencode |
| 2026-09-04 | Phase 7 completed — notifications and reminders (63 tests) | opencode |
| 2026-09-04 | Phase 8 completed — subscriptions and SaaS billing (58 tests) | opencode |
| 2026-09-04 | Phase 9 completed — dashboard & analytics with CSV exports (36 tests) | opencode |

---

## Appendix: Key File Locations

```
backend/
├── config/
│   ├── settings.py          # ENV-driven config, DRF defaults, SPECTACULAR_SETTINGS
│   └── urls.py              # Root URL config (Phase 10 hardening noted)
├── core/
│   ├── models.py            # User, AuditLog, NotificationPreference
│   ├── managers.py          # Custom UserManager (email-based)
│   ├── permissions.py       # IsPlatformAdmin, IsLandlord, IsTenant, IsLandlordOrAdmin
│   ├── exceptions.py        # DomainError, ForbiddenError, NotFoundError, ConflictError
│   ├── serializers.py       # Register, Login, ChangePassword, PasswordReset, UpdateProfile
│   ├── services.py          # send_email() — Phase 6 notification integration seam
│   ├── pagination.py        # StandardPagination (page=20, max=100)
│   ├── views.py             # 8 FBVs with @extend_schema
│   └── urls.py              # 8 auth endpoints
├── properties/
│   ├── models.py            # Property, Unit
│   ├── views.py             # PropertyViewSet, UnitViewSet
│   └── tests.py             # 15+ tests
├── tenants/
│   ├── models.py            # TenantProfile, TenantInvitation
│   ├── views.py             # InvitationViewSet, TenantViewSet
│   └── tests.py             # 48 tests
├── leases/
│   ├── models.py            # Lease (5 lifecycle statuses, self-referential renewal)
│   ├── services.py          # create_lease, edit_lease, renew_lease, terminate_lease
│   └── tests.py             # 37 tests
├── payments/
│   ├── models.py            # Payment, RentSchedule, RentPeriodStatus
│   ├── services.py          # generate_schedule, period_status, record/update/cancel_payment
│   └── tests.py             # 65 tests
├── notifications/
│   ├── models.py            # Notification, NotificationType, NotificationChannel, NotificationStatus
│   ├── services.py          # generate_lease/rent_notifications, send_email, idempotency
│   ├── views.py             # NotificationViewSet (read-only, mark-read)
│   ├── serializers.py       # NotificationSerializer, MarkReadSerializer
│   ├── urls.py              # Router (wired into config/urls.py)
│   └── tests.py             # 63 tests
├── subscriptions/
│   ├── models.py            # Plan, Subscription, BillingCycle, VALID_STATUS_TRANSITIONS
│   ├── services.py          # ensure_landlord_subscription, upgrade/downgrade/cancel/reactivate, trial expiry
│   ├── serializers.py       # PlanSerializer, SubscriptionSerializer, Create/Cancel/Usage serializers
│   ├── views.py             # PlanViewSet (admin CRUD), SubscriptionViewSet (landlord lifecycle)
│   ├── urls.py              # Plan routes + subscription lifecycle endpoints
│   ├── admin.py             # PlanAdmin, SubscriptionAdmin
│   ├── tests.py             # 58 tests
│   └── migrations/          # 0001, 0002_seed_free, 0003_billing_cycle, 0004_seed_paid_plans
└── dashboard/
    ├── services.py          # landlord_metrics, tenant_metrics, admin_metrics, CSV export helpers
    ├── serializers.py       # LandlordDashboardSerializer, TenantDashboardSerializer, AdminDashboardSerializer
    ├── views.py             # Dashboard views + CSV export views (role-gated)
    ├── urls.py              # 5 dashboard routes
    ├── models.py            # EMPTY (no models — read-only aggregation)
    ├── tests.py             # 36 tests
    └── migrations/          # Empty (no models)
```

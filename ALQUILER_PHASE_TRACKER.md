# ALQUILER — Phase Tracker

> **Authoritative phase tracking document** for the Alquiler rental management SaaS platform.
> Created: 2026-09-09 | Last updated: 2026-09-09 (Phase 10B)

---

## Phase Summary

| Phase | Name | Status | Tests |
|-------|------|--------|-------|
| 0 | Project Foundation | ✅ COMPLETED | — |
| 1 | Backend Core | ✅ COMPLETED | — |
| 2 | Property & Tenant Management | ✅ COMPLETED | — |
| 3 | Lease & Rent Management | ✅ COMPLETED | — |
| 4 | Payments & Financial Logic | ✅ COMPLETED | — |
| 5 | Subscriptions & Platform Rules | ✅ COMPLETED | — |
| 6 | Notifications & Dashboard APIs | ✅ COMPLETED | — |
| 7 | Backend Integration / API Completion | ✅ COMPLETED | — |
| 8 | Backend Hardening | ✅ COMPLETED | 86 |
| 9 | Backend Final QA | ✅ COMPLETED | 501 |
| 10 | Super User Web Application | Phase 10B ✅ | 24 frontend + 26 backend analytics |
| 11 | Landlord Mobile Application | PLANNED | — |
| 12 | Client Integration & E2E Testing | PLANNED | — |
| 13 | Production Deployment | PLANNED | — |
| 14 | Launch Readiness | PLANNED | — |

---

## Phase 0 — Project Foundation

> **Status:** ✅ COMPLETED

### Objective
Establish the Django project structure, configuration, and base infrastructure.

### Scope
- Django project setup (`config/settings.py`, `config/urls.py`)
- Environment-driven configuration (django-environ)
- Database configuration (SQLite dev, PostgreSQL prod)
- DRF configuration (authentication, pagination, throttling)
- OpenAPI schema configuration (drf-spectacular)
- CORS configuration
- Docker infrastructure (Dockerfile, docker-compose.yml)
- Health check endpoint

### Deliverables
- Django project with `config/` package
- `manage.py` entry point
- `.env.example` configuration template
- `docker-compose.yml` with web, db, redis services
- `Dockerfile` for production deployment
- `gunicorn.conf.py` for HTTP server
- `.dockerignore` for build optimization

### Verification Requirements
- Django system check passes
- Docker containers build successfully
- Health check endpoint returns 200
- OpenAPI schema generates without errors

### Completion Criteria
- [x] Django project runs locally
- [x] Docker containers build and start
- [x] Health check endpoint responds
- [x] Environment configuration works

---

## Phase 1 — Backend Core

> **Status:** ✅ COMPLETED

### Objective
Implement user model, authentication, authorization, exception handling, and audit logging.

### Scope
- Custom User model with email-based authentication
- User roles: LANDLORD, TENANT, PLATFORM_ADMIN
- Custom UserManager for role-based querysets
- Custom exception handler (DomainError, ForbiddenError, NotFoundError, ConflictError)
- Consistent error envelope: `{detail, code, errors?}`
- Role-based permissions (IsPlatformAdmin, IsLandlord, IsTenant, IsLandlordOrAdmin)
- Standard pagination (page_size=20, max=100)
- Auth views (register, login, logout, me, profile, change_password, password reset)
- AuditLog model for cross-cutting logging
- NotificationPreference model for user toggles

### Deliverables
- `core/models.py` — User, AuditLog, NotificationPreference
- `core/managers.py` — Custom UserManager
- `core/exceptions.py` — Custom exception handler
- `core/permissions.py` — Role-based permissions
- `core/pagination.py` — StandardPagination
- `core/views.py` — 8 auth endpoints
- `core/urls.py` — 8 auth routes

### Verification Requirements
- User can register as LANDLORD, login, logout
- Role-based access control enforced at DB level
- Consistent error envelope across all endpoints
- No internal details leaked to API clients

### Completion Criteria
- [x] User registration, login, logout working
- [x] Role-based permissions enforced
- [x] Error envelope consistent
- [x] AuditLog model ready

---

## Phase 2 — Property & Tenant Management

> **Status:** ✅ COMPLETED

### Objective
Implement property/unit CRUD with landlord-scoped data isolation, tenant invitation flow, and tenant profile.

### Scope
- Property model with landlord FK, property types, status (ACTIVE/ARCHIVED)
- Unit model with property FK, status (VACANT/OCCUPIED)
- PropertyViewSet with full CRUD, search, filter, ordering
- UnitViewSet nested under properties
- Subscription limit enforcement (assert_can_add_property, assert_can_add_tenant)
- TenantProfile model (OneToOne to User)
- TenantInvitation model with secure token flow
- InvitationViewSet with create/revoke/resend
- Invitation acceptance flow (creates TENANT User + TenantProfile)
- TenantViewSet with data isolation
- Occupancy validation (invitation to occupied unit refused)

### Deliverables
- `properties/models.py` — Property, Unit
- `properties/views.py` — PropertyViewSet, UnitViewSet
- `tenants/models.py` — TenantProfile, TenantInvitation
- `tenants/views.py` — InvitationViewSet, TenantViewSet
- `subscriptions/services.py` — Quota enforcement functions

### Verification Requirements
- Landlord can create, list, retrieve, update, archive properties
- Landlord can create, list, update, delete units under their properties
- Cross-landlord access returns 404
- Subscription plan limits enforced
- Invitation is secure (unpredictable token, time-limited, single-use)
- Tenant accepts invitation → creates account + profile

### Completion Criteria
- [x] Property/Unit CRUD working
- [x] Data isolation enforced
- [x] Subscription limits enforced
- [x] Invitation flow complete
- [x] Tenant profile creation working

---

## Phase 3 — Lease & Rent Management

> **Status:** ✅ COMPLETED

### Objective
Implement lease lifecycle, renewal, rent schedule generation, and unit status integration.

### Scope
- Lease model with 5 lifecycle statuses (FUTURE/ACTIVE/EXPIRING/EXPIRED/TERMINATED)
- Self-referential renewal chaining (previous_lease FK)
- Date-derived effective_status()
- LeaseViewSet with CRUD, status filter, renewal, termination
- Lease services: create_lease, edit_lease, renew_lease, terminate_lease
- Overlap detection (has_conflicting_active_lease)
- Unit availability assertion
- Rent schedule generation (generate_schedule)
- Unit status integration (ACTIVE lease → OCCUPIED)

### Deliverables
- `leases/models.py` — Lease model
- `leases/services.py` — Lease lifecycle services
- `leases/views.py` — LeaseViewSet
- `payments/services.py` — generate_schedule function

### Verification Requirements
- Lease lifecycle (FUTURE → ACTIVE → EXPIRING → EXPIRED/TERMINATED)
- Overlap detection prevents double-booking
- Renewal creates new lease and chains to previous
- Termination frees unit and is allowed after expiry
- Rent schedule auto-generated on lease creation
- Edit only allowed for FUTURE leases

### Completion Criteria
- [x] Lease CRUD working
- [x] Overlap detection enforced
- [x] Renewal chaining working
- [x] Rent schedule generation working
- [x] Unit status integration working

---

## Phase 4 — Payments & Financial Logic

> **Status:** ✅ COMPLETED

### Objective
Implement manual payment recording, rent period status derivation, and concurrency safety.

### Scope
- Payment model with status (PAID/PENDING/FAILED/CANCELLED)
- RentSchedule model with period dates and amounts
- RentPeriodStatus (derived, never stored)
- Financial invariant: paid_amount = SUM(Payments)
- Payment services: record_payment, update_payment, cancel_payment
- Row-level locking for concurrency safety
- Deterministic lock ordering (ascending PK)
- PaymentViewSet with CRUD, filters
- PaymentScheduleViewSet (read-only)
- Payment amount ceiling (50M NGN)

### Deliverables
- `payments/models.py` — Payment, RentSchedule
- `payments/services.py` — Payment recording services
- `payments/views.py` — PaymentViewSet, PaymentScheduleViewSet
- `payments/serializers.py` — PaymentCreateSerializer, PaymentUpdateSerializer

### Verification Requirements
- Manual payment recording with all payment methods
- Rent period status derived from payment aggregate
- Concurrency-safe payment operations
- Deterministic lock ordering prevents deadlocks
- Cancel payment recalculates period aggregate
- Payment amount ceiling enforced

### Completion Criteria
- [x] Payment CRUD working
- [x] Financial invariants enforced
- [x] Concurrency safety verified
- [x] Amount ceiling enforced
- [x] Status derivation working

---

## Phase 5 — Subscriptions & Platform Rules

> **Status:** ✅ COMPLETED

### Objective
Implement subscription management, plan upgrades/downgrades, and billing integration stubs.

### Scope
- Plan model with tiers (FREE/PROFESSIONAL/BUSINESS)
- Subscription model with lifecycle statuses
- VALID_STATUS_TRANSITIONS map
- Subscription services: upgrade, downgrade, cancel, reactivate
- Trial management (configurable duration)
- Plan CRUD (admin-only create/update/deactivate)
- SubscriptionViewSet with lifecycle endpoints
- Quota enforcement on resource creation

### Deliverables
- `subscriptions/models.py` — Plan, Subscription
- `subscriptions/services.py` — Subscription lifecycle services
- `subscriptions/views.py` — PlanViewSet, SubscriptionViewSet
- `subscriptions/serializers.py` — PlanSerializer, SubscriptionSerializer
- `subscriptions/migrations/0004_seed_paid_plans.py` — Seed data

### Verification Requirements
- Landlord can view available plans
- Landlord can subscribe, upgrade, downgrade, cancel
- Plan limits enforced on property, tenant, and lease creation
- Trial period auto-expires (paid plans only)
- Admin can manage plans via API
- Billing history accessible to landlord

### Completion Criteria
- [x] Plan CRUD working
- [x] Subscription lifecycle complete
- [x] Quota enforcement working
- [x] Trial management working
- [x] Admin plan management working

---

## Phase 6 — Notifications & Dashboard APIs

> **Status:** ✅ COMPLETED

### Objective
Implement idempotent notification generation, scheduled reminders, KPI endpoints, and CSV exports.

### Scope
- Notification model with 15 types, idempotency key, 3 composite indexes
- Notification services: generate_lease/rent_notifications, create_notification
- Deterministic idempotency keys (recipient+type+channel+date+resource)
- Preference-respecting email/in-app generation
- Management commands for cron/scheduler triggering
- NotificationViewSet with unread-count, mark-all-read, preferences
- Dashboard services: landlord_metrics, tenant_metrics, admin_metrics
- Dashboard views: LandlordDashboardView, TenantDashboardView, AdminDashboardView
- CSV export views: LandlordExportView, AdminExportView
- Date-range filtering on all analytics

### Deliverables
- `notifications/models.py` — Notification model
- `notifications/services.py` — Notification generation services
- `notifications/views.py` — NotificationViewSet
- `notifications/management/commands/` — send_rent_notifications, send_lease_notifications
- `dashboard/services.py` — Analytics aggregation
- `dashboard/views.py` — Dashboard views, CSV export views
- `dashboard/serializers.py` — Dashboard serializers

### Verification Requirements
- Notification model with idempotency key and 3 indexes
- 15 notification types (7 lease + 6 rent + 2 invitation)
- Idempotent create_notification with _created flag
- Terminated-lease rent notification exclusion
- Preference-respecting email/in-app generation
- Dashboard KPIs for all three roles
- CSV export works for landlord and admin

### Completion Criteria
- [x] Notification model complete
- [x] Idempotent generation working
- [x] Management commands functional
- [x] Dashboard KPIs accurate
- [x] CSV export working
- [x] Data isolation enforced

---

## Phase 7 — Backend Integration / API Completion

> **Status:** ✅ COMPLETED

### Objective
Integrate all backend modules, complete API wiring, and verify cross-module functionality.

### Scope
- URL wiring for all modules (config/urls.py)
- Cross-module integration testing
- API documentation (OpenAPI schema)
- Error handling consistency across all endpoints
- Pagination consistency
- Authentication consistency across all endpoints

### Deliverables
- Complete `config/urls.py` with all module includes
- OpenAPI schema with 45+ endpoints
- Integration test coverage

### Verification Requirements
- All endpoints accessible and documented
- Cross-module interactions work correctly
- Error handling consistent across all endpoints
- No regressions from previous phases

### Completion Criteria
- [x] All URLs wired correctly
- [x] OpenAPI schema complete
- [x] Integration tests passing
- [x] Error handling consistent

---

## Phase 8 — Backend Hardening

> **Status:** ✅ COMPLETED

### Objective
Security hardening, API schema cleanup, production infrastructure, and comprehensive testing.

### Scope
- **Phase 10A:** Security hardening (expiring tokens, throttling, error envelope, headers)
- **Phase 10B:** Data & business integrity (payment amount ceiling, backdated lease tests)
- **Phase 10C:** API & schema hardening (Retry-After header, OpenAPI fixes, content-type validation)
- **Phase 10D:** Production & infrastructure hardening (logging fix, gunicorn config, .dockerignore)
- **Phase 10E:** Final QA (full test suite verification)

### Deliverables
- `core/authentication.py` — ExpiringTokenAuthentication
- `core/throttling.py` — ConditionalScopedRateThrottle
- `core/exceptions.py` — Retry-After header
- `core/tests_phase10a.py` — 40 security tests
- `core/tests_phase10c.py` — 18 API/schema tests
- `core/tests_phase10d.py` — 15 infrastructure tests
- `gunicorn.conf.py` — Env-var-configurable gunicorn
- `.dockerignore` — Build optimization
- Payment amount ceiling tests
- Backdated/short lease tests
- Archive with active leases tests

### Verification Requirements
- `manage.py check` passes with 0 issues
- `makemigrations --check` shows no changes
- Full test suite passes (501 tests)
- OpenAPI schema generates without errors
- No security vulnerabilities introduced

### Completion Criteria
- [x] Security hardening complete
- [x] API schema clean
- [x] Production infrastructure ready
- [x] Full test suite passing (501/501)
- [x] No regressions

---

## Phase 9 — Backend Final QA

> **Status:** ✅ COMPLETED

### Objective
Final quality assurance, test verification, and release gate.

### Scope
- Full test suite execution (501 tests)
- System check verification
- Migration check verification
- OpenAPI schema verification
- Regression testing across all modules

### Deliverables
- Test results: 501 passed, 0 failed, 0 errors, 0 skipped
- System check: PASS (0 issues)
- Migration check: No changes detected
- OpenAPI schema: Clean generation

### Verification Requirements
- All 501 tests pass
- No system check issues
- No pending migrations
- OpenAPI schema clean
- No regressions

### Completion Criteria
- [x] Full test suite passing
- [x] System check clean
- [x] Migration check clean
- [x] OpenAPI schema clean
- [x] Release gate cleared

---

## Phase 10 — Super User Web Application

> **Status:** Phase 10B ✅ COMPLETED

### Objective
Build platform admin dashboard for user management, system monitoring, and platform analytics.

### Phase 10A — Foundation & Product Design (✅ COMPLETED)

**Frontend Stack:** React 19 + TypeScript 6 + Vite 8 + Tailwind CSS 4 + Vitest 5

**Delivered:**
- Complete application shell (sidebar, header, responsive layout)
- Authentication system (token-based, localStorage persistence)
- PLATFORM_ADMIN role enforcement (frontend + backend)
- Protected routing with loading/error/empty states
- Dashboard with real admin metrics from backend
- Leases page (real data from backend)
- Payments page (real data from backend)
- Subscriptions page (plan cards from backend)
- Notifications page (admin's own notifications)
- System health page (real-time health checks)
- Backend gap documentation (Users, Properties pages)
- 19 frontend tests passing
- TypeScript build clean
- Documentation updated

### Phase 10B — Platform Analytics & Business Intelligence (✅ COMPLETED)

**Enhanced Backend Analytics:**
- `admin_metrics()` expanded with comprehensive KPIs
- Database-level aggregation (TruncMonth, Count, Sum, conditional)
- All queries efficient (no N+1, no application-level iteration)

**Backend Changes:**
- `dashboard/services.py` — Enhanced admin_metrics with:
  - User status breakdown (active/suspended landlords/tenants)
  - Unit occupancy (occupied/vacant/rate)
  - Lease status breakdown (active/expiring/expired/terminated/future)
  - Revenue with period comparison and growth %
  - Outstanding rent (from rent schedules)
  - Overdue rent (amount + count)
  - Subscription plan tier breakdown (free/professional/business)
  - 12-month growth trends (TruncMonth aggregation)
- `dashboard/serializers.py` — Updated AdminDashboardSerializer
- `dashboard/tests.py` — 26 new analytics tests added

**Frontend Changes:**
- `src/api/types.ts` — AdminDashboardResponse updated with all new fields
- `src/pages/DashboardPage.tsx` — Complete rebuild:
  - Period selector (All Time / 7d / 30d / 90d / 12m)
  - User KPIs with status breakdown
  - Property/unit KPIs with occupancy rate
  - Lease status breakdown (5 categories)
  - Financial KPIs (revenue, outstanding, overdue, growth %)
  - User growth chart (12-month line)
  - Property/unit growth chart (12-month line)
  - Payment volume chart (12-month bar)
  - Subscription distribution (donut/pie)
  - Subscription detail cards
  - System health
  - Manual refresh button
- `src/test/DashboardPage.test.tsx` — 10 tests (up from 5)
- recharts installed for charting

**Test Results:**
- Backend: 26 new analytics tests + 6 existing admin tests = 32 dashboard tests passing
- Frontend: 24 tests passing (4 files)
- Production build: Clean

**Metrics Now Available (all from authoritative backend data):**
- Users: total, landlords, tenants, admins, active/suspended breakdown
- Properties: total count
- Units: total, occupied, vacant, occupancy rate
- Leases: total, active, expiring, expired, terminated, future
- Revenue: all-time total, period total, previous period, growth %, payment count
- Outstanding rent: total amount, period count
- Overdue rent: total amount, period count
- Subscriptions: total, active, trial, cancelled, past_due, expired, free, professional, business
- Growth trends: 12-month monthly counts for all entities
- System health: database, Django check, migrations

**Backend Gaps Still Remaining:**
- Admin user listing endpoint (for Users page)
- User suspend/reactivate (for User management)
- Admin-wide property listing (for Properties page)
- Audit log listing (for activity feed)
- Recent activity feed

### Remaining Phase 10 Work

- **Phase 10C:** User management UI (requires backend user listing endpoint)
- **Phase 10D:** Plan management UI (create, update, deactivate)
- **Phase 10E:** Activity feed & audit log
- **Phase 10F:** CSV export integration
- **Phase 10G:** Final QA & polish

### Completion Criteria (Phase 10A)
- [x] Frontend technology selected and documented
- [x] Frontend project structure exists
- [x] Super User authentication exists
- [x] Protected routing exists
- [x] PLATFORM_ADMIN access is enforced
- [x] Main application shell exists
- [x] Dashboard foundation exists
- [x] Real backend data is consumed where available
- [x] Loading/error/empty states exist
- [x] Tests written and actually executed (19/19 passing)
- [x] Existing backend tests remain passing (501 — not modified)
- [x] No Phase 11 work has started
- [x] Documentation updated
- [x] Git diff contains only intended Phase 10A changes

### Completion Criteria (Phase 10B)
- [x] Platform KPI dashboard implemented with real backend data
- [x] User metrics with status breakdown (active/suspended)
- [x] Unit occupancy correctly calculated from Unit.status
- [x] Lease status metrics use existing lease logic
- [x] Payment metrics respect existing financial architecture
- [x] Subscription metrics use actual subscription data by plan tier
- [x] Growth metrics computed from creation dates (not fabricated)
- [x] Dashboard date filtering works (period parameter sent to backend)
- [x] Backend aggregation efficient (TruncMonth, DB-level Count/Sum)
- [x] PLATFORM_ADMIN permissions enforced
- [x] Backend tests pass (26 new analytics tests)
- [x] Frontend tests pass (24 tests)
- [x] Frontend production build passes
- [x] Existing Phase 10A functionality remains working
- [x] Documentation updated (architecture + phase tracker)
- [x] Git diff contains only intended Phase 10B work
- [x] Phase 10C NOT started
- [x] Phase 11 NOT started

---

## Phase 11 — Landlord Mobile Application

> **Status:** PLANNED

### Objective
Build mobile client for landlords to manage properties, tenants, leases, and payments on the go.

### Scope (Planned)
- Property and unit management
- Tenant invitation and management
- Lease creation and renewal
- Payment recording and tracking
- Notification viewing and preferences
- Dashboard with revenue/occupancy KPIs
- Offline support (if applicable)

### Deliverables (Planned)
- Landlord Mobile App (technology TBD)
- Offline data caching (if applicable)
- Push notification support (if applicable)

### Verification Requirements (Planned)
- All landlord endpoints accessible
- Data isolation enforced
- Offline support working (if applicable)
- Push notifications working (if applicable)

### Completion Criteria (Planned)
- [ ] Mobile app builds successfully
- [ ] All landlord endpoints functional
- [ ] Data isolation verified
- [ ] Offline support working (if applicable)
- [ ] Push notifications working (if applicable)

### Notes
- Backend endpoints already implemented
- Technology choice deferred (React Native, Flutter, or native)

---

## Phase 12 — Client Integration & E2E Testing

> **Status:** PLANNED

### Objective
End-to-end testing across all clients (web, mobile, tenant) and backend API.

### Scope (Planned)
- End-to-end flow testing (property → tenant → lease → payment)
- Cross-client compatibility testing
- Performance testing (load, stress)
- Security testing (penetration, vulnerability)
- User acceptance testing

### Deliverables (Planned)
- E2E test suite
- Performance test results
- Security test report
- UAT sign-off

### Verification Requirements (Planned)
- All E2E flows pass
- Performance within acceptable limits
- No security vulnerabilities
- UAT approved

### Completion Criteria (Planned)
- [ ] E2E tests passing
- [ ] Performance acceptable
- [ ] Security cleared
- [ ] UAT approved

---

## Phase 13 — Production Deployment

> **Status:** PLANNED

### Objective
Deploy the platform to production infrastructure and verify production readiness.

### Scope (Planned)
- Production environment setup (cloud provider)
- Database migration execution
- Static files collection and serving
- SSL/TLS certificate installation
- DNS configuration
- Monitoring setup (uptime, performance)
- Logging aggregation setup
- Backup configuration
- CI/CD pipeline (if applicable)

### Deliverables (Planned)
- Production deployment
- Monitoring dashboards
- Logging infrastructure
- Backup procedures
- Deployment documentation

### Verification Requirements (Planned)
- Application accessible via production URL
- All endpoints functional in production
- Monitoring working
- Logging working
- Backups configured

### Completion Criteria (Planned)
- [ ] Application deployed successfully
- [ ] Production URL accessible
- [ ] All endpoints functional
- [ ] Monitoring working
- [ ] Logging working
- [ ] Backups configured

---

## Phase 14 — Launch Readiness

> **Status:** PLANNED

### Objective
Final launch preparation, documentation, and go-live readiness.

### Scope (Planned)
- User documentation (landlord guide, tenant guide, admin guide)
- API documentation finalization
- Launch checklist completion
- Go-live announcement preparation
- Post-launch monitoring plan
- Rollback procedures

### Deliverables (Planned)
- User documentation
- API documentation
- Launch checklist
- Go-live announcement
- Post-launch monitoring plan
- Rollback procedures

### Verification Requirements (Planned)
- All documentation complete
- Launch checklist 100% complete
- Monitoring ready
- Rollback procedures tested

### Completion Criteria (Planned)
- [ ] Documentation complete
- [ ] Launch checklist complete
- [ ] Monitoring ready
- [ ] Rollback procedures tested
- [ ] Go-live approved

---

## Phase Mapping (Legacy → Current)

| Legacy Phase | Name | Current Phase |
|--------------|------|---------------|
| Phase 1 | Core Foundation | Phase 0 + Phase 1 |
| Phase 2 | Properties | Phase 2 |
| Phase 3 | Tenants | Phase 2 |
| Phase 4 | Leases | Phase 3 |
| Phase 5 | Payments | Phase 4 |
| Phase 8 | Subscriptions | Phase 5 |
| Phase 7 | Notifications | Phase 6 |
| Phase 9 | Dashboard | Phase 6 |
| Phase 6 | Hardening | Phase 7 |
| Phase 10A-10D | Production Hardening | Phase 8 |
| Phase 10E | Final QA | Phase 9 |

---

## Strict Rules

1. **One phase at a time** — Do not begin work on a new phase until the current phase is COMPLETED
2. **No skipping** — Phases must be completed in order
3. **Tests must actually run** — Do not mark a phase as COMPLETED without running the full test suite
4. **Preserve existing decisions** — Do not reverse previously made architectural decisions
5. **Phase status must only be updated after all completion criteria are met**
6. **Changes to phase scope require explicit approval**
7. **Phase numbers are fixed** — Do not renumber existing phases
8. **New phases are appended** — Next available: Phase 15

---

## Change Control Rules

1. **This file is the authoritative source of truth** for phase definitions and status
2. Phase status must only be updated after all completion criteria are met
3. Changes to phase scope require explicit approval and a note in the changelog below
4. Phase numbers are fixed — do not renumber existing phases
5. New phases are appended (next available: Phase 15)

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-09-09 | Initial creation — 15 phases (0-14) with mapped legacy phases | opencode |
| 2026-09-09 | Phase 10A completed — React+TS foundation, auth, dashboard, routing | opencode |
| 2026-09-09 | Phase 10B completed — Platform analytics, KPIs, charts, date filtering | opencode |

---

## Appendix: Key File Locations

```
Alquiler/
├── ALQUILER_ARCHITECTURE.md        # Architectural blueprint
├── ALQUILER_PHASE_TRACKER.md       # This file
├── docker-compose.yml              # Docker services
├── frontend/                       # Super User Web App (Phase 10A+)
│   ├── src/
│   │   ├── api/                    # API client layer
│   │   │   ├── client.ts           # Axios instance
│   │   │   ├── auth.ts             # Auth API calls
│   │   │   ├── dashboard.ts        # Dashboard API calls
│   │   │   └── types.ts            # TypeScript interfaces
│   │   ├── components/             # Reusable UI components
│   │   │   ├── Layout.tsx          # App shell (sidebar + header)
│   │   │   ├── ProtectedRoute.tsx  # Auth guard
│   │   │   ├── LoadingSpinner.tsx
│   │   │   ├── EmptyState.tsx
│   │   │   ├── ErrorState.tsx
│   │   │   └── MetricCard.tsx
│   │   ├── contexts/
│   │   │   └── AuthContext.tsx      # Auth state management
│   │   ├── pages/                  # Page components
│   │   │   ├── LoginPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── UsersPage.tsx       # Backend gap placeholder
│   │   │   ├── PropertiesPage.tsx  # Backend gap placeholder
│   │   │   ├── LeasesPage.tsx
│   │   │   ├── PaymentsPage.tsx
│   │   │   ├── SubscriptionsPage.tsx
│   │   │   ├── NotificationsPage.tsx
│   │   │   ├── HealthPage.tsx
│   │   │   └── NotFoundPage.tsx
│   │   ├── test/                   # Frontend tests
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── vite.config.ts
│   ├── vitest.config.ts
│   └── package.json
├── backend/
│   ├── config/
│   │   ├── settings.py            # ENV-driven config
│   │   └── urls.py                # Root URL config
│   ├── core/
│   │   ├── models.py              # User, AuditLog, NotificationPreference
│   │   ├── managers.py            # Custom UserManager
│   │   ├── permissions.py         # Role-based permissions
│   │   ├── exceptions.py          # Custom exception handler
│   │   ├── authentication.py      # ExpiringTokenAuthentication
│   │   ├── throttling.py          # ConditionalScopedRateThrottle
│   │   ├── services.py            # send_email()
│   │   ├── pagination.py          # StandardPagination
│   │   ├── views.py               # Auth endpoints
│   │   ├── urls.py                # Auth routes
│   │   ├── tests_phase10a.py      # Security tests
│   │   ├── tests_phase10c.py      # API/schema tests
│   │   └── tests_phase10d.py      # Infrastructure tests
│   ├── properties/
│   │   ├── models.py              # Property, Unit
│   │   ├── views.py               # PropertyViewSet, UnitViewSet
│   │   └── tests.py               # Property tests
│   ├── tenants/
│   │   ├── models.py              # TenantProfile, TenantInvitation
│   │   ├── views.py               # InvitationViewSet, TenantViewSet
│   │   └── tests.py               # Tenant tests
│   ├── leases/
│   │   ├── models.py              # Lease
│   │   ├── services.py            # Lease lifecycle services
│   │   └── tests.py               # Lease tests
│   ├── payments/
│   │   ├── models.py              # Payment, RentSchedule
│   │   ├── services.py            # Payment recording services
│   │   ├── views.py               # PaymentViewSet, PaymentScheduleViewSet
│   │   ├── serializers.py         # Payment serializers
│   │   └── tests.py               # Payment tests
│   ├── notifications/
│   │   ├── models.py              # Notification
│   │   ├── services.py            # Notification generation services
│   │   ├── views.py               # NotificationViewSet
│   │   ├── management/commands/    # Cron/scheduler commands
│   │   └── tests.py               # Notification tests
│   ├── subscriptions/
│   │   ├── models.py              # Plan, Subscription
│   │   ├── services.py            # Subscription lifecycle services
│   │   ├── views.py               # PlanViewSet, SubscriptionViewSet
│   │   └── tests.py               # Subscription tests
│   ├── dashboard/
│   │   ├── services.py            # Analytics aggregation
│   │   ├── views.py               # Dashboard views, CSV export
│   │   ├── serializers.py         # Dashboard serializers
│   │   └── tests.py               # Dashboard tests
│   ├── gunicorn.conf.py           # Gunicorn configuration
│   ├── Dockerfile                 # Production Docker image
│   ├── .dockerignore              # Build optimization
│   ├── .env.example               # Environment template
│   ├── requirements.txt           # Production dependencies
│   └── requirements-dev.txt       # Dev dependencies
```

---

### Phase 10B — Surgical Fixes (2026-09-09)

**N+1 Query Fix:**
- `dashboard/services.py` `admin_metrics()` overdue rent calculation replaced per-period `period_status()` + `remaining_amount()` loop with single annotated query: `RentSchedule.objects.annotate(_paid=Sum('payments__amount', filter=Q(payments__status=PAID)))`.
- SQL confirms LEFT OUTER JOIN + annotated SUM with FILTER — single query for all overdue periods.
- Financial semantics preserved: partial payments, overpayments (floor to zero), cancelled payments excluded, terminated leases included.

**Financial Labeling Fix:**
- `revenue` field renamed to `collected_rent` across: `services.py` (admin_metrics, landlord_metrics, landlord_export_data), `serializers.py`, `views.py` (CSV exports), `tests.py` (all admin dashboard tests).
- Frontend: `types.ts`, `DashboardPage.tsx`, `DashboardPage.test.tsx` updated.
- `revenue_growth` renamed to `rent_growth`.
- Section label changed from "Revenue & Financials" to "Rent Collected & Financials".

**Test Results:**
- Backend: 62/62 passed
- Frontend: 24/24 passed
- Production build: SUCCESS

---

*This document is the authoritative phase tracking reference for the Alquiler platform.*
*All phase status changes should be documented here with evidence.*

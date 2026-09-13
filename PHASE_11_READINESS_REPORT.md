# PHASE 11 READINESS REPORT — LANDLORD MOBILE APPLICATION

**Date:** 2026-09-11
**Status:** NOT READY FOR PHASE 11 IMPLEMENTATION
**Authorship:** Automated Phase 11 readiness audit of the Alquiler repository (documentation only — no code changes).
**Source material:** `ALQUILER_PHASE_TRACKER.md`, `ALQUILER_ARCHITECTURE.md`, `CURRENT_PROJECT_STATUS.md`, `PROJECT_AUDIT_REPORT.md`, `README.md`, and direct inspection of `backend/**/urls.py`, `backend/core/views.py`, `backend/core/authentication.py`, `backend/payments/views.py`, `frontend/src/**`.

---

## 1. Phase 11 Definition and Documented Scope

**Phase 11 — Landlord Mobile Application** is defined in `ALQUILER_PHASE_TRACKER.md` (status: **PLANNED**) as:

> Build a mobile client for landlords to manage properties, tenants, leases, and payments on the go.

### Documented scope (Planned, per phase tracker)
- Property and unit management
- Tenant invitation and management
- Lease creation and renewal
- Payment recording and tracking
- Notification viewing and preferences
- Dashboard with revenue/occupancy KPIs
- Offline support (if applicable)

### Documented deliverables (Planned)
- Landlord mobile app (technology TBD)
- Offline data caching (if applicable)
- Push notification support (if applicable)

### Documented completion criteria (Planned, all open)
- [ ] Mobile app builds successfully
- [ ] All landlord endpoints functional
- [ ] Data isolation verified
- [ ] Offline support working (if applicable)
- [ ] Push notifications working (if applicable)

### Stated note in the tracker
> Backend endpoints already implemented; technology choice deferred (React Native, Flutter, or native).

`ALQUILER_ARCHITECTURE.md` §8 mirrors this scope (property/unit management, tenant invitation and management, lease creation and renewal, payment recording and tracking, notification viewing and preferences, dashboard with collected rent/occupancy KPIs) and records that the technology decision is pending.

---

## 2. Documentation Status

| Item | Status |
|------|--------|
| `PROJECT_PHASES.md` | **ABSENT** — no file of this name exists in the repository |
| Separate Phase 11 specification document | **ABSENT** — there is no standalone Phase 11 spec beyond the tracker + architecture references above |
| Phase 11 status in `ALQUILER_PHASE_TRACKER.md` | PLANNED, scope verbatim from lines 658–695 |
| Phase 11 status in `ALQUILER_ARCHITECTURE.md` | PLANNED (§8), technology TBD |
| Phase 11 impact in `CURRENT_PROJECT_STATUS.md` | Listed as next phase; backend described as ready |
| Phase 10 final verification (`PROJECT_AUDIT_REPORT.md`) | Concluded "ready to begin Phase 11" from a backend-only perspective; does **not** audit mobile-specific requirements |

**Documentation gap:** the tenet "backend endpoints are ready" is confirmed for CRUD, but **no** Phase 11 specification exists that defines the mobile UX, device/session policy, push-notification mechanism, offline strategy, or payment-retry behavior. This report supplies that missing specification input and the required blockers.

---

## 3. Backend API Readiness / Inventory

Backend is Django 5.2 + DRF 3.18, versioned under `/api/v1/`, auth via DRF `TokenAuthentication` (custom `ExpiringTokenAuthentication`). OpenAPI is generated with drf-spectacular (`/api/schema/`, Swagger UI at `/api/docs/`; **ReDoc is not wired**).

| Group | Base path | Endpoints (method) | Notes |
|-------|-----------|--------------------|-------|
| **Auth** | `/api/v1/auth/` | `register` (POST), `login` (POST), `logout` (POST), `me` (GET), `profile` (PATCH), `change-password` (POST), `password-reset` (POST), `password-reset/confirm` (POST), `health` (GET) | Single-token rotation per user; 7-day expiry; **no refresh endpoint** |
| **Properties** | `/api/v1/properties/` | `list/create`, nested `/properties/{id}/units/` list/create, unit detail retrieve/update/patch/delete | Landlord-scoped; subscription limits enforced; search/filter/ordering |
| **Tenants** | `/api/v1/tenants/` | `me/` (GET), `invitations/accept/` (POST), invitations list/create/retrieve + revoke/resend, tenant list/retrieve | Secure single-use invite tokens with expiry |
| **Leases** | `/api/v1/leases/` | list/create/retrieve/partial-update + `{id}/renew/` (POST), `{id}/terminate/` (POST), `{id}/rent-schedule/` (GET) | Overlap detection, unit availability, server-derived status |
| **Payments** | `/api/v1/payments/`, `/api/v1/rent-schedules/` | payment list/create/partial-update + `{id}/cancel/` (POST); rent-schedules read-only | Landlord/tenant access split; financial invariant `paid_amount = SUM(PAID)`; 50M NGN ceiling; **no idempotency key on payment creation** |
| **Notifications** | `/api/v1/notifications/` | list/retrieve, `unread-count` (GET), `mark-all-read` (POST/PATCH), `{id}/read` (POST/PATCH), `preferences` (GET/PATCH) | 15 types, idempotent generation, IN_APP + EMAIL channels only (no push) |
| **Subscriptions** | `/api/v1/subscriptions/` | `plans/` list, `subscription/` get/create, `subscription/cancel`, `subscription/reactivate`, `subscription/usage`, `subscription/history` | 3-tier SaaS, quotas enforce resource creation limits |
| **Dashboard** | `/api/v1/dashboard/` | `landlord/` (GET), `landlord/export/` (CSV), `tenant/` (GET), `admin/` (GET), `admin/export/` (CSV) | Landlord KPIs (revenue, occupancy, overdue) exist for mobile |
| **Platform Admin** | `/api/v1/admin/` | users/properties/plans/subscriptions/audit-logs ViewSets, `issues/` | **NOT required by the landlord app** |

**Mobile-app relevance verdict on CRUD readiness: every landlord workflow in Phase 11 scope has a tested backend endpoint** (properties, units, tenants, invitations, leases, renewals, terminations, payments, rent schedules, notifications, preferences, dashboard, subscription usage). The two genuine blockers are cross-cutting concerns, not missing CRUD endpoints (see §9).

---

## 4. Mobile-Specific Gaps — Classification

> Each gap below has been inspected in the backend and classified against the Phase 11 MVP scope.

### A. REQUIRED BLOCKERS — must be resolved before Phase 11 implementation

| # | Gap | Evidence | Why it blocks mobile |
|----|-----|----------|----------------------|
| **A1** | **Multi-device token lifecycle / token refresh absent** | `core/views.py:_issue_token` deletes **all** existing tokens for a user on every `login` (single-session rotation). `ExpiringTokenAuthentication` (`core/authentication.py`) rejects tokens older than `AUTH_TOKEN_EXPIRY_DAYS` (default **7**). `change_password` and `password_reset_confirm` delete all tokens. There is **no refresh endpoint** and no multi-device/session model. | Logging into a phone silently signs out the web session; every token expires after 7 days with no refresh path (forced full re-login, which in turn logs out all other devices). A landlord using web + phone cannot have a stable authenticated mobile session without a session/refresh redesign. |
| **A2** | **Payment idempotency absent on `POST /api/v1/payments/`** | `payments/views.py:PaymentViewSet.create` (lines 124–147) calls `record_payment(...)` with **no client-supplied idempotency key** and no `Idempotency-Key` header handling. Idempotency exists only for notification generation and rent-schedule generation — **not** for payment recording. | On flaky mobile networks a timed-out `POST` is retried; without idempotency a retry double-records a payment, silently corrupting the financial invariant `paid_amount = SUM(PAID payments)`. This is unacceptable for a money-movement operation and must be solved server-side before any client ships. |

### B. NICE-TO-HAVE — add after blockers are resolved; do not gate MVP

| Gap | Status | Notes |
|-----|--------|-------|
| Push notifications | Backend has IN_APP + EMAIL only; no device-token registry or FCM/APNs provider seam | The notification model/channels would need a DEVICE/PUSH channel, token registration endpoint, and provider integration. Defer to post-MVP or 11F stretch. |
| Offline data caching / write queue | No backend support needed; purely a client concern | Read-only offline cache (properties, schedules) is feasible with Expo SecureStore/AsyncStorage + SQLite; offline **writes** (lease/payment) are risky and should be deferred. |
| Biometric auth / OS keychain | Client-only | expo-local-authentication + expo-secure-store; recommended but not a blocker. |
| Background refresh / silent sync | Client-only | Optional; needs an idempotent, refresh-capable auth layer first (depends on A1). |
| Role isolation extension for multiple clients | Client-only | e.g., refuse LANDLORD role login on the admin web app is already enforced; inverse enforcement on mobile is trivial. |

### C. NOT REQUIRED for the Phase 11 landlord app

| Item | Reason |
|------|--------|
| Platform Admin console APIs (`/api/v1/admin/*`) | Not a landlord concern |
| Admin/tenant dashboards + CSV exports | Desktop/admin oriented; landlord dashboard KPIs are reused, exports are not needed on mobile |
| ReDoc endpoint | Cosmetic docs item, unrelated to mobile |
| New database migrations for Phase 11 features | Blockers A1/A2 may require migrations; no feature migration is otherwise needed |
| Any change to `requirements.txt` | No new backend package is required for the landlord app |
| FCM/APNs push in MVP | Classified as Nice-to-have (B) |

---

## 5. Existing Frontend Architecture

### What exists today
The Phase 10 frontend (`frontend/`) is a **React 19 + TypeScript + Vite + Tailwind + Vitest** web application — but it is the **Super User (PLATFORM_ADMIN) console**, not a landlord client. It ships 11 admin pages (Login, Dashboard/analytics, Users, Properties, Leases, Payments, Subscriptions, Issues, Notifications, Health, NotFound), 15 reusable components, 5 API modules, and an `AuthContext`. All admin endpoints consumed are read-only.

### Conceptual patterns that CAN be reused directly

| Pattern | Source | Reuse value |
|---------|--------|-------------|
| Versioned API base URL + Axios instance | `frontend/src/api/client.ts` | Same `Token` header scheme, error normalization |
| Error normalization (`ApiRequestError` / `{detail, code, errors}`) | `client.ts` | Identical backend error envelope — reuse the type contract |
| Auth flow shape (login → store token → fetch `/me/` → role-gate) | `frontend/src/contexts/AuthContext.tsx` | Same endpoint contract; role gate becomes LANDLORD instead of PLATFORM_ADMIN |
| TypeScript domain types (User, Property, Unit, Lease, Payment, Notification, Subscription) | `frontend/src/api/types.ts` | Contract-first typing can be translated to RN/TS |
| UI state conventions (loading / error / empty states, pagination, filters) | `components/*` | Design-system pattern translation, not literal reuse |
| Dashboard KPI consumption logic | `frontend/src/api/dashboard.ts` | `landlord/` KPI endpoint mirrored for mobile |
| CSV/none — CSV export is admin-only and NOT reused | `api/admin.ts` | Excluded from mobile |

### What MUST be rebuilt for mobile

| Area | Why |
|------|-----|
| **Every landlord screen** | The existing app has **no** landlord workflows: no property/unit creation, no tenant invitation, no lease create/renew, no payment recording. Those UI flows do not exist anywhere and must be built from scratch. |
| Platform/navigation | `react-router` DOM navigation → `expo-router`/React Navigation with bottom tabs + stack |
| Token storage | `localStorage` → `expo-secure-store` (Keychain/Keystore) |
| Rendering/styling stack | Tailwind/DOM → React Native primitives + StyleSheet/NativeWind (rework, not port) |
| Charts | Recharts (SVG/DOM) → a mobile chart lib (victory-native / react-native-svg) |
| Auth session logic | Must be **rewritten** to match the A1 solution (refresh handling, per-device tokens, secure storage, 401-silent-renewal interceptor) |
| Test stack | Vitest + jsdom → Jest + jest-expo/react-native-testing-library |
| Push/offline plumbing | New (Expo Notifications, AsyncStorage/SQLite) — does not exist in the web app |

**Bottom line:** the web app contributes contracts, auth-scheme knowledge, and design patterns — roughly 15–20% conceptual reuse. The landlord mobile app is effectively a greenfield client build.

---

## 6. Phase 11 MVP Scope (Recommended)

In **Phase 11 MVP**, the following screens and flows (all backed by existing endpoints) are in scope, in priority order:

1. **Auth:** landlord login, token storage (secure), logout, `/me/` validation, password change.
2. **Dashboard:** `GET /api/v1/dashboard/landlord/` KPIs (collected rent, occupancy, overdue) with period filter.
3. **Properties:** property + unit list with search/filter, detail, create/update/archive; unit occupancy state.
4. **Tenants:** tenant list/detail, invitation create/revoke/resend, invite acceptance status.
5. **Leases:** lease list/detail, create, renew, terminate; rent schedule view.
6. **Payments:** payment list/search, record payment, cancel payment, rent-schedule status.
7. **Notifications:** list, unread count, mark read / mark-all-read, preferences toggle.
8. **Subscription status:** current plan, usage, history (read-only).

**MVP exclusions (explicit):** offline write queue, push notifications, biometric login, CSV export, admin console.

---

## 7. Proposed Sub-Phases

> Backend changes for A1/A2 land in 11A. Each sub-phase ends with tests + a build.

| Phase | Name | Scope |
|-------|------|-------|
| **11A** | **Foundation + Auth** | Resolve A1 (multi-device token lifecycle + refresh) and A2 (payment idempotency) server-side; create Expo project, secure token storage, auth screens, protected navigation, role gate (LANDLORD). |
| **11B** | **Dashboard** | Landlord KPI screen, period filter, loading/error/empty states, pull-to-refresh. |
| **11C** | **Properties** | Property/unit list + detail + create/update forms, search/filter, occupancy badges, archive. |
| **11D** | **Leases + Schedules** | Lease list/detail/create, renew/terminate, rent-schedule view with period status. |
| **11E** | **Payments** | Payment list/search, record payment (with idempotency header), cancel, rent-period status derivation. |
| **11F** | **Notifications** | List, unread badge, mark-read/mark-all-read, preference toggles. (Push notifications = optional stretch.) |
| **11G** | **Tenants + Subscription** | Tenant list/detail, invitation create/revoke/resend; subscription usage/status read-only. |
| **11H** | **QA + Release** | Offline read-cache (nice-to-have), device smoke tests, E2E against backend, app store build config, release. |

---

## 8. Technology Recommendation

### Recommended: **React Native + Expo**

Rationale:
- Shared **language (TypeScript)** and **type contracts** with the existing React web frontend — the API types in `frontend/src/api/types.ts` carry over almost verbatim.
- Same **Axios/Token-header** client pattern (`frontend/src/api/client.ts`) can be reused with a React Native interceptor; the existing error-envelope handling is directly portable.
- Reuses the team's existing React knowledge from Phase 10; fastest path to a working client.
- Expo Managed workflow provides SecureStore, Push (expo-notifications), OTA updates, and Expo Go for fast iteration.
- Needs no backend rewrite; Token auth aligns with the current `Authorization: Token <key>` scheme (refresh layer added via 11A).

### Alternatives (documented, not selected)
| Option | Considerations |
|--------|----------------|
| **Flutter (Dart)** | Excellent native performance and single codebase, but introduces a new language + toolchain; the Phase 10 frontend contracts are TS-based and would need rewriting; larger team retraining cost. |
| **Native iOS (Swift) / Android (Kotlin)** | Best platform integration and offline control, but doubles the build and maintenance effort (two codebases) and is the slowest to MVP for a small platform team. |

---

## 9. Exact Phase 11 Blockers

### A1 — Multi-device token lifecycle / token refresh
**Problem:** `core/views.py:_issue_token` performs single-token rotation (deletes all existing tokens on login); `ExpiringTokenAuthentication` (default 7-day expiry) rejects stale tokens; password change/reset purge all tokens; there is no refresh endpoint and no per-device session.
**Impact:** any second login invalidates the first device; a mobile user is force-logged-out weekly and cannot restore a session without re-login.

**Minimum work required to remove A1:**
1. Backend: introduce a device/session identifier so a user can hold multiple valid tokens (e.g., add a `Device`/`TokenSession` model linking each token to a named device, or switch to JWT access + refresh pairs).
2. Backend: add `POST /api/v1/auth/refresh/` that issues a new token for the requesting device; keep `logout` scoped to the current device only.
3. Backend: update `login` to stop deleting other devices' tokens; keep `change_password`/`password_reset` revoking **all** sessions except (optionally) the current one.
4. Backend: keep `ExpiringTokenAuthentication` expiry but ensure refresh keeps sessions alive within policy (e.g., sliding/session TTL).
5. Client (11A): store token in SecureStore; add a silent-refresh interceptor that retries 401 once with a refresh token before surfacing an error.
6. Tests: multi-device login coexistence, refresh rotation, expiry + refresh recovery, logout-is-device-scoped, password-change session revocation.

### A2 — Payment idempotency on `POST /api/v1/payments/`
**Problem:** `payments/views.py:PaymentViewSet.create` (lines 124–147) passes no idempotency key; `record_payment` is not idempotent. Retrying a timed-out payment POST can record the payment twice and corrupt `paid_amount`, violating the core financial invariant.
**Impact:** double-billing a tenant because of a mobile network retry — unacceptable for a money movement API.

**Minimum work required to remove A2:**
1. Backend: accept a client-supplied `Idempotency-Key` header on `POST /api/v1/payments/`; validate format/length.
2. Backend: persist the key on `Payment` with a uniqueness constraint scoped to `(landlord, idempotency_key)`; on duplicate, return the existing payment (or 200 with the prior record) instead of creating a second row.
3. Backend: enforce via the existing row-locking path (`record_payment`) so concurrent duplicate attempts serialize correctly.
4. Backend: generate server-side fallback keys when the header is absent (still race-safe), and apply the same pattern to lease creation if the mobile flows can double-fire writes there.
5. Tests: duplicate-key returns existing payment, concurrent duplicate attempts create one payment, key scoped per landlord, invalid/absent keys, retry-after network-drop simulation.
6. Client (11A/11E): generate a UUID idempotency key once per payment attempt and reuse it across retries.

---

## 10. Final Readiness Verdict

> ### ❌ **NOT READY FOR PHASE 11 IMPLEMENTATION**

The backend is strong: every landlord workflow in Phase 11 scope already has a tested, documented endpoint, and the frontend provides reusable TS/API contracts. **However, Phase 11 cannot begin safely until:**

1. **A1 (token lifecycle / refresh)** is solved — required for any multi-device mobile session.
2. **A2 (payment idempotency)** is solved — required before any mobile client can record money without risking double-payment.

Additionally, no Phase 11 specification document exists (`PROJECT_PHASES.md` is absent) and the tech decision is still an open TBD — both should be captured alongside the blocker work per §7 (11A).

**Definition of "ready":** A1 and A2 merged with tests, Phase 11 spec + tech recommendation recorded, and 11A foundation (Expo project + secure auth) green-lit. MVP scope and sub-phases in §6–§7 remain valid once blockers are cleared.

---

*Documentation-only deliverable. No application, backend, or frontend code was modified; no packages were installed; no migrations were created; `ALQUILER_PHASE_TRACKER.md` was not modified; Phase 11 was not started.*
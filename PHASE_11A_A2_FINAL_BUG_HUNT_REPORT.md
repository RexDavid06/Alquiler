# PHASE 11A/A2 — FINAL DEEP BUG HUNT REPORT

**Date:** 2026-09-12
**Scope:** A1 multi-device auth + A2 payment idempotency + finalization hardening (TASK 1–7 from the prior task).
**Method:** Full source re-read of every A1/A2-touched file, independent verification of the prior reports' claims, lifecycle/transaction trace, PostgreSQL race reasoning, and a fresh full test run.
**Result:** **READY_TO_COMMIT** — 4 real bugs fixed (each with a regression test), 2 explicit coverage gaps closed, 616/616 backend tests pass, migrations clean.

---

## 1. Executive Summary

The prior reports' headline claims were **verified correct**:
- A1 multi-device auth implemented and internally consistent for the ACTIVE/ACTIVE accounts it serves.
- A2 payment idempotency correct, with the DB unique constraint as the final authority.
- Suspended-user fix present and effective (`status != ACTIVE` gate at token-auth and refresh).
- Pre-fix suite passes (608/608 reconfirmed).

This hunt nonetheless found the following **real defects**:

1. **CORS blocks the `Idempotency-Key` header** — the browser client (Vite :5173 → API :8000) cannot send header-based idempotency keys; the header is absent from `CORS_ALLOW_HEADERS`, so preflights are refused. (A2 integration bug.)
2. **`POST /auth/login/` issues full credentials to non-ACTIVE accounts.** Users with `status ∈ {PENDING, DEACTIVATED}` and `is_active=True` receive a 200 response with a device session + access token + refresh credential — all of which the authentication layer immediately rejects (`account_not_active`). Login was inconsistent with the auth gate; also created junk sessions/tokens. (A1 correctness bug.)
3. **Oversize `Idempotency-Key` header → HTTP 500.** The header path bypasses the serializer `max_length=64`; the model `full_clean()` then raises Django `ValidationError`, which the custom exception handler maps to a 500 envelope instead of a 400. (A2 bug, task scenario J.)
4. **`change_password` / `password_reset_confirm` commit the password change before credential revocation**; a revocation failure left a changed password with still-usable old credentials and returned an error for a change that actually happened. Made atomic. (Data-integrity issue, task scenario: "failed transaction leaves half-created authentication state".)
5. **Duplicate imports** in `core/authentication.py` (cleanup).

Two explicit **coverage gaps** from the task's must-consider list were closed with new tests (inactive access-token rejection; cancelled-payment replay contract).

Everything else inspected was found correct **or** intentionally left alone for documented reasons (§4, §10, §14).

---

## 2. Bugs Discovered

| # | Severity | Area | Description |
|---|----------|------|-------------|
| B1 | High (functionality) | A2 / CORS | `Idempotency-Key` header not in `CORS_ALLOW_HEADERS` → browser preflight refuses header-based idempotency. |
| B2 | Medium-High (correctness) | A1 / login | Login grants tokens+refresh+sessions to `PENDING`/`DEACTIVATED` (non-ACTIVE) accounts that cannot use them. |
| B3 | Low-Medium (robustness) | A2 / input | `Idempotency-Key` header >64 chars → 500 instead of 400 (header bypasses serializer validation; `full_clean()` raises Django `ValidationError`). |
| B4 | Medium (data integrity) | A1 / lifecycle | Password change & reset were not atomic with revocation; a mid-failure left a changed password with usable old credentials. |
| B5 | Nit | A1 | Duplicate `settings`/`timezone` imports in `core/authentication.py`. |

## 3. Bugs Fixed

- **B1**: added `idempotency-key` to `CORS_ALLOW_HEADERS` (`backend/config/settings.py`). Regression: `test_cors_preflight_allows_idempotency_key_header`.
- **B2**: `LoginSerializer` now rejects any `user.status != AccountStatus.ACTIVE` (SUSPENDED keeps its specific `account_suspended` message/code; PENDING/DEACTIVATED fail closed with the same 400 envelope). Regression: `test_login_pending_account_blocked_no_session_created`, `test_login_deactivated_account_blocked_no_session_created` (assert **no token/session rows** are created).
- **B3**: `PaymentViewSet.create` validates the header key length (≤64) before handing off, returning a 400. Regression: `test_oversized_header_key_rejected_with_400`.
- **B4**: both views wrap `set_password`+`save`+`revoke_all_sessions`+`Token.delete` in a single `transaction.atomic`. Regression: `test_change_password_rolls_back_when_revocation_fails`.
- **B5**: removed the duplicated imports in `core/authentication.py`.
- **Coverage gaps**: added `test_inactive_user_existing_access_token_rejected` (session suite) and `test_invalid_request_with_key_returns_400_no_payment` + `test_replay_after_cancel_returns_original` (payment idempotency suite).

## 4. Bugs Intentionally NOT Fixed + Rationale

1. **201-vs-200 on a true concurrent same-key race** — the DB unique constraint plus IntegrityError fallback guarantee exactly one Payment; only the client-visible status code may be 201 on the losing request (the view computed `replayed` before the other transaction committed). Cosmetic; explicitly permitted to leave by the task ("do not introduce complexity solely to make a status code prettier"). No change.
2. **Password-reset for DEACTIVATED/PENDING users** — `password_reset_request` only special-cases SUSPENDED. Resetting does not reactivate an account and requires access to the account's email; login is now uniformly gated on ACTIVE, so there is no privilege escalation. Left unchanged.
3. **In-flight request after suspension** — a `status` flip only cuts off the *next* request (auth is checked per request, DRF default). Immediate mid-request enforcement would require per-view state checks — out of scope, matches the design.
4. **Rotated-out access-token rows on suspension** — suspension blocks refresh (`status=ACTIVE` filter) and token auth (`account_not_active`) on the next request; residual token rows are inert and expire naturally. No purge added (consistent with "smallest change").
5. **`_trim_excess_sessions` ordering with `NULL last_used_at`** (PostgreSQL sorts NULLs first under `DESC`) — session creation/refresh always sets `last_used_at`, so the keep-session is always most recent; unreachable in practice.
6. **Single-generation refresh-reuse tracking, `CheckConstraint`, `compare_digest`, `/auth/sessions/` endpoint** — all previously deferred with rationale; reconfirmed as non-issues (no exploitable race in the single-slot design; the DB hash compare is equivalent for this threat model; session/access coherence is upheld by the single write-path).
7. **Throttles disabled under `DEBUG=True`** — intentional dev/test ergonomics; throttle classes + scoped rates are active when `DEBUG=False` (production), verified in `settings.py` and by `ThrottleTests`.

## 5. Authentication Lifecycle Audit (code truth, not report claims)

Traced every flow against `create_device_session`, `refresh_access_token`, `_rotate_session`, `revoke_all_sessions`, `revoke_session_for_token`, `ExpiringTokenAuthentication`, and the serializers/views:

- **Registration** → `RegisterSerializer` → `user.activate()` (ACTIVE, is_active=True) → `ensure_landlord_subscription` → tokens issued. Tenant invitation accept sets ACTIVE before issuing tokens. Both paths produce usable credentials. ✓
- **Login** → `authenticate()` (backend checks is_active) + SUSPENDED gate + **new** non-ACTIVE gate; ACTIVE accounts get a session + rotating refresh. ✓
- **Token creation** → `secrets.token_hex(20)` (160-bit), PK-unique. ✓
- **Same-device login** → session reused, prior access token deleted, both credentials rotate; other devices untouched (verified by `test_login_same_device_rotates_token`, `test_repeated_login_same_device_single_token`). ✓
- **Multi-device** → one DeviceSession per (user, device); `uniq_user_device_session`; coexistence covered. ✓
- **Access-token auth** → base DRF behavior (valid/inactive/deleted = 401) + expiry gate (deletes expired) + ACTIVE gate. ✓
- **Refresh** → requires non-expired, non-revoked, ACTIVE+is_active session matching device_id AND hash; rotates both credentials under `transaction.atomic`, writes `previous_refresh_token_hash`. ✓
- **Refresh reuse** → rotated-out hash matches `previous_refresh_token_hash` on a non-revoked session → session revoked + access token deleted + 401. ✓
- **Logout** → revokes only the owning device's session and deletes its access token (legacy tokens: delete-only, no session row — covered). ✓
- **Password change / reset** → now atomic: new password + `revoke_all_sessions` + delete-all-tokens commit together; old old-refresh credentials 401 (covered). ✓
- **Suspension / deactivation** → non-ACTIVE users: login 400, existing access token 401, refresh 401 (covered incl. new inactive-access test). ✓
- **Device limit** → oldest sessions trimmed after every create (covered by `test_factory_device_limit_revokes_oldest`). ✓

**Failed-transaction answer:** pre-fix, change-password/reset could leave half-created state (B4). Now atomic.

## 6. Refresh Token Security Audit

- Plaintext never persisted — only SHA-256 hexdigest; `_new_refresh_token()` = `secrets.token_hex(32)`. ✓
- Never logged — no logging statements touch credentials; `request.META`/headers not logged. ✓
- Not returned beyond lifetime — rotation issues fresh refresh with a TTL window each use; expiry enforced in the session query. ✓
- Old credential unusable after rotation — fails first (current-hash) query. ✓
- Reuse detection — revokes the whole session AND deletes its access token. ✓
- Expiry — `refresh_expires_at > now` in the lookup (covered). ✓
- Revocation — `revoked_at__isnull=True` in the lookup (covered). ✓
- Device binding — `device_id` required and matched (covered). ✓
- User binding — session rows are per-user; lookup climbs through the user's own session. ✓
- Suspension bypass — impossible: refresh lookup requires `user__is_active=True` and `user__status=ACTIVE` (covered). ✓
- Throttle in production — active at `DEBUG=False`; refresh scoped at 30/minute. ✓
- **Single-slot reuse tracking**: no exploitable race found. A credential two+ rotations old simply fails the hash match (rejected as invalid), and the current/previous slot scheme cannot revoke the wrong session because both lookups are non-revoked-session-scoped and hashes are 256-bit random. Not redesigned (per task). ✓

## 7. Access Token Audit

- Expired → deleted-on-detection + 401 `token_expired`. ✓
- Deleted/revoked → 401 (base lookup miss). ✓
- Inactive user → 401 (base `is_active` check; now also covered by new test). ✓
- Suspended/non-ACTIVE → 401 `account_not_active`. ✓
- Valid ACTIVE → 200 (covered). ✓
- Legacy tokens (created pre-session) → still authenticate; logout works (covered). ✓
- Deletion leaves no inconsistent state — FK is `SET_NULL`; a token-only delete simply leaves its session without an access token (still rotatable/revocable). ✓
- **Status check on every request**: the ACTIVE gate adds one attribute read per auth; no role-based behavioral change observed for ACTIVE tenants/landlords/admins (full suite green). ✓

## 8. DRF Token Replacement Audit

- **Imports**: no production import of `rest_framework.authtoken` remains — grep confirms only docstring mentions in `core/models.py` and `core/authentication.py`. Test files were migrated to `core.models.Token` (`core/tests.py`, `tests_phase10a.py`, `tests_phase10c.py`, `payments/tests.py`). ✓
- **Migrations**: `core/0002` creates `core.Token` + `DeviceSession`; `payments/0003` touches only the Payment idempotency key. No migration references the old authtoken table. `makemigrations --check --dry-run` → **no changes detected**. ✓
- **Admin**: no Token/DeviceSession registered; nothing assumes the old model. ✓
- **Serializers**: Login/Register/Refresh/User serializers use the project Token/session flow; no old-model assumption. ✓
- **Test helpers**: create `core.Token` via `Token.objects.get_or_create` / login flows. ✓
- **Key generation**: `secrets.token_hex(20)` (160-bit CSPRNG), unique PK. ✓
- **FK behavior**: `Token.user` CASCADE (deleting a user removes tokens); `DeviceSession.access_token` `SET_NULL` (deleting a token nulls the session's link, immediately revocable/rotatable); `DeviceSession.user` CASCADE. ✓
- **`INSTALLED_APPS`**: `rest_framework.authtoken` removed. Old-table tokens become invalid by design (the project intentionally accepts this; no migration strategy invented). Legacy behavior for *new* pre-session tokens is preserved. ✓
- **Deployment note (unchanged)**: first real-DB deploy must apply `core.0002` + `payments.0003`; `authtoken` rows are not copied (accepted).

## 9. Payment Idempotency Audit

Request paths traced end-to-end (view → serializer → service → DB):

- A. First success → 201 + row. ✓
- B. Exact retry (header or body key, serialized) → 200 + original row, count stays 1. ✓ (covered)
- C/D/E/F. Retry with different amount/tenant/lease/date → 200 + **original** row (key-scoped, outcome-agnostic). ✓ (covered for body-differs; the unique constraint is the authority)
- G. Same key, different landlord → separate rows per landlord, never cross-leak. ✓ (covered)
- H. Missing key → no dedup, multiple payments allowed. ✓ (covered)
- I. Empty/whitespace key → normalized to `NULL`, stored as null. ✓ (covered)
- J. Oversized key → body path: serializer 400; header path: **was 500 → now 400** (B3). ✓ (new coverage)
- K. Invalid request with key → 400, no row, key not consumed. ✓ (new coverage)
- L. Mid-creation failure → `full_clean()`/IntegrityError handled inside `transaction.atomic`; no partial row. ✓
- M. Payment later cancelled → replay returns the original CANCELLED record (200), no duplicate, aggregate excludes it. ✓ (new coverage)
- N. Duplicate during transaction → see §10.
- O. Duplicate after commit → serialized replay → 200 + original. ✓

**Invariant holds:** for one `(landlord, idempotency_key)` there is never more than one Payment — enforced by `UniqueConstraint(landlord, idempotency_key)` (DB), with the two-phase service look-aside + IntegrityError fallback as defense-in-depth.

## 10. PostgreSQL Concurrency Reasoning

`record_payment` is `@transaction.atomic`; the idempotency look-aside is `select_for_update` on `(landlord, idempotency_key)`, then a unique-index-backed `INSERT` inside a nested `atomic()` (savepoint), with an `IntegrityError` fallback that re-selects by `(landlord, key)`.

Race trace (READ COMMITTED):

1. A and B call `POST /payments/` with the same key.
2. If a row already exists: the first requester's `select_for_update` locks it; the second blocks on that lock until commit, then its select returns the committed row → returns it (no insert, no error). ✓
3. If **no row exists yet** (both look-asides return empty): neither acquires a row lock — there is no row to lock. Both proceed to INSERT.
4. PostgreSQL: the second `INSERT` blocks on the first's uncommitted unique-index entry, then raises a **unique-violation at INSERT time** (Django uses a plain, non-deferred unique index). The nested savepoint rolls back, leaving the outer transaction usable. The fallback query then finds the committed original and returns it. ✓
5. Outcomes: exactly one Payment; the loser returns the same object; financial aggregates stay consistent; no `IntegrityError` escapes to the client; no transaction is left aborted; no cross-landlord row can be returned because lookups filter `landlord=request.user`.

**Residual observation:** client-visible 201-vs-200 status on the truly simultaneous race (the view's `replayed` bool was computed pre-commit) — left as is, per §4.

**SQLite note (unchanged):** a threaded race test in the test suite hits SQLite's single-writer lock (`database table is locked`) and is inherently flaky; documented in `payments/tests.py` `ConcurrentPaymentIdempotencyTests` and in the finalization report. The DB constraint + serialized-replay tests are the portable guarantees.

## 11. Permission / Isolation Audit

- `PaymentAccessPermission` — read: landlord/tenant/admin; write: landlord-only. Platform admin cannot create payments; their queryset (`landlord=user`) is empty, so no cross-tenant surface. ✓
- `PaymentCreateSerializer` — tenant queryset scoped to role TENANT; lease queryset scoped to **the authenticated landlord**; rent_period must belong to a landlord-owned lease; cross-field lease↔tenant/period checks. ✓
- Idempotency never bypasses ownership — replay lookups are always `landlord=request.user` (covered by `test_same_key_different_landlord_is_isolated`). ✓
- Payment/leases `PROTECT` FKs prevent dangling financial references. ✓
- No regression in platforms/blocks; admin list filtering by status/lease/tenant remains landlord-scoped. ✓

## 12. Migration / Database Audit

- `core/0002` and `payments/0003` match their models exactly (`makemigrations --check --dry-run` clean).
- Indexes: `DeviceSession.refresh_token_hash` unique+indexed; `(user, device_id)` unique; Payment has `(landlord, payment_date)`, `(tenant, payment_date)`, `(lease, payment_date)`, `(rent_period, status)`; the idempotency unique constraint yields the `(landlord, idempotency_key)` index.
- NULL semantics: `idempotency_key=NULL` rows are exempt from the unique constraint (intended — one null key = unlimited non-idempotent payments; PostgreSQL/MySQL NULLs-not-distinct caveat documented earlier, MySQL not in scope).
- FK deletion: Payment→user/lease PROTECT; rent_period SET_NULL; Token/user CASCADE; session/user CASCADE; session/access_token SET_NULL. ✓
- Reversibility: both migrations are reversible `CreateModel`/`AddField`+`AddConstraint` (database backends supporting `RemoveConstraint`). ✓
- SQLite test behavior does not hide a PostgreSQL correctness issue — the race is handled identically by unique-index + savepoint fallback on both engines; only the client-visible status differs (see §10).

## 13. API Contract Regression Audit

- `POST /auth/login/` → 200 `{user, token, refresh_token, device_id, expires_in}` — additive fields, intentional A1 contract. Same-device rotation is now the documented behavior.
- `POST /auth/register/`, `/refresh/`, `/logout/`, `/me/`, `/change-password/`, `/password-reset/*` — status codes unchanged; responses unchanged except the documented additive fields.
- `POST /payments/` — 201 (new) / 200 (replay); `PaymentSerializer` adds read-only `idempotency_key` (additive). No existing field removed or retyped; pagination, filtering, ordering untouched.
- Error envelope unchanged (`{detail, code, errors?}`); non-field auth errors keep the existing `invalid` code at the envelope (the SUSPENDED login error behaves identically — prior behavior preserved).
- Tenant/landlord/admin querysets and status-code semantics verified by the 616-green suite.

## 14. Security Configuration Audit

- `DEBUG=False` (production): throttles active (`ConditionalScopedRateThrottle` + scoped rates), security headers applied, `SECRET_KEY` fail-fast rejects the `django-insecure-*` default, `SECURE_SSL_REDIRECT`, HSTS, secure cookies, content-nosniff, referrer policy, proxy SSL header. ✓
- `DEBUG=True`: throttles intentionally disabled (dev/test ergonomics). ✓
- No hard-coded secret/token/password introduced by A1/A2 — diff-affirmed; only env-driven settings (`AUTH_TOKEN_EXPIRY_DAYS`, `AUTH_REFRESH_TOKEN_TTL_DAYS`, `AUTH_DEVICE_LIMIT`) plus the pre-existing dev default key/guard.
- `CORS_ALLOWED_ORIGINS` is explicit (no wildcard); `CORS_ALLOW_CREDENTIALS=True` with a fixed allow-list. The one defect (missing `idempotency-key`) is fixed.
- Token/refresh lifetimes: 7d access / 90d refresh / 20-device cap (env-configurable).

## 15. Test Coverage Gaps

Closed in this hunt:
- inactive user's **existing access token** rejected (`SuspendedUserSecurityTests.test_inactive_user_existing_access_token_rejected`).
- invalid request **with idempotency key** → 400, no row, key remains usable (`test_invalid_request_with_key_returns_400_no_payment`).
- **cancelled-payment replay** contract (`test_replay_after_cancel_returns_original`).
- CORS preflight allow-list for `idempotency-key` (B1 regression).
- oversize header key → 400 (B3 regression).
- login status gating for PENDING/DEACTIVATED with zero-credential assertion (B2 regression).
- atomic rollback of change-password on revocation failure (B4 regression).

Remaining deliberately-untested areas (no exploit/correctness consequence): PASETO-free race-status cosmetics, SQLite true-concurrency, multi-generation reuse, suspend mid-request.

## 16. Final Test Results

| Run | Result |
|-----|--------|
| Pre-hunt baseline full suite | **608/608 OK** (reconfirmed) |
| Affected modules after fixes (core.tests, core.tests_sessions, payments.tests) | 172/172 OK |
| **Final full backend suite** | **616 tests in 1552.272s — OK** (EXITCODE=0) |
| `python manage.py check` | 0 issues |
| `python manage.py makemigrations --check --dry-run` | **No changes detected** |

Test delta: 608 → **616** (+8: 5 bug-regressions, 3 coverage-gap tests).

## 17. Remaining Risks

1. **Concurrent same-key status code** remains 201-vs-200 in the pure race (accepted, invariant safe).
2. **MySQL null-unique semantics** if ever adopted (not in scope; SQLite/PostgreSQL fine).
3. **Old `authtoken`-era tokens** invalid after deployment (accepted design; no data migration).
4. **Login envelope** reports `invalid` (not `account_not_active`) for PENDING/DEACTIVATED at the top level — consistent with prior non-field-error behavior; a distinct client-facing code would be a contract change, deliberately not made.
5. **Everything A1/A2 + this hardening is uncommitted** — committing preserves the 616-green baseline (task forbids committing here).

## 18. Final Verdict

**READY_TO_COMMIT**

The prior reports were accurate; the hunt still uncovered and fixed 4 genuine defects (CORS header allow-list, login status gating, oversize-key 500, non-atomic password flows) plus closed 3 stated coverage gaps. The DB unique constraint remains the authoritative guard for payment idempotency; PostgreSQL race analysis shows exactly-one-Payment with no broken-transaction or isolation path. Suite green at 616, migrations and checks clean. Ready for the final commit, then Phase 11.

*No commit was created (per task). No Phase 11 work started. No architecture redesign.*
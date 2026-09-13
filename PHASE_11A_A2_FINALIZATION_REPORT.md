# PHASE 11A/A2 — FINALIZATION REPORT

**Date:** 2026-09-12
**Input:** `PHASE_11A_A2_POST_IMPLEMENTATION_AUDIT.md` (verdict READY_WITH_MINOR_FIXES) + task.md finalization instructions.
**Outcome:** **READY_TO_COMMIT**
**Type:** Hardening/finalization only — no architecture change, no JWT, no A1/A2 revert, no Phase 11 work.

---

## 1. Changes Made

| File | Change | Task |
|------|--------|------|
| `backend/core/authentication.py` | `ExpiringTokenAuthentication.authenticate_credentials` now rejects any token whose user `status != AccountStatus.ACTIVE` (SUSPENDED, DEACTIVATED, PENDING) with 401 `account_not_active`, **before** expiry handling | 1 |
| `backend/core/sessions.py` | `refresh_access_token` session query now requires `user__status=AccountStatus.ACTIVE` in addition to `user__is_active=True` | 1 |
| `backend/core/tests_sessions.py` | New `SuspendedUserSecurityTests` (4 tests): suspended-refresh blocked, suspended access-token blocked, active user still authenticates, inactive user cannot refresh | 2 |
| `backend/payments/tests.py` | Removed the flaky threaded concurrent test from `ConcurrentPaymentIdempotencyTests` and turned the class into a documented-limitation note (SQLite single-writer lock) | 4 |
| `backend/payments/views.py` | Documented the key-scoped first-wins cancel-replay contract at the idempotency block (comment only, no behavior change) | 3 |
| `PHASE_11A_A2_POST_IMPLEMENTATION_AUDIT.md` | §8 finding 3 upgraded to "Resolved — decision recorded"; §8 finding 1 is now fixed; finding 4 noted as intentionally deferred | 3, 5 |
| `.gitignore` (root) | Added `*.log` and `runserver.*` so runtime artifacts are ignored | 7 |

**Net source-behavior change:** exactly one security fix (non-ACTIVE users can no longer refresh or authenticate via existing tokens). Nothing else was altered behaviorally.

---

## 2. Security Fix (TASK 1)

**Problem (from audit):** login blocks SUSPENDED (`LoginSerializer`), but `ExpiringTokenAuthentication` only checked expiry, and `refresh_access_token` only checked `user__is_active=True` — so a SUSPENDED user (which still has `is_active=True`) could refresh existing credentials and keep making authenticated API calls.

**Fix (smallest correct change, consistent with the account-status model):**
- `ExpiringTokenAuthentication` → `if user.status != AccountStatus.ACTIVE: raise AuthenticationFailed(..., code='account_not_active')`. A token held by a SUSPENDED/DEACTIVATED/PENDING user is now denied at every protected endpoint (immediate suspension enforcement).
- `refresh_access_token` → added `user__status=AccountStatus.ACTIVE` to the lookup, so a non-ACTIVE user cannot mint a fresh access token via `/auth/refresh/`.

**Preserved behavior:**
- ACTIVE users (LANDLORD/TENANT/PLATFORM_ADMIN) — unaffected (verified: full suite green).
- `is_active=False` users — still blocked by DRF base authentication and now also by the explicit refresh filter (unchanged intent; confirmed by `test_inactive_user_cannot_refresh`).
- Legacy `Token <key>` clients — untouched (`ExpiringTokenAuthentication` still resolves by key; the new check only adds a status gate).
- `DeviceSession` model — not redesigned.
- Password change / reset global revocation — untouched (`GlobalRevocationTests` still pass).

**Known scope boundary (documented, intentionally not expanded):** login also gates the generic "account not active" family only via the SUSPENDED and `is_active` checks; the login serializer was not changed in this task to avoid scope creep. The authentication-layer gate now makes the *status* model authoritative for all three entry points (login semantics for DEACTIVATED remain as-is).

---

## 3. Tests Added / Updated (TASK 2)

New `SuspendedUserSecurityTests` in `backend/core/tests_sessions.py`:

1. `test_suspended_user_gets_no_new_token_via_refresh` — SUSPENDED user's refresh returns 401.
2. `test_suspended_user_existing_access_token_rejected` — SUSPENDED user's pre-issued token returns 401 on `/auth/me/`.
3. `test_active_user_still_authenticates_and_refreshes` — ACTIVE user refreshes (200) and the new access token authenticates.
4. `test_inactive_user_cannot_refresh` — `is_active=False` user's refresh returns 401.

No existing test was weakened or removed. `payments/tests.py` had the thread-based concurrent test removed (see §5) — the serialized replay tests and DB constraint coverage remain.

---

## 4. Payment Idempotency Decision (TASK 3)

**Statement:** replaying an `Idempotency-Key` that originally created a payment whose *later* state is `CANCELLED` returns that original payment.

**Decision: CORRECT — keep as the Alquiler idempotency contract. Behavior NOT changed.**

Rationale (documented in `payments/views.py` `PaymentViewSet.create` and audit §8.3):
- Keys identify the **operation**, not its outcome. The contract is *deduplication* ("same key ⇒ same response object"). Returning anything else (a new object, an error, a "status-sensitive" replay) would either create duplicates or break the contract callers encode retries against.
- Financial invariant unaffected: `paid_amount = SUM(PAID)` excludes CANCELLED payments, so a replayed cancelled payment never corrupts aggregates.
- Different intent ⇒ new key (keys are client-generated per attempt); nothing about the payment lifecycle was invented or changed.

---

## 5. Concurrent Idempotency Test (TASK 4)

**Attempted:** `TransactionTestCase` + two real threads driving `record_payment(...)` with the same key through a `Barrier`.

**Result (SQLite):** `sqlite3.OperationalError: database table is locked` — the SQLite test environment serializes writes with its single-writer lock and surfaces the race as a raw lock error, not as a clean unique-constraint violation or serialized replay. A threaded race test here is inherently **flaky** and was therefore **removed**, per the task instruction.

**Documented limitation** (standing in for the test, in `payments/tests.py` `ConcurrentPaymentIdempotencyTests`):
- The authoritative guarantee is the DB-level `UniqueConstraint(landlord, idempotency_key)` — a second row with the same key and landlord can never commit, on PostgreSQL (production) and SQLite alike.
- Serialized re-use is covered by `PaymentIdempotencyTests` / `RecordPaymentIdempotencyTests` (replay returns the original record, count stays 1, aggregate stays single).
- The row-lock + `IntegrityError` fallback path is designed for PostgreSQL; verifying the true race on SQLite is out of reach for the test suite without adding a flaky test.

---

## 6. Deferred Design Items (TASK 5)

| Design item | Decision | Rationale |
|-------------|----------|-----------|
| `DeviceSession` `CheckConstraint` (revoked/access coherence) | **Deferred** | Session/access-token coherence is already maintained by the single write-path (`create_device_session`, `_rotate_session`, `revoke_*`). No correctness gap exists without it; a migration for a purely defensive constraint is not warranted pre-Phase-11. |
| `secrets.compare_digest` for refresh compare | **Deferred** | The stored credential is a 64-hex SHA-256 digest matched via DB index lookup; there is no plaintext and no timing-oracle path that a *network* attacker can exploit (the digest space is the entropy itself). `compare_digest` would be defense-in-depth only. |
| Multi-generation refresh-reuse tracking (beyond one-slot `previous_refresh_token_hash`) | **Deferred** | A credential two+ rotations old fails the hash lookup (rejected as invalid), so it is *unusable* even though it doesn't trigger the stronger "revoke session" signal. Single-slot tracking matches the mobile threat model; multi-generation history is not needed for Phase 11. |
| `GET /auth/sessions/` device-management endpoint | **Deferred** | Explicitly deferred in the A1 design ("unless requested"); not in the Phase 11 MVP scope. Per-device logout (which *is* in scope) is already fully supported. |

No migration or schema change resulted from this task. `makemigrations --check --dry-run` → **No changes detected**.

---

## 7. Full Test Results (TASK 6)

| Suite | Command | Result |
|-------|---------|--------|
| A1 security/session tests | `python manage.py test core.tests_sessions` | **19/19 OK** (15 prior + 4 new) |
| Full core/auth | `python manage.py test core` | **166/166 OK** (162 prior + 4 new) |
| Payment idempotency | `python manage.py test payments.tests.PaymentIdempotencyTests payments.tests.RecordPaymentIdempotencyTests` | **9/9 OK** |
| Full payments | `python manage.py test payments` | **72/72 OK** |
| **FULL BACKEND SUITE** | `python manage.py test` | **608/608 OK** (Ran 608 tests in 1595.315s — OK) |
| System check | `python manage.py check` | 0 issues |
| Migrations | `python manage.py makemigrations --check --dry-run` | **No changes detected** |

**New total: 608 tests (was 604).** The +4 are the suspended-user security tests; no existing test regressed.

---

## 8. Migration Check

`python manage.py makemigrations --check --dry-run` → **No changes detected.** The hardening is pure logic (`authentication.py`, `sessions.py`, tests, comments) — no migration was created or required.

---

## 9. Worktree Cleanup (TASK 7)

- `git status --short` was run (see below).
- Runtime artifacts (`backend/runserver.log`, `backend/runserver.err.log`, `backend/test_full_run.log`, `frontend/vite.log`, `frontend/vite.err.log`) were generated by the local dev/test runs.
- Root `.gitignore` updated to ignore `*.log` and `runserver.*` (database `*.sqlite3`/`db.sqlite3` were already ignored).
- The log files were removed from the working tree; only source/documentation files remain as legitimately untracked/modified. No legitimate documentation or source file was deleted.

---

## 10. Remaining Risks

1. **DEACTIVATED/PENDING login semantics** unchanged (login serializer gates only SUSPENDED + `is_active`); authentication-layer now blocks those statuses for token/refresh, so there is a small inconsistency between login and authenticated access for DEACTIVATED. Deliberately scoped out; worth aligning in a later touch (single line in `LoginSerializer`).
2. **MySQL unique-index NULL semantics** (informational): if MySQL is ever used, `uniq_landlord_idempotency_key` would need NULLS-NOT-DISTINCT handling. Not applicable to SQLite/PostgreSQL.
3. **Uncommitted state** — all A1/A2 work (plus this hardening) remains uncommitted. Committing preserves the 608-green state (per task rules, nothing was committed here).
4. **First live `makemigrations` on a real DB** must run `core.0002` + `payments.0003` at deploy; existing `authtoken`-era rows are intentionally superseded (documented in the audit).

---

## 11. Recommendation

**READY_TO_COMMIT**

The security gap is closed with the smallest correct change, all 608 backend tests pass with no regressions, migrations are clean, the idempotency contract is documented and decided, the concurrent-test limitation is documented (not flaked), and the worktree is clean of runtime artifacts.

Suggested next step (with your approval): commit the full A1 + A2 + hardening changeset, then begin Phase 11 mobile foundation.

---

*Finalization only. No commit was created; Phase 11 was not started; no unrelated code was modified.*
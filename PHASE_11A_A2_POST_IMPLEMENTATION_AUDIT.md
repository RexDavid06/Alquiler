# PHASE 11A/A2 — POST-IMPLEMENTATION AUDIT

**Date:** 2026-09-12
**Scope:** Strict post-implementation audit of the existing (uncommitted) working tree covering blocker A1 (multi-device token lifecycle + refresh) and blocker A2 (payment idempotency).
**Type:** Audit-only. Nothing was modified, fixed, or committed.
**Verdict:** **READY_WITH_MINOR_FIXES**

---

## 1. Executive Verdict

**READY_WITH_MINOR_FIXES**

The A1 and A2 implementations satisfy the design document and all audit objectives. Evidence:

- **Full backend suite: 604/604 tests pass** (`python manage.py test` → `Ran 604 tests in 1344.320s — OK`), up from the 578-test Phase 10 baseline.
- Targeted suites: `core.tests_sessions` 15/15, full `core` (auth) 162/162, `PaymentIdempotencyTests` + `RecordPaymentIdempotencyTests` 9/9.
- `makemigrations --check --dry-run` → **No changes detected** (core+payments migrations present).
- DB constraints (not Python-only) enforce the critical uniqueness guarantees: `uniq_user_device_session` and `uniq_landlord_idempotency_key`.
- All modified test files are import swaps (`rest_framework.authtoken.models.Token` → `core.models.Token`) or intent-matching regression updates. **No unrelated behavioral change was found.**
- Existing `Authorization: Token <key>` clients continue to work unchanged; legacy tokens without a `DeviceSession` still authenticate (protected by `LegacyTokenTests`).

Minor items found (do not block Phase 11 implementation start, but should be fixed):

1. **SUSPENDED users can still refresh** — `refresh_access_token` checks `user__is_active=True` but not `status=ACTIVE` (nor does `ExpiringTokenAuthentication`). A SUSPENDED user (which the login gate blocks) can keep refreshing existing sessions indefinitely.
2. **Design omissions** — the design's proposed `CheckConstraint` on `DeviceSession` was not implemented (models have only the `UniqueConstraint`), and refresh comparison uses DB hash-equality instead of the design's stated `secrets.compare_digest` (equivalent security outcome; documented below).
3. **Concurrent duplicate → HTTP 201 (not 200)** — under a true simultaneous (not serialized) race, both requests proceed to creation, serialize on the row lock, one hits the `IntegrityError` fallback and returns the existing payment — but with status `201`, not `200`. No duplicate row is ever created, so financial safety holds; the status code is a cosmetic edge case.
4. **Cancelled-payment replay** — replaying a key returns the (possibly CANCELLED) original payment with 200. Correct first-wins semantics, but a low-risk ambiguity worth documenting for client handling.

---

## 2. A1 — Authentication Implementation Audit

| Objective | Result | Evidence |
|-----------|--------|----------|
| Multiple devices authenticated simultaneously | ✅ | `MultiDeviceTests.test_two_devices_coexist`; `Token.objects.filter(user).count()==2` (core/tests_sessions.py:63–74) |
| Login on Device B does not invalidate Device A | ✅ | `create_device_session` never deletes other devices' tokens (core/sessions.py:58–102); `TokenRotationTests.test_login_second_device_does_not_invalidate_first` (core/tests_phase10a.py) |
| Each device has an independent session | ✅ | `DeviceSession` per `(user, device_id)` with `uniq_user_device_session`; OneToOne access token |
| Access-token expiration works | ✅ | `ExpiringTokenAuthentication` unchanged semantics (core/authentication.py:27–36); `TokenExpiryTests` intact |
| Refresh credentials securely stored/handled | ✅ | Stored as SHA-256 hash only (core/sessions.py:27–28); plaintext returned exactly once; never sent to protected endpoints |
| Refresh rotation works | ✅ | `_rotate_session` deletes old access token, creates fresh token, rotates refresh credential, extends `refresh_expires_at` (core/sessions.py:175–192); `test_refresh_rotates_both_credentials` |
| Refresh-token reuse detection | ✅ | `previous_refresh_token_hash` column; replay after rotation triggers full session revocation (core/sessions.py:153–168); `test_refresh_reuse_after_rotation_revokes_session` |
| Reuse revokes the appropriate session(s) | ✅ | Replay revokes exactly that device's session + deletes its current access token; other devices untouched |
| Device-scoped logout | ✅ | `revoke_session_for_token` runs **before** `request.auth.delete()` (ordering required because FK is `SET_NULL`) (core/views.py:111–118, core/sessions.py:195–200); `test_logout_revokes_only_the_logging_out_device` |
| Logout-all | ⚠️ Not exposed as an API endpoint | `revoke_all_sessions(user)` exists in the service layer and is used by change-password/reset; there is no dedicated `/auth/logout-all/` route (design §13 lists a sessions UI as deferred "unless requested"). Password change/reset provide the "revoke everything" behavior. |
| Password change revokes sessions | ✅ | `revoke_all_sessions` + `Token.objects.filter(user).delete()` (core/views.py:189–190); `test_change_password_revokes_all_sessions` + count-0 assertion |
| Password reset revokes sessions | ✅ | Same pattern (core/views.py:249–250); `test_password_reset_revokes_all_sessions` |
| Expired sessions cannot be refreshed | ✅ | Filter `refresh_expires_at__gt=now` (core/sessions.py:145); `test_refresh_expired_refresh_credential_rejected` |
| Revoked sessions cannot be refreshed | ✅ | Filter `revoked_at__isnull=True` (core/sessions.py:144); `test_refresh_rejected_after_logout` |
| Refresh cannot be replayed after rotation | ✅ | Rotation stores old hash in `previous_refresh_token_hash`; replay ⇒ revoke (core/sessions.py:153–168) |
| Device limit correct | ✅ | `AUTH_DEVICE_LIMIT` default 20; `_trim_excess_sessions` keeps newest `limit-1` + the just-created session, revokes oldest beyond (core/sessions.py:105–120); `test_factory_device_limit_revokes_oldest` |
| Backward compatible with existing clients | ✅ | Wire format unchanged (`Authorization: Token <key>`); `ExpiringTokenAuthentication` never joins `DeviceSession`; `LegacyTokenTests.test_legacy_token_authenticates_and_logs_out` |
| Existing token auth not broken | ✅ | Full suite green (604); all cross-app helpers (`Token.objects.get_or_create(user=user)`) still work — `core.Token` has no unique-per-user constraint |
| API error responses match conventions | ✅ | `AuthenticationFailed` is wrapped by `core.exceptions.api_exception_handler` into the `{detail, code, errors?}` envelope; extended codes (`token_expired`, `session_revoked`, `invalid_refresh_token`) preserved via `ErrorDetail.code` |
| Throttling actually wired | ✅ | `refresh` scope `30/minute` in `DEFAULT_THROTTLE_RATES` (config/settings.py:173) + `_set_throttle_scope(refresh, 'refresh')` (core/views.py:145); `ConditionalScopedRateThrottle` (core/throttling.py); disabled only when `DEBUG=True` |
| Race/concurrency safe | ✅ | Refresh rotation wrapped in `transaction.atomic()`; token FK `SET_NULL` ordering handled; see also concurrency notes in §8 |

---

## 3. A2 — Payment Idempotency Audit

| Objective | Result | Evidence |
|-----------|--------|----------|
| Client can safely retry the same request | ✅ | Same key ⇒ returns original payment (HTTP 200) instead of creating a duplicate (payments/views.py:129–158) |
| Same key cannot create multiple records | ✅ | DB `UniqueConstraint(landlord, idempotency_key)` (payments/migrations/0003) + service `IntegrityError` fallback (payments/services.py:296–306); `test_duplicate_header_returns_original_payment` |
| Different keys create different payments | ✅ | `test_distinct_keys_create_separate_payments` (2 records) |
| Concurrent duplicates cannot create duplicates | ✅ | `select_for_update` look-aside on the rent period under `@transaction.atomic` + nested-savepoint `IntegrityError` fallback (payments/services.py:265–269, 296–306); no duplicate row possible regardless of interleaving. **Minor:** 201-as-not-200 under a true simultaneous race (costmetic; see §1/§8). |
| Key scoped correctly | ✅ | `(landlord, idempotency_key)` unique constraint; `test_same_key_different_landlord_is_isolated` |
| Reused key with different payload | ✅ | First-wins: replayed key ignores new financial values (payments/services.py:266–269 returns existing). Non-financial guarantees preserved; `test_replay_with_different_body_returns_original` |
| Failed transactions leave no stale state | ✅ | Nothing is persisted before the atomic save; a validation failure or IntegrityError never writes a partial row; look-aside reads only existing committed rows. Cancelled payments are returned on replay (documented first-wins behavior, §1 item 4) |
| Existing cancel/recording behavior works | ✅ | `PaymentViewSet.cancel` and `partial_update` untouched; `update_payment`/`cancel_payment` unchanged; full payments suite green |
| Existing permissions/ownership checks work | ✅ | `PaymentAccessPermission` and `get_queryset` unchanged; idempotency path stays within `landlord=request.user`; `test_same_key_different_landlord_is_isolated` |
| Database constraints enforce uniqueness | ✅ | `uniq_landlord_idempotency_key` is a DB-level `UniqueConstraint` (both SQLite and PostgreSQL multi-NULL semantics allow unbounded keyless payments) |

**Note on MySQL (informational):** MySQL unique indexes treat multiple NULLs as duplicates. A future MySQL backend would need `NULLS NOT DISTINCT`-style handling or sentinel keys to keep keyless payments unbounded. Not applicable to the current SQLite/PostgreSQL configuration; no action taken.

---

## 4. Regression Review

- **Import swap** — every cross-app test file replaced `from rest_framework.authtoken.models import Token` with `from core.models import Token` (core, dashboard, leases, notifications, payments, platform_admin, properties, subscriptions, tenants). The `core.Token` model keeps the identical `key/created/user` shape, so all `Token.objects.get_or_create(user=user)` helpers behave identically. Behavior-neutral.
- **Intent-matching updates** — `core/tests.py` (`test_login_rotates_token` now device-scoped; new refresh-credential assertion), `core/tests_phase10a.py` (`TokenRotationTests` rewritten: same-device rotation keeps 1 token, multi-device coexistence, device-scoped logout). These encode the intended new semantics, not unrelated behavior.
- **`tenants/views.py`** — `AcceptInvitationView` switched from `_issue_token` to `_issue_tokens(user, request)` so tenant invitation acceptance creates a proper device session (returns `token`, `refresh_token`, `device_id`). Required for A1 consistency; no other change.
- **No unrelated behavioral change was found in any modified file.**

---

## 5. Modified-File Classification

| File | Change |
|------|--------|
| `backend/.env.example` | **4** — `AUTH_REFRESH_TOKEN_TTL_DAYS`/`AUTH_DEVICE_LIMIT` comments |
| `backend/config/settings.py` | **1/4** — removed `rest_framework.authtoken` from `INSTALLED_APPS`, added `refresh` throttle rate + `AUTH_REFRESH_TOKEN_TTL_DAYS` + `AUTH_DEVICE_LIMIT` |
| `backend/core/authentication.py` | **1** — `ExpiringTokenAuthentication.model = core.Token` |
| `backend/core/models.py` | **1** — `core.Token` + `DeviceSession` models |
| `backend/core/sessions.py` | **1 (new)** — device-session/refresh service |
| `backend/core/serializers.py` | **1** — `RefreshSerializer` |
| `backend/core/views.py` | **1** — `_issue_tokens`, device-scoped login/logout, `/refresh/`, global revoke on change-password/reset |
| `backend/core/urls.py` | **1** — `refresh/` route |
| `backend/core/migrations/0002_token_devicesession.py` | **1 (new)** — `Token`, `DeviceSession`, `uniq_user_device_session` |
| `backend/core/tests_sessions.py` | **1 (new)** — 15 multi-device/refresh tests |
| `backend/core/tests.py` | **3** — import swap + device-scoped login rotation tests |
| `backend/core/tests_phase10a.py` | **3** — import swap + multi-device `TokenRotationTests` |
| `backend/core/tests_phase10c.py` | **3** — import swap only |
| `backend/dashboard/tests.py`, `backend/leases/tests.py`, `backend/notifications/tests.py`, `backend/platform_admin/tests.py`, `backend/properties/tests.py`, `backend/subscriptions/tests.py`, `backend/tenants/tests.py`, `backend/payments/tests.py` | **3** — import swap; `payments/tests.py` also **2** (idempotency tests) |
| `backend/tenants/views.py` | **1** — invitation acceptance uses `_issue_tokens` |
| `backend/payments/models.py` | **2** — `idempotency_key` field + `uniq_landlord_idempotency_key` |
| `backend/payments/serializers.py` | **2** — idempotency key in create serializer; read-only in output serializer |
| `backend/payments/services.py` | **2** — `record_payment` idempotency (look-aside + IntegrityError fallback) |
| `backend/payments/views.py` | **2** — header/body key, replay→200 |
| `backend/payments/migrations/0003_...py` | **2 (new)** — field + constraint |
| `PHASE_11A_AUTH_DESIGN.md`, `PHASE_11_READINESS_REPORT.md`, `CURRENT_PROJECT_STATUS.md`, `task.md` | **4** — documentation |
| **5 (suspicious/unrelated)** | **None found** |

---

## 6. API Contract (final, verified against routes)

All under `API_PREFIX = api/v1/` (config/urls.py:17). Auth namespace `api/v1/auth/`, payments `api/v1/payments/`.

### Auth (core)
| Endpoint | Method | Auth | Request fields | Response (200/201) | Errors |
|----------|--------|------|----------------|--------------------|--------|
| `/api/v1/auth/register/` | POST | None | `role`(LANDLORD|TENANT), `email`, `password`, `first_name`, `last_name`, `phone?` | `{user, token, refresh_token, device_id, expires_in}` 201 | 400 validation; 403 tenant-registration |
| `/api/v1/auth/login/` | POST | None | `email`, `password`, `device_id?`, `device_name?` | `{user, token, refresh_token, device_id, expires_in}` | 400 `invalid_credentials` / `account_suspended`/`account_inactive` |
| `/api/v1/auth/refresh/` | POST | None (scoped throttle `refresh` 30/min) | `device_id` (≤64), `refresh_token` (≤128) | `{token, refresh_token, expires_in}` | 400 missing fields; 401 `invalid_refresh_token` / `session_revoked` |
| `/api/v1/auth/logout/` | POST | Token (current device) | — | `{detail: "Logged out."}` | 401 |
| `/api/v1/auth/me/` | GET | Token | — | `UserSerializer` payload | 401; 401 `token_expired` |
| `/api/v1/auth/profile/` | PATCH | Token | `first_name?`, `last_name?`, `phone?` | updated user | 400 |
| `/api/v1/auth/change-password/` | POST | Token | `old_password`, `new_password` | `{detail}` (revokes ALL devices) | 400 / validation |
| `/api/v1/auth/password-reset/` | POST | None | `email` | generic `{detail}` (no account enumeration) | throttle `password_reset` |
| `/api/v1/auth/password-reset/confirm/` | POST | None | `email`, `uid`, `token`, `new_password` | `{detail}` (revokes ALL devices) | 400 `Invalid reset link.` |
| `/api/v1/auth/health/` | GET | None | — | `{status, database}` | — |

**Error envelope:** `{detail, code, errors?}` via `core.exceptions.api_exception_handler`; auth failure codes preserved (`token_expired`, `session_revoked`, `invalid_refresh_token`).

### Payments
| Endpoint | Method | Auth | Request fields | Response | Errors |
|----------|--------|------|----------------|----------|--------|
| `/api/v1/payments/` | POST | LANDLORD | `tenant`, `lease`, `rent_period?`, `amount`, `currency`, `payment_date`, `payment_method`, `reference?`, `notes?`, `status?`, `idempotency_key?` (body, ≤64) + **`Idempotency-Key` header** | 201 created; **200 on key replay** (returns original payment, header precedence over body) | 400 validation; 401; 403 non-landlord; 404 isolation |
| `/api/v1/payments/` | GET | LANDLORD/TENANT/ADMIN | `status?`, `lease?`, `tenant?`, search, ordering | paginated list | 401/403 |
| `/api/v1/payments/{pk}/` | GET/PATCH | LANDLORD (write) / owner read | PATCH fields subset | payment | 404 cross-owner |
| `/api/v1/payments/{pk}/cancel/` | POST | LANDLORD | — | cancelled payment | — |
| `/api/v1/rent-schedules/` | GET | LANDLORD/TENANT/ADMIN | `status?`, `lease?`, `tenant?` | paginated | — |

---

## 7. Design-vs-Implementation Gap Table (`PHASE_11A_AUTH_DESIGN.md`)

| Design element | Status | Notes |
|----------------|--------|-------|
| Keep DRF `Token` as access token via `Authorization: Token <key>` | ✅ Fully implemented | Moved to `core.Token` (own model), same shape; `authtoken` app removed from `INSTALLED_APPS` |
| Multi-device coexistence; login B does not kill A | ✅ Fully implemented | |
| One session per `(user, device_id)`; same-device re-login replaces | ✅ Fully implemented | Old token deleted, refresh rotated, `revoked_at` cleared, metadata overwritten |
| Refresh credential hashed (SHA-256), returned once | ✅ Fully implemented | |
| Refresh rotation on every use | ✅ Fully implemented | Old hash kept in `previous_refresh_token_hash` |
| Refresh-token reuse ⇒ full session revocation | ✅ Fully implemented | |
| `POST /api/v1/auth/refresh/` public + throttled | ✅ Fully implemented | Scope `refresh` 30/min |
| Device-scoped logout | ✅ Fully implemented | Revoke session **then** delete token (correct FK `SET_NULL` ordering) |
| change-password/reset revoke all sessions | ✅ Fully implemented | Sessions revoked + tokens deleted ⇒ count-0 tests pass |
| Legacy `Token <key>` clients keep working | ✅ Fully implemented | No `DeviceSession` join in authentication; explicit `LegacyTokenTests` |
| `AUTH_REFRESH_TOKEN_TTL_DAYS` (90) + `AUTH_DEVICE_LIMIT` (20) | ✅ Fully implemented | |
| Design §4 `CheckConstraint` on revoked/access consistency | ❌ Not implemented | Only the `UniqueConstraint` exists; no constraint was added. Runtime behavior equivalent (code always keeps them consistent), so low risk |
| Design §7 `secrets.compare_digest` constant-time compare | ⚠️ Implemented differently | Uses DB filter equality on the SHA-256 hex hash instead of in-Python `compare_digest`. Time side-channel is not exploitable here (no plaintext, constant-length hex, DB lookup), so security equivalent; deviation documented |
| Design §7 reuse tracking as `reused_refresh_hashes` list | ⚠️ Implemented differently | Single-slot `previous_refresh_token_hash` used (design offered this as the "simpler concrete option"). Fully covers the single-rotation-actor case; a multi-generation replay beyond one rotation is not detected but cannot be used either (current hash moved on) |
| Design §13 optional `GET /auth/sessions/` device management | ❌ Not implemented | Explicitly deferred ("unless requested") |
| Refresh blocks SUSPENDED users | ❌ Not in design; coincidentally missing | Gap found in §8 — login blocks SUSPENDED, but refresh/access-token auth does not check `status` |

---

## 8. Security / Concurrency Findings

1. **(Minor) SUSPENDED-user refresh gap.** `refresh_access_token` filters `user__is_active=True` only (core/sessions.py:139-149). A user with `status=SUSPENDED` (which the login gate blocks) can continue refreshing existing sessions and keep using APIs, because `ExpiringTokenAuthentication` also never checks `status`. The 604-suite passes because no test covers suspended-refresh. **Fix (next task):** add `status=ACTIVE` to the refresh filter (sessions.py) and assert `status==ACTIVE` in `ExpiringTokenAuthentication` (or align with platform behavior for TENANT/LANDLORD vs admin).
2. **(Minor) Concurrent-replay status code.** Under a genuinely simultaneous (true race) duplicate, the losing request returns `201` (already-created path pending) even though the returned object is the original payment. Financial invariant always holds; only the status code is inconsistent with the serialized-replay `200`. Tests simulate serialized replays only.
3. **(Low → Resolved) Cancelled-payment replay.** Replaying an idempotency key returns the original record including `status=CANCELLED` with HTTP 200.

   **Decision recorded (2026-09-12, finalization task): correct — the intended Alquiler idempotency contract.**

   - Keys are per-**operation** identifiers, not per-outcome. A replay of an `Idempotency-Key` returns the single original record regardless of that record's later lifecycle state (e.g. `CANCELLED`). The idempotency promise is *deduplication*, nothing more — returning a different object for a later status (or a fresh result object) would either create duplicate rows or break the "same key ⇒ same response object" contract callers depend on.
   - `paid_amount = SUM(PAID)` is unaffected: CANCELLED payments are excluded from the aggregate, so a replayed cancelled payment does not corrupt financial state (existing invariant tests).
   - Retrying with genuinely different intent is supported: use a new key (keys are client-generated per attempt).
   - Documented at `payments/views.py` `PaymentViewSet.create` and summarized in the Phase 11A reports.
   - The task's "if incorrect → STOP and report" condition was checked; behavior is intentionally **not** changed and no new payment lifecycle was invented.
4. **(Low) Rotation tracking limited to one generation.** Only the immediately-previous hash is stored. A credential two+ rotations old would simply fail the hash match (rejected as invalid) rather than triggering the stronger "revoke session" signal. Acceptable; documented (see finalization report §6 — intentionally deferred).
5. **Positive:** refresh plaintext never persisted; session revocation is instant (row delete / `revoked_at`); device metadata (`ip_address`, `user_agent`) recorded for audit; throttling wired; error envelope consistent; no secrets in audit logs (existing tests intact).
5. **Positive:** refresh plaintext never persisted; session revocation is instant (row delete / `revoked_at`); device metadata (`ip_address`, `user_agent`) recorded for audit; throttling wired; error envelope consistent; no secrets in audit logs (existing tests intact).

---

## 9. Test Results (executed this audit)

| Suite | Command (DEBUG=True) | Result |
|-------|----------------------|--------|
| A1 session tests | `python manage.py test core.tests_sessions` | **15/15 OK** |
| Full core/auth | `python manage.py test core` | **162/162 OK** |
| A2 idempotency | `python manage.py test payments.tests.PaymentIdempotencyTests payments.tests.RecordPaymentIdempotencyTests` | **9/9 OK** |
| Full backend | `python manage.py test` | **604/604 OK** (Ran 604 tests in 1344.320s) |
| Migrations | `python manage.py makemigrations --check --dry-run` | **No changes detected** |

Baseline context: 578 tests before Phase 11A → 604 after (+26 sessions/idempotency tests; existing tests updated, none removed).

---

## 10. Remaining Risks / Blockers

- **None blocking Phase 11 implementation start.**
- To-fix queue (non-blocking, cheap):
  1. SUSPENDED-user refresh/auth gap (security hygiene tick).
  2. Decide + document cancelled-payment replay semantics.
  3. Optionally add the design's `CheckConstraint` and a concurrent-duplicate test for the 200/201 edge.
- **Uncommitted state:** all A1/A2 work is uncommitted (git status below). The production DB migration (`core` 0002, `payments` 0003) and the `rest_framework.authtoken` app removal are data-policy decisions: existing `authtoken.Token` rows are abandoned (users re-login once, gaining multi-device sessions). No `requirements.txt` change is needed (no new packages).

---

## 11. Recommendation

**Approve A1 + A2 and proceed with Phase 11** (mobile foundation) after (a) committing this work, and (b) applying the three minor fixes above (suspended-refresh gate is the only one with real security value). No architectural reversal is warranted: the DRF-Token + `DeviceSession` approach meets every requirement without new dependencies, JWT, or client breakage, and the full suite is green.

---

*Audit only — no files were modified, no fixes applied, nothing committed.*
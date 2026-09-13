# PHASE 11A — AUTH DESIGN: MULTI-DEVICE TOKEN LIFECYCLE + TOKEN REFRESH

**Date:** 2026-09-11
**Phase:** 11A-0 (design only — no implementation)
**Status:** DESIGN — pending approval
**Related blocker:** A1 from `PHASE_11_READINESS_REPORT.md` (multi-device token lifecycle / token refresh)
**Source material:** `backend/core/authentication.py`, `backend/core/models.py`, `backend/core/serializers.py`, `backend/core/views.py`, `backend/core/urls.py`, `backend/config/settings.py`, `backend/core/tests.py`, `backend/core/tests_phase10a.py`, plus the `Token.objects...` usage scan across all apps and tests.

---

## 1. Current Architecture (audit summary)

Authentication today is **single-session DRF Token auth** with server-side expiry, built entirely on `rest_framework.authtoken`.

### How tokens are created
- `backend/core/views.py:27-30` — `_issue_token(user)`:
  ```python
  Token.objects.filter(user=user).delete()   # delete ALL existing tokens
  return Token.objects.create(user=user).key
  ```
  Called by `login` (line 76) and `register` (line 58). This is **single-token rotation**: any login deletes every previous token for the user.
- No other production code creates tokens. All other references to `rest_framework.authtoken.models.Token` are in **tests only** (via `Token.objects.get_or_create(user=user)` helpers in `core/tests.py:37`, `properties/tests.py:36`, `tenants/tests.py:47`, `leases/tests.py:44`, `payments/tests.py:55`, `notifications/tests.py:72`, `subscriptions/tests.py:69`, `dashboard/tests.py:58`, `platform_admin/tests.py:47`, and `core/tests_phase10a.py`/`_phase10c.py`).

### How tokens are stored
- Default DRF `rest_framework.authtoken.models.Token` table (key, user FK, `created`). No custom token columns, no device metadata, no refresh credential — anything.

### How expiration is checked
- `backend/core/authentication.py:14-31` — `ExpiringTokenAuthentication(TokenAuthentication)`.
  - `authenticate_credentials(key)` calls the DRF parent, then rejects tokens whose `created < now - AUTH_TOKEN_EXPIRY_DAYS`.
  - Expired tokens are **deleted on detection** (`token.delete()`).
  - Setting: `AUTH_TOKEN_EXPIRY_DAYS = env.int('AUTH_TOKEN_EXPIRY_DAYS', default=7)` (`settings.py:297`). Wired as the only `DEFAULT_AUTHENTICATION_CLASS` (`settings.py:153-155`).

### What login does to existing tokens
- `views.py:76` calls `_issue_token` → **deletes every existing token for the user** and issues one fresh key. Logging in on device B kills device A's session. Verified by `TokenRotationTests` (`core/tests_phase10a.py:213-276`): `test_login_invalidates_old_token`, `test_old_token_rejected_after_rotation`, `test_repeated_login_no_multiple_tokens`.

### What logout does
- `views.py:87-95` — `request.auth.delete()`. Revokes exactly the presented token. Verified by `LogoutApiTestCase` (`core/tests.py:294-308`).

### What change-password does
- `views.py:131-140` — deletes all password, then `Token.objects.filter(user=request.user).delete()` (line 139) — **revokes every session**. Verified by `test_change_password_invalidates_old_token` (`core/tests.py:473-481`, asserts token count 0).

### What password-reset-confirm does
- `views.py:186-200` — sets new password, then `Token.objects.filter(user=user).delete()` (line 199) — **revokes every session**. Verified by `test_password_reset_confirm_invalidates_all_tokens` (`core/tests.py:642-650`).

### How authentication identifies the user
- DRF `TokenAuthentication` → `Token.key` → `Token.user` → `request.user`. Header format: `Authorization: Token <key>`.

### All token/session revocation points (inventory)
| Location | Trigger | Scope |
|----------|---------|-------|
| `core/views.py:29` (`_issue_token`) | login / register | All tokens for the user |
| `core/views.py:139` | change-password | All tokens for the user |
| `core/views.py:199` | password-reset-confirm | All tokens for the user |
| `core/views.py:93` | logout | Only the presented token |
| `core/authentication.py:27` | expired token detected | Only that token |

### Existing tests covering these behaviors
| Test class | File | Covers |
|-----------|------|--------|
| `AuthApiTestCase` | `core/tests.py:44-279` | register issues token, login rotates token, invalid old token after rotation |
| `LogoutApiTestCase` | `core/tests.py:283-310` | logout deletes the token |
| `ChangePasswordApiTestCase` | `core/tests.py:452-538` | change-password deletes all tokens |
| `PasswordResetConfirmApiTestCase` | `core/tests.py:616+` | reset deletes all tokens |
| `TokenExpiryTests` | `core/tests_phase10a.py:131-206` | 7-day expiry, deletion on detection, boundary cases |
| `TokenRotationTests` | `core/tests_phase10a.py:213-276` | single-token-per-user rotation, old token rejection |
| Cross-app helpers | all `*/tests.py` | `Token.objects.get_or_create(user=user)` direct-token usage |

---

## 2. Identified Problems

1. **No multi-device coexistence.** Login rotates the single token (`_issue_token`, `views.py:29`). Logging in on a phone logs out the web session, and vice versa.
2. **No refresh mechanism.** Tokens expire after `AUTH_TOKEN_EXPIRY_DAYS = 7` with no way to renew without a full password re-login; re-login then invalidates all other devices (1 + 2 combine into the mobile deal-breaker).
3. **No per-device revocation.** Logout kills only the presented token, which is correct, but there is no device identity — a user cannot separately manage "this laptop" vs "this phone", and there is nothing to revoke except the raw token.
4. **No refresh credential.** Requirement 8 of the task (refresh credentials must be stored securely, not as long-lived access tokens) is unmeetable in the current model — the only credential is the access token itself.
5. **No reuse protection.** There is nothing to detect a stolen/rotated credential being replayed.

---

## 3. Proposed Architecture

**Decision: extend the existing DRF TokenAuthentication system with a lightweight device/session layer. Do NOT adopt JWT.**

### Why not JWT
| Consideration | DRF Token + DeviceSession (chosen) | JWT |
|----------------|-------------------------------------|-----|
| New dependency | **None** (uses installed `rest_framework.authtoken`) | Requires `PyJWT`/`SimpleJWT` install + config (task forbids new deps unless proven necessary) |
| Existing `Token <key>` clients | Continue working unchanged | New header format → all clients migrate |
| Instant revocation | Deleting a row instantly kills the token (already the pattern) | Needs denylist/short-TTL machinery or token version claims |
| Server-side expiry | Already implemented (`ExpiringTokenAuthentication`) | Need new validation logic |
| Existing 578 tests | Stay green (helpers create plain DRF tokens) | Many token tests need rewriting |
| Match architecture doc decision | "Token auth over JWT — sufficient for mobile clients" (`ALQUILER_ARCHITECTURE.md` §16) | Contradicts documented decision |

### The model at a glance
- **Access token** = the existing DRF `Token` (kept verbatim, still sent via `Authorization: Token <key>`, still expiring via `AUTH_TOKEN_EXPIRY_DAYS`).
- **Session** = new `core.DeviceSession` row per device: ties one access token to a client-supplied `device_id`, and holds a **hashed refresh credential** used only by the refresh endpoint.
- **Refresh** = `POST /api/v1/auth/refresh/` exchanges (device_id + refresh credential) for a new access token + a **rotated** refresh credential.

A user may hold **many** `DeviceSession` rows, hence many valid access tokens — one per device — all coexisting.

---

## 4. Data Model Changes

New model in `core/models.py`:

```
class DeviceSession(models.Model):
    user                 = FK(AUTH_USER_MODEL, related_name='device_sessions', on_delete=CASCADE)
    access_token         = OneToOneField(rest_framework.authtoken.models.Token,
                                         on_delete=CASCADE, related_name='device_session', null=True)
    device_id            = CharField(max_length=64)        # client-generated opaque device identifier
    device_name          = CharField(max_length=100, default='')   # e.g. "Chrome on Windows", "iPhone 15"
    refresh_token_hash   = CharField(max_length=64, unique=True, db_index=True)  # SHA-256 hex of the refresh credential
    refresh_expires_at   = DateTimeField()
    created_at           = DateTimeField(auto_now_add=True)
    last_used_at         = DateTimeField(null=True, blank=True)
    revoked_at           = DateTimeField(null=True, blank=True)
    ip_address           = GenericIPAddressField(null=True, blank=True)   # metadata for audit
    user_agent           = CharField(max_length=255, default='')          # metadata for audit

    class Meta:
        constraints = [
            UniqueConstraint(fields=['user', 'device_id'], name='uniq_user_device'),
            CheckConstraint(check=Q(revoked_at__isnull=True) | ~Q(access_token__isnull=True, ...), name=...),
        ]
```

### Design rules
- **One active session per (user, device_id).** Re-login from the same device replaces that device's session (revokes the old access token) instead of stacking sessions — bounds token growth.
- **Refresh credential is stored as SHA-256 hash only** (`secrets.compare_digest` on compare; plaintext returned to the client exactly once). A DB leak cannot replay refresh tokens.
- **Refresh credentials rotate on every use** (requirement 9). A rotated-out refresh token presented again ⇒ the session is treated as compromised and **fully revoked** (both access token and new refresh credential).
- The DRF `Token` table is **not modified**; existing rows remain valid access tokens even if they have no `DeviceSession` (legacy/backward-compatible — see §9).

### New settings
- `AUTH_REFRESH_TOKEN_TTL_DAYS = env.int('AUTH_REFRESH_TOKEN_TTL_DAYS', default=90)` — lifetime of a refresh credential.
- `AUTH_TOKEN_EXPIRY_DAYS` (already exists, default 7) — access-token lifetime, unchanged.
- Optional: `AUTH_DEVICE_LIMIT = env.int('AUTH_DEVICE_LIMIT', default=20)` — cap active sessions per user (defensive; newest wins).

---

## 5. Token Lifecycle

```
Login/Register
   │  creates access token (DRF Token, 7-day expiry)
   │  creates DeviceSession (one per user+device_id)
   │  generates refresh credential (returned once, stored hashed, 90-day expiry)
   ▼
  ACTIVE ──(access expiry)──────────────► REFRESH via /auth/refresh/
                                            └► rotates access token + refresh credential
   │
   ├── logout (this device only)         ──► REVOKED (access token + session)
   ├── refresh credential reused after rotation ──► REVOKED (security event)
   ├── refresh credential expired        ──► REVOKED (requires full re-login)
   ├── change-password                   ──► ALL sessions REVOKED
   └── password-reset-confirm            ──► ALL sessions REVOKED
```

- **Access token** (7 days): presented on every API call; checked by existing `ExpiringTokenAuthentication`, which deletes expired tokens on detection.
- **Refresh credential** (90 days): never sent to protected endpoints; only to `POST /api/v1/auth/refresh/`.
- Expired access + valid refresh ⇒ silent renewal, no password prompt. Expired/revoked refresh ⇒ full re-login.

---

## 6. Login Flow (per device)

`POST /api/v1/auth/login/` — body optionally includes `device_id` and `device_name`.

1. Validate credentials exactly as today (`LoginSerializer`, suspended/inactive checks unchanged).
2. If `device_id` is absent, generate one server-side (`secrets.token_hex(16)`) and return it — **backward compatible**.
3. Find or create the session for `(user, device_id)`:
   - Existing session found ⇒ delete its old access token and revoke the old session (same-device re-login replaces it; no other device is touched).
4. Create a fresh DRF access token (`Token.objects.create(user=user)` — **no longer deletes other tokens**).
5. Create/update the `DeviceSession` with a new refresh credential hash + expiry.
6. Respond (additive to the existing `{user, token}` contract):
   ```json
   { "user": {...}, "token": "<access>", "device_id": "<id>", "refresh_token": "<once-only>", "expires_in": 7*86400 }
   ```

Register (`POST /api/v1/auth/register/`) follows the same path (fresh account, one session).

---

## 7. Refresh Flow

`POST /api/v1/auth/refresh/` — **public endpoint** (AllowAny) with its own throttle scope.

Request body: `{ "device_id": "...", "refresh_token": "..." }`

1. Look up `DeviceSession` by `(user?)` — session identified by `device_id` joined with its hashed refresh credential.
   - Fetch sessions for `device_id`, compare `sha256(refresh_token)` against `refresh_token_hash` using `secrets.compare_digest`.
2. Reject (401, code `session_revoked`) if: session missing, `revoked_at` set, refresh expired, or the presented hash matches a **previously rotated** hash (reuse detection ⇒ revoke session fully and reject).
3. Rotate:
   - Delete the session's current access token, create a new DRF access token.
   - Generate a new refresh credential; store its hash; keep the OLD refresh hash in a `reused_refresh_hashes` list (or a separate small table / JSON field) for reuse detection. Simpler concrete option: keep `previous_refresh_token_hash` (single-slot) on the session — a match against it triggers full revocation.
4. Update `last_used_at`, `ip_address`, `user_agent`.
5. Respond:
   ```json
   { "token": "<new access>", "refresh_token": "<new once-only>", "expires_in": 7*86400 }
   ```

Success path never requires the password; it is therefore throttled (new scope `refresh`, e.g. `30/minute`).

---

## 8. Logout Flow

`POST /api/v1/auth/logout/` — authenticated with the access token.

1. As today: `request.auth.delete()` — deletes only the presented access token.
2. New: revoke the `DeviceSession` that owns that access token (`revoked_at = now`) and delete/`revoked_at` its refresh credential so it can no longer be used to refresh.

**Only this device is affected.** Other devices' sessions and access tokens remain valid.

---

## 9. Password-Change and Password-Reset Flows

Both already delete all DRF tokens for the user (`views.py:139`, `views.py:199`). Extend them to also revoke **all** `DeviceSession` rows for the user (`revoked_at = now`) — this is the intended "kill everything" security behavior and matches the current tests' expectation that token count drops to 0 after each.

No external contract change: the endpoints still behave identically from a client's perspective, and the frontend `change-password` flow continues to force re-login.

---

## 10. Token Expiration Policy

| Credential | Lifetime | Who sets it | Notes |
|-----------|----------|-------------|-------|
| Access token (DRF `Token`) | `AUTH_TOKEN_EXPIRY_DAYS` = **7 days** (default) | existing settings | Enforced by `ExpiringTokenAuthentication`; deleted on detection |
| Refresh credential | `AUTH_REFRESH_TOKEN_TTL_DAYS` = **90 days** (new) | new setting | Stored hashed; rotated each refresh; single refresh credential per device session |

Policy is therefore: **access tokens are short-lived; sessions are long-lived but always revocable, replacing the old "re-login every 7 days or share one token" trade-off.**

---

## 11. Multi-Device Behavior

- User can hold N active access tokens (one per `(user, device_id)`), each independently revocable.
- Login from device B does **not** touch device A's token or session.
- Re-login from the **same** device id replaces only that device's session (prevents unbounded token growth).
- Data isolation and role enforcement are server-side queryset/permission logic that operate on `request.user` — **completely unaffected** by the session change (requirements 10, and LANDLORD/TENANT/PLATFORM_ADMIN behavior preserved).

---

## 12. Security Considerations

- **Refresh credential never stored in plaintext** — SHA-256 hash only, compared with `secrets.compare_digest` (constant-time).
- **Rotation defeats replay** — a presented credential is valid for exactly one refresh; reuse ⇒ full session revocation (compromise detection).
- **Access tokens remain short-lived** and are broadcast as little as possible (sent only on protected endpoints).
- **Revocation is instant** — deleting the token row / setting `revoked_at` takes effect on the very next request (no JWT denylist needed).
- **Suspended/revoked users** — unchanged from today: login rejects SUSPENDED/inactive; `AuthenticationMiddleware` + DRF still validate `is_active`. (Existing valid tokens of a suspended user remain valid until expiry/detection — same behavior as today, out of scope for this phase.)
- **Throttling** — new `refresh` scope, plus existing login/register/reset scopes.
- **Audit log** — optional detail fields (`device_name`, `ip_address`, `user_agent`) support future "sessions" UI and forensics. No credentials ever enter `AuditLog` (existing sanitisation tests unaffected).
- **Client storage** — refresh credential must be stored in OS keychain (Expo SecureStore / web localStorage backup) and never written to plain logs. This is a 11A-client concern; the design only mandates it must not be treated as a plain long-lived access token.

---

## 13. API Endpoint Changes

| Endpoint | Change | Backward compatibility |
|----------|--------|------------------------|
| `POST /api/v1/auth/register/` | Also creates a `DeviceSession`; response gains `refresh_token` + `device_id` | Additive; `{user, token}` still present |
| `POST /api/v1/auth/login/` | Accepts optional `device_id` / `device_name`; stops deleting other devices' tokens; returns `refresh_token` + `device_id` | Additive + strictly better (logins no longer log each other out) |
| `POST /api/v1/auth/refresh/` | **NEW** — exchange `{device_id, refresh_token}` for fresh access + rotated refresh | New endpoint |
| `POST /api/v1/auth/logout/` | Now also revokes the owning `DeviceSession` (this device only) | Request/response shape unchanged |
| `POST /api/v1/auth/change-password/` | Also revokes all `DeviceSession` rows | Request/response shape unchanged |
| `POST /api/v1/auth/password-reset/confirm/` | Also revokes all `DeviceSession` rows | Request/response shape unchanged |
| `GET /api/v1/auth/me/` + all protected endpoints | No change (`Authorization: Token <key>` still the only auth mechanism) | Not affected |
| `GET /api/v1/auth/sessions/` (optional, nice-to-have) | NEW — list own devices with revoke-by-device | Deferred unless requested |

---

## 14. Backward Compatibility Considerations

- **Wire format unchanged:** every protected endpoint still expects `Authorization: Token <key>`; the only header ever introduced, `Idempotency-Key`, belongs to blocker A2 (not this phase).
- **Existing clients that never call refresh** keep working exactly as before — token valid for 7 days, then re-login. Only improvement: login no longer evicts their other devices.
- **Legacy tokens without a `DeviceSession`** (created via the test helpers / pre-existing rows) remain valid access tokens until they expire or are revoked by change-password/reset. They simply have no refresh capability. This keeps all 578 backend tests green without edits (helpers use `Token.objects.get_or_create`, which the proposed code never deletes indiscriminately anymore).
- **Tests whose expectations change** must be updated in implementation, and they represent the *intended* new behavior:
  - `TokenRotationTests.test_login_invalidates_old_token`, `test_old_token_rejected_after_rotation`, `test_repeated_login_no_multiple_tokens`, `test_login_creates_fresh_token`/`test_login_new_token_authenticates` (still true) — the "rotation kills everything" tests become "separate device sessions coexist" tests.
  - `AuthApiTestCase.test_login_rotates_token` (still true for a single device).
  - `core/tests.py` login helpers that assume one token per user (`Token.objects.get(user=user)`) need a device-scoped helper.
  - `TokenExpiryTests` (unchanged — expiry logic untouched) and `LogoutApiTestCase` (still true for a lone device; add a second-device case).

---

## 15. Migration Requirements

- **One new migration** in `core` creating `DeviceSession` (fields + `uniq_user_device` constraint + refresh-hash index). No changes to existing tables; no changes to the `authtoken` app.
- Optionally one `data` migration to backfill nothing (there is no session data to migrate).
- Settings addition `AUTH_REFRESH_TOKEN_TTL_DAYS` (add to `backend/.env.example`).
- `makemigrations --check --dry-run` must stay clean after implementation.

---

## 16. Tests Required (implementation phase)

New dedicated work (in `core/test_sessions.py` or extended `core/tests*.py`):

1. **Two-device coexistence:** login device A then device B ⇒ both tokens authenticate; logging in on B does not invalidate A's token or session.
2. **Same-device re-login:** login twice with the same `device_id` ⇒ the first session is revoked, the second is active (session count for that device stays 1).
3. **Device-scoped logout:** device A logs out ⇒ A's token 401s and A's refresh fails; B still authenticates and can refresh.
4. **Refresh success:** valid (device_id, refresh_token) ⇒ new access token works, old access token no longer works, refresh token was rotated.
5. **Refresh with expired access token:** 8-day-old access token + valid refresh ⇒ 200 (no re-login).
6. **Refresh token expiry:** backdated `refresh_expires_at` ⇒ 401, requires re-login.
7. **Refresh-token reuse detection:** replay a rotated-out refresh token ⇒ 401 and the whole session (incl. current access token + newest refresh) is revoked.
8. **Revoked session refresh:** `revoked_at` set ⇒ 401.
9. **Change-password:** revokes all access tokens AND all `DeviceSession` rows (matches existing count-0 assertions).
10. **Password-reset-confirm:** same as (9).
11. **Register:** returns `refresh_token` + `device_id`; refresh works thereafter.
12. **Legacy tokens:** `Token.objects.get_or_create(user=user)`-style tokens still authenticate (578-suite regression is the guard).
13. **Throttle:** `refresh` scope 429s on burst.
14. **Missing/stale device:** wrong `device_id` or bad refresh credential ⇒ 401, no session side effects.

---

## 17. Concrete Example — Devices A and B

Setup: `POST /auth/login/` from device A and device B for the same landlord.

```
Device A: login {email, password, device_id: "A", device_name: "Chrome/Windows"}
  → access token "TOK_A", refresh credential "RFA", session_A(user, device"A")   [A1]
Device B: login {email, password, device_id: "B", device_name: "iPhone 15"}
  → access token "TOK_B", refresh credential "RFB", session_B(user, device"B")   [B1]
  → session_A and TOK_A remain valid (NOT invalidated)
```

Scenario walkthrough — **A logs out, B remains logged in:**
```
POST /auth/logout/  (Authorization: Token TOK_A)
  → TOK_A deleted, session_A revoked (refresh "RFA" dead)
  → TOK_B / session_B / RFB      still VALID
```

Scenario — **B refreshes (e.g. after 8 days, access expired):**
```
POST /auth/refresh/ {device_id: "B", refresh_token: "RFB"}
  → TOK_B revoked; new access "TOK_B2" + new refresh "RFB2" returned
  → A replay of "RFB" later  ⇒ session_B fully revoked (compromise detected)
```

Scenario — **A refreshes (impossible, already logged out):**
```
POST /auth/refresh/ {device_id: "A", refresh_token: "RFA"}
  → 401 session_revoked (A must log in again)
  → B completely unaffected
```

Scenario — **password changes (all devices):**
```
POST /auth/change-password/ (Authorization: Token TOK_B2)
  → backend deletes EVERY access token (TOK_B2, any other) and revokes
    every DeviceSession (session_A already dead, session_B revoked)
  → both A and B must log in with the new password; any outstanding
    refresh credentials are inert
  → device_C, device_D ... (future logins) unaffected going forward
```

Scenario — **password reset occurs (all devices):**
```
POST /auth/password-reset/ + /auth/password-reset/confirm/ {new_password}
  → all access tokens deleted, all DeviceSessions revoked (as above)
  → both devices require a fresh login with the new password
```

---

## 18. Summary / Recommendation

1. Keep DRF `Token` as the short-lived **access token** (`Authorization: Token <key>` unchanged).
2. Add one new `core.DeviceSession` model for per-device sessions with hashed, rotating refresh credentials.
3. Add `POST /api/v1/auth/refresh/`; stop `login` from rotating all tokens; scope `logout` to the requesting device; keep change-password/reset as global revocation.
4. One new migration, two settings, no new dependencies (JWT rejected as unecessarily complex), zero change to LANDLORD/TENANT/PLATFORM_ADMIN authorization, full backward compatibility with existing `Token <key>` clients.

**Requested approval to proceed to 11A implementation (backend-only) once this design is accepted.**

---

*Design document only. No application, backend, or frontend code modified; no packages installed; no migrations created; the Expo app was not created; payment idempotency (A2) was not implemented; `ALQUILER_PHASE_TRACKER.md` was not modified.*
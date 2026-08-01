# TASK 3 — Wallet Management

## Completed
Wallet connection, storage, and **signature-based ownership verification** with full
per-user isolation and audit events. Auth (JWT) added as the mechanism that makes
isolation enforceable.

## What was built

### Auth (required for isolation)
- `POST /api/auth/register` — create an account by email, returns a signed HS256 JWT
  (24h, `sub` + unique `jti`). Idempotent for existing emails.
- `backend/app/api/deps.py::get_current_user` — Bearer-token dependency; every wallet
  route resolves the user from the JWT and scopes all queries to it.
- `backend/app/core/security.py` — `create_access_token` / `decode_access_token`.

### Wallet API (all authenticated)
| Endpoint | Behavior |
|---|---|
| `POST /api/wallets/challenge` | Issues a single-use, 10-min expiring nonce for an address; returns the exact message to sign |
| `POST /api/wallets/connect` | Verifies the signature, creates/re-activates the wallet, marks the challenge used, writes `wallet.connected` audit event |
| `GET /api/wallets` | Lists the caller's wallets |
| `GET /api/wallets/{id}` | Fetches one of the caller's wallets (404 for others) |
| `POST /api/wallets/{id}/revoke` | Revokes a wallet; reconnecting re-activates the same row |

### Ownership verification (no keys ever leave the user's wallet)
1. Backend issues `nonce = secrets.token_urlsafe(32)` bound to `(user, address, chain)`.
2. The client signs the message `"keeperpilot.example wants you to sign in..."` in their
   wallet (MetaMask etc.).
3. Backend recovers the signer with `eth_account.Account.recover_message`
   (secp256k1 ecrecover, local — no RPC) and compares against the checksummed address.
4. Nonce is single-use (`used` flag) and expires after `CHALLENGE_TTL_MINUTES`.

### New model & migration
- `WalletChallenge` (`wallet_challenges`): `user_id`, `address`, `chain`, `message`,
  `nonce` (unique), `signature` (stored after success), `used`, `expires_at`,
  `created_at`.
- Migration `cab0eea8fd85` — upgrade/downgrade verified against SQLite.

## Files created/changed
- `backend/app/core/security.py` (new), `backend/app/api/deps.py` (new)
- `backend/app/api/routes/auth.py` (new), `backend/app/api/routes/wallets.py` (new)
- `backend/app/schemas/auth.py`, `backend/app/schemas/wallets.py` (new)
- `backend/app/services/wallets.py` (new — verification + lifecycle + audit)
- `database/models/wallet_challenge.py` (new) + relationship on `User`
- `database/migrations/versions/cab0eea8fd85_add_wallet_challenges...py` (new)
- `tests/test_auth.py`, `tests/test_wallets.py` (new)
- `pyproject.toml` — added `eth-account`, `eth-utils`, `pyjwt`, `email-validator`
- `backend/app/core/config.py`, `.env.example` — JWT + challenge TTL settings
- `database/models/wallet.py` — **fixed a pre-existing bug**: duplicated `user_id`
  column with a wrong type annotation (annotation-only change, no schema diff)

## Security properties (each backed by a test)
- **Keys never persisted** — schema has no key fields; test signs with a key and asserts
  the key hex appears in no table row.
- **No replay** — challenge `used` flag; second connect with the same nonce → 400.
- **Expiry** — `expires_at` check; expired nonce → 400.
- **Signature ≠ address** → 400; garbage signature → 400.
- **Challenge/address binding** — challenge is bound to the issued address/chain.
- **Cross-user isolation** — user B gets 404 on fetch/revoke of A's wallet, and cannot
  use A's challenge.
- **Auth enforced** — missing/garbage/tampered/expired/ghost-user tokens → 401.
- **Address validation** — malformed addresses rejected (400/422).

## Testing
- `pytest`: **32 passed** (4 auth + 11 token security + 4 wallet API security/lifecycle +
  existing 13 from Tasks 1–2).
- Coverage: **96%** on `backend/app` (wallet service 95%; uncovered lines are defensive
  decode/404 branches).
- Live smoke: booted uvicorn and ran the full flow over HTTP
  (register → challenge → sign → connect → list → revoke → unauth rejected) — PASS.
- `ruff check .`: **All checks passed**.
- Migrations: `upgrade head` / `downgrade` / `upgrade head` verified.

## Problems
1. **eth-account 0.13 removed `Account.to_checksum_address`** — moved to
   `eth_utils.to_checksum_address`; imports updated.
2. **Same-second JWTs were byte-identical** (deterministic HS256 over equal payloads) —
   added a unique `jti` claim.
3. **SQLite strips tzinfo from stored datetimes** — expiry comparison now normalizes
   naive datetimes to UTC.
4. **Local `.env` pointed at PostgreSQL** (not installed on this machine), so live
   requests 500'd — `.env` now defaults to SQLite for local dev; Postgres remains the
   prod URL via env override.
5. Raw `signature.hex()` from eth-account has no `0x` prefix — schema accepts 130–132
   chars and the service normalizes to `0x`-prefixed.

## Notes / honest limits
- Auth is **email + JWT only (no password)** — acceptable for the hackathon surface,
  documented as a must-upgrade before production (real identity, rate limiting, CSRF
  for cookie flows, nonce cleanup job).
- Challenge nonces accumulate in `wallet_challenges`; a periodic cleanup of
  expired/used rows is a follow-up.
- Signing is currently **manual via any EIP-191 wallet**; a frontend wallet-button flow
  lands with the dashboard task.

## Next recommendation
Proceed to **TASK 4 — User Preferences & Risk Policies**: preference CRUD, policy
validation (risk level, min yield delta, max gas), and wiring the per-user preference
into the decision loop.

---

# CODE AUDIT — TASK 3

**Status: PASS** ✅

## Security
- **Ownership = cryptographic proof, not possession**: private keys are never requested,
  stored, or logged. Verification uses local secp256k1 recovery (`eth_account`), no RPC.
- **Isolation enforced at the query layer**: every service function takes the
  authenticated `User` and scopes `WHERE user_id = ...`; cross-user fetches return 404
  (not 403) to avoid leaking wallet existence.
- **Replay/expiry protection**: single-use nonces with a TTL, enforced inside the service
  (not just the schema).
- **Address canonicalization**: all addresses stored EIP-55 checksummed; comparisons are
  checksum-safe.
- **Token hygiene**: HS256 with `sub`/`jti`/`exp`; invalid, tampered, expired, and
  ghost-user tokens all rejected with 401.
- **Input validation** at Pydantic (lengths, hex shape) plus service-level address checks.
- Audit events written on connect/revoke/register (append-only `audit_logs`).
- **Known limits (accepted)**: no password identity, no rate limiting on register/challenge,
  no nonce cleanup. All documented in `docs/TASK3.md`.

## Architecture
- Service layer (`services/wallets.py`) holds all security logic; routes are thin
  HTTP adapters — the same verification logic could be reused by a CLI or worker.
- Challenge model keeps the nonce/message/signature together, enabling future
  replay-audit and SIWE (EIP-4361) upgrade.
- Auth dependency (`get_current_user`) is reusable by every later protected route.
- Migration pattern matches Task 2 (UUID PKs, enum-by-name, FK `ondelete`).

## Dependencies
- `eth-account` + `eth-utils` (pure-Python, no heavy deps) for offline signature recovery.
- `pyjwt` and `email-validator` added explicitly (were transitive) — pinned in `pyproject.toml`.

## Configuration
- JWT secret default is a dev-only string with a `# noqa` + comment; production must set
  `JWT_SECRET` (documented in `.env.example`).
- `CHALLENGE_TTL_MINUTES` and `JWT_EXPIRES_MINUTES` configurable via env.

## Recommendations (non-blocking)
- Move to **SIWE (EIP-4361)** message format when the frontend wallet flow lands.
- Add **rate limiting** on `/auth/register` and `/wallets/challenge`.
- Add a **nonce cleanup job** (delete expired/used challenges older than N days).
- Add a **Postgres CI job** to verify migrations against the real dialect.
- Consider signing challenge rotation with a keyed HMAC so a DB read of `nonce` alone
  can't be replayed against a different deployment.

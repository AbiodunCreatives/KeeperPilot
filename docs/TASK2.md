# TASK 2 — Database Design

## Completed
Six PostgreSQL-backed ORM models matching the spec, async session management, an Alembic
migration pipeline (upgrade + downgrade verified), and a database test suite.

## Models created (`database/models/`)

| Model | Fields (spec + justified additions) |
|---|---|
| `User` | `id` (UUID), `email` (unique, indexed), `created_at` |
| `Wallet` | `id`, `user_id` (FK), `address` (42-char EVM), `chain`, `status` (active/revoked), `created_at`; unique `(user_id, address, chain)` |
| `UserPreferences` | `id`, `user_id` (FK, unique — one-to-one), `risk_level` (low/medium/high), `preferred_assets` (JSON list), `minimum_yield_difference` (pp), `maximum_gas_cost` (USD), `updated_at` |
| `Position` | `id`, `wallet_id` (FK), `protocol`, `asset`, `amount` (Numeric 38,18), `apy` (Numeric 12,4), `updated_at`; unique `(wallet_id, protocol, asset)` |
| `Execution` | `id`, `user_id` (FK), `action`, `status` (7-state lifecycle), `transaction_hash`, `gas_used` (USD), `amount`, `asset`, `reason`, `created_at`, `completed_at` |
| `AuditLog` | `id`, `event` (dotted convention), `description`, `user_id` (nullable FK), `execution_id` (nullable FK), `timestamp`; index `(user_id, timestamp)` |

Design decisions:
- **UUID primary keys** with client-side defaults — portable across Postgres/SQLite.
- **Enum storage by name** (verified empirically) so the generated CHECK constraints
  match on Postgres and SQLite alike. `StrEnum` types in Python.
- **`user_id`/`execution_id` added to AuditLog** and **`reason`/`amount`/`asset` to Execution**
  beyond the bare spec — required for the Task 9 audit dashboard and Task 5 decision explanations.
- Cascades: deleting a user removes owned wallets/preferences/positions/executions;
  audit logs use `SET NULL` on user/execution so the immutable log survives.

## Files created
- `database/models/`: `base.py`, `enums.py`, `user.py`, `wallet.py`, `preferences.py`,
  `position.py`, `execution.py`, `audit_log.py`, updated `__init__.py`
- `database/session.py` — `build_engine`, `build_session_factory`, module-level
  `engine`/`async_session_factory`, FastAPI `get_db` dependency
- `database/alembic.ini`, `database/migrations/env.py` (async), `script.py.mako`
- `database/migrations/versions/b48cbc369e9f_initial_schema...py` (initial migration)
- `tests/test_models.py`, `tests/test_migrations.py`, updated `tests/conftest.py`

## Dependencies
- Added `aiosqlite>=0.20` to dev extras (in-memory/test DB driver).

## Testing
- `pytest`: **11 passed** (7 model tests + 2 migration tests + 2 Task-1 smoke tests).
- Model tests cover: full hierarchy + relationships, enum defaults, unique constraints
  (email, wallet address+chain, position protocol+asset), same-address-different-chain
  allowed, and user-delete cascade.
- Migration tests run Alembic `upgrade head` → all 6 tables present, then `downgrade base`
  → only `alembic_version` remains.
- Manual lifecycle check: `upgrade head` / `current` / `downgrade base` against SQLite.
- Coverage: **95%** on database/backend/agent (uncovered lines are offline-mode branches in env.py).
- `ruff check .`: **All checks passed** (excluded generated `versions/*` from lint).
- uvicorn boot + `/api/health` still healthy.

## Problems
1. **Async lazy-load pitfall**: accessing relationships after commit raises
   `MissingGreenlet`; tests now use `selectinload` eager loading — application code
   must do the same (noted for service layer in later tasks).
2. Migration tests must run **synchronously** because env.py drives the async engine via
   `asyncio.run()`, which cannot nest inside pytest-asyncio's loop. Documented in the test module.
3. ruff flagged SQLAlchemy forward refs (`F821`) — resolved with the standard
   `TYPE_CHECKING` import pattern; SQLAlchemy resolves these through its registry at
   mapper-config time.

## Next recommendation
Proceed to **TASK 3 — Wallet Management**: connect/storage/verification endpoints with
ownership checks and isolation, plus API tests.

---

# CODE AUDIT — TASK 2

**Status: PASS** ✅

## Security
- **No secrets** in models/migrations; addresses only (42-char), keys are never stored by design.
- Foreign keys use `ondelete` rules matched to cascade behavior; audit log is append-only by
  convention (`user_id`/`execution_id` survive user deletion via `SET NULL`).
- Emails uniquely indexed — prevents duplicate accounts at the DB layer.
- Enum CHECK constraints prevent invalid status/risk values entering the DB.

## Architecture
- Models isolated in `database/models/`, session plumbing in `database/session.py`, schema
  lifecycle in Alembic — clean seams the service layer can consume without ORM leakage.
- Portability: `native_enum=False`, `Uuid` generic type, `Numeric` for money/token amounts —
  same DDL works on Postgres (prod) and SQLite (tests).
- Relationship direction is unidirectional where appropriate (audit → user), avoiding
  accidental traversal costs.

## Dependencies
- Only `aiosqlite` added (dev-only). No new runtime deps for Task 2.
- SQLAlchemy 2.0 typed-mapping pattern used consistently (`Mapped[...]` + `mapped_column`).

## Configuration
- Alembic URL resolved from app settings at runtime, with explicit override for tests.
- `path_separator = os` silences the legacy-splitting deprecation warning.

## Recommendations (non-blocking)
- Service layer must always use eager loading (`selectinload`) in async handlers.
- Add a Postgres-backed CI job to exercise migrations against the real dialect before launch.
- Consider a `CHECK (minimum_yield_difference >= 0)` app-level validation at the Pydantic layer (Task 4).
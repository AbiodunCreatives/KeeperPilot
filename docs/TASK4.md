# TASK 4 — User Preferences & Risk Policies

## Completed
Preference CRUD (per-user), input validation/normalization, and a **pure risk-policy
engine** (`evaluate_opportunity`) that gates every candidate opportunity the agent
considers. The engine is exposed both as a library (for Task 5's decision loop) and as
an HTTP endpoint (`POST /api/preferences/decide`).

## API
| Endpoint | Behavior |
|---|---|
| `GET /api/preferences` | Returns the caller's policy knobs; **defaults** (medium risk, empty assets, min 2pp, max $5 gas) if never customized — without persisting |
| `PUT /api/preferences` | Upsert; omitted fields keep their current value (partial update); writes `preferences.updated` audit event |
| `POST /api/preferences/decide` | Evaluates `{asset, current_apy, candidate_apy, gas_cost, candidate_protocol_risk?}` → allow/deny with per-rule reasons |

All three are authenticated and scoped to the JWT owner.

## The policy engine (`services/policies.py`)
Pure, no-I/O functions reused by both the API and the future decision loop.

| Rule | Logic |
|---|---|
| `preferred_assets` | Empty list = no restriction; otherwise asset (case-insensitive) must be in the list |
| `minimum_yield_difference` | `candidate_apy - current_apy >= threshold` (percentage points) |
| `maximum_gas_cost` | estimated execution cost in USD must not exceed the cap |
| `risk_apy_ceiling` | LOW → candidate APY ≤ 10%, MEDIUM → ≤ 30%, HIGH → no ceiling (higher APY ≈ higher risk) |
| `protocol_risk_tier` | optional; a protocol's risk tier must not exceed the user's tolerance |

Every rule returns a `PolicyCheck` so **rejections are explainable** (`reasons` list) —
this feeds Task 5 explanations and Task 9's audit dashboard.

## Validation & normalization
- `risk_level` must be `low|medium|high` (enum).
- `minimum_yield_difference` ∈ [0, 100] pp; `maximum_gas_cost` ∈ [0, 10000] USD.
- `preferred_assets`: ≤ 20 symbols, each ≤ 16 chars of `[A-Za-z0-9-]`; **normalized to
  uppercase, de-duplicated, sorted** (e.g. `[" usdc ", "USDC", "usdt"]` → `["USDC", "USDT"]`).
- All violations rejected with 422 before touching the DB.

## Files created/changed
- `backend/app/services/policies.py` (new) — constants + `evaluate_opportunity` + `PolicyDecision`/`PolicyCheck`
- `backend/app/services/preferences.py` (new) — `get_preferences` (defaults), `upsert_preferences`, audit
- `backend/app/schemas/preferences.py` (new)
- `backend/app/api/routes/preferences.py` (new); `api/router.py` wired
- `tests/test_preferences.py` (new) — 18 tests

## Testing
- `pytest`: **50 passed** (18 new + 32 from Tasks 1–3).
- Coverage: **97%** on `backend/app` (schemas/preferences 97%).
- Policy engine unit tests cover every rule branch: allow, insufficient delta,
  expensive gas, disallowed asset, empty-assets = unrestricted, LOW ceiling (10%),
  HIGH uncapped, protocol-tier mismatch, and per-user isolation.
- HTTP tests cover defaults, create/partial-update, normalization, 422 validation,
  unauthenticated 401, per-user isolation, and `/decide` honoring saved preferences.
- Live smoke: register → defaults → update → decide denies DAI → decide allows USDC — PASS.
- `ruff check .`: **All checks passed**.

## Problems
1. **Column defaults are not populated until flush** — a freshly created
   `UserPreferences` had `risk_level = None`, crashing the audit-log description.
   Fixed with an explicit `flush()` after insert (defaults then apply).
2. Asset normalization on the Pydantic layer vs DB layer: normalization lives in the
   schema (`field_validator`) so the service always receives clean data; documented so
   future writers don't re-implement it.

## Next recommendation
Proceed to **TASK 5 — AI Decision Engine**: scan tracked positions, fetch candidate
opportunities (KeeperHub mock), run them through `evaluate_opportunity`, and emit a
human-readable recommendation with the policy checks that passed/failed.

---

# CODE AUDIT — TASK 4

**Status: PASS** ✅

## Security
- **No new attack surface on data**: preferences are owned 1:1 by `user_id`
  (DB unique constraint) and every route resolves the user from the JWT — cross-user
  reads/updates are impossible.
- **Input hardening**: enum + numeric bounds + asset-symbol allowlist at the Pydantic
  layer; rejected with 422 before any DB write.
- **Audit trail**: every preference change writes a `preferences.updated` event with the
  resulting knob values.
- **Policy failures are explicit**: the engine never fails open — missing data means a
  rule is skipped or the decision returns the failing checks; an empty `preferred_assets`
  (default) deliberately means "no asset restriction," which is documented and tested.

## Architecture
- Policy logic is **pure and dependency-free** (`services/policies.py`) — the decision
  loop, HTTP layer, and audit dashboard all share one implementation instead of
  duplicating risk math.
- Service layer returns ORM objects; routes adapt to Pydantic responses — consistent
  with Task 3.
- Defaults are computed (transient object), not persisted, so "default policy" and
  "saved policy" are indistinguishable to callers.

## Dependencies
- No new dependencies for Task 4.

## Configuration
- Risk ceilings are constants in `policies.py` — configurable later via settings if
  product wants to tune them without code changes.

## Recommendations (non-blocking)
- Consider promoting risk ceilings to `Settings` (env-tunable) before launch.
- Add a `protocol_risk_tier` column to `Position`/`protocols` catalog so the tier check
  fires with real data in Task 5.
- Consider a `preferences.decide` audit event when the agent actually acts (Task 5), so
  the audit log connects policy → decision → execution.

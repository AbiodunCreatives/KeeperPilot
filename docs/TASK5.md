# TASK 5 — AI Decision Engine

## Completed
The decision loop core: scan a user's tracked positions, pull candidate yield
opportunities (deterministic mock market for now), evaluate every candidate through
the Task 4 risk-policy engine, rank them, and emit an explainable, human-readable
recommendation. Exposed as `GET /api/decisions/scan`.

## Architecture
```
GET /api/decisions/scan
  -> services/decisions.py: analyze()
       -> load ACTIVE wallets + positions (eager-loaded)
       -> preferences.get_preferences(user)
       -> keeperhub client .get_opportunities(asset, chain)   [mock today]
       -> policies.evaluate_opportunity(...) per candidate    [Task 4 engine]
       -> rank (allowed first, then APY delta desc)
       -> agent/reasoning/summary.py: summarize_scan(...)      [plain-language briefing]
       -> audit event decision.scanned
```

### New modules
| Module | Role |
|---|---|
| `agent/keeperhub/mock_data.py` | Deterministic market dataset: 2 chains × 4 assets × 3–5 protocols (APY, risk tier, estimated gas) |
| `agent/keeperhub/client.py` | `KeeperHubClient` protocol, `MockKeeperHubClient`, `KeeperHubMCPClient` stub (raises until Task 7), `get_keeperhub_client(settings)` factory |
| `agent/reasoning/summary.py` | Template-based plain-language briefing (LLM narrative is a later enhancement — no key needed) |
| `backend/app/services/decisions.py` | Scan orchestration: `scan_user_opportunities`, `analyze` |
| `backend/app/schemas/decisions.py` | `ScanReport`, `RecommendationResponse`, `OpportunityResponse` |
| `backend/app/api/routes/decisions.py` | `GET /api/decisions/scan` |

### Decisions made
- **Same-protocol candidates are excluded** (moving USDC from Aave to Aave is a no-op).
- **Ranking**: allowed candidates first (by APY delta desc), then blocked — so the
  "best move" is always the top item, and blocked candidates still explain *why*.
- **Blocked candidates are kept in the report** with their failing policy checks —
  the user (and later the audit dashboard) sees what was considered and rejected.
- **Stateless scan**: recommendations are recomputed on demand; the audit log records
  each scan with counts (persisted decision history is a Task 6/9 concern).
- **Summary is template-based** and always present, so the scan is understandable
  without an OpenAI key; swapping in an LLM narrative later is a drop-in change.

## API
```
GET /api/decisions/scan   (Bearer token)
-> ScanReport { scanned_at, recommendation_count, allowed_count, blocked_count,
                summary, recommendations: [{ wallet_address, chain, current_protocol,
                asset, amount, current_apy, opportunity {protocol, apy, risk_level,
                estimated_gas}, delta_apy, allowed, reasons, checks }] }
```
Example output (default policy, USDC@aave-v3 at 4.0%):
```
recommendations[0] = allowed, opportunity.protocol = "fluid", delta_apy = +4.40
summary = "Best move: move 10000.00 USDC from aave-v3 to fluid for +4.40pp APY. ..."
```

## Files created/changed
- `agent/keeperhub/mock_data.py`, `agent/keeperhub/client.py` (new)
- `agent/reasoning/summary.py` (new)
- `backend/app/services/decisions.py` (new)
- `backend/app/schemas/decisions.py` (new)
- `backend/app/api/routes/decisions.py` (new), `api/router.py` wired
- `tests/test_decisions.py` (new) — 8 tests

## Testing
- `pytest`: **58 passed** (8 new + 50 from Tasks 1–4).
- Coverage: **96%** on `backend/app` + `agent`; the new decision modules are fully
  covered (uncovered lines are the real-MCP-client stub paths).
- Tests cover: ranked output shape, same-protocol exclusion, allowed/blocked counts,
  per-rule checks on every recommendation, strict-policy blocking (gas + delta +
  APY ceiling + protocol tier), per-user isolation, empty scan, audit event, and mock
  client determinism + unknown-chain empty.
- Live smoke (real HTTP): register → signed wallet connect → empty scan → seeded
  position → scan returns 4 candidates / 2 allowed, best move aave-v3 → fluid +4.40pp,
  summary reads correctly — PASS.
- `ruff check .`: **All checks passed**.

## Problems
1. Test-writer bug during development: JSON user ids are strings, but ORM columns need
   `uuid.UUID` — converted in the test helper (real API flow already passes `user.id`).
2. Two early test assertions were wrong, not the code: the "empty scan" test passed the
   whole register response as the token (→ 401), and the low-risk ceiling is not always
   `reasons[0]` (gas fails first for the farm) — fixed to inspect the per-rule checks.

## Honest limits
- Market data is **deterministic mock** (no live APY). Real rates arrive with KeeperHub
  wiring in Task 7.
- No LLM narrative yet; summary is template text.
- Scan is pull-based (on request); a scheduled sweep + Telegram push is Task 6.

## Next recommendation
Proceed to **TASK 6 — Autonomous Execution & Safety** (or the planned KeeperHub wrapper):
persist decisions, auto-execute allowed moves through the KeeperHub client, track
`Execution` lifecycle, and add confirmation/guardrails.

---

# CODE AUDIT — TASK 5

**Status: PASS** ✅

## Security
- **User-scoped end to end**: the route resolves the user from the JWT; the scan queries
  only `user_id = current_user.id` and only `ACTIVE` wallets. No cross-user data path.
- **Read-only**: the scan performs no writes to market state; the only write is an audit
  event with counts (no position/asset data in the log beyond generic description).
- **Deterministic data source**: mock client never touches the network — no data
  exfiltration or injection surface in dev/test.
- **No secrets**: mock requires no key; the real-client stub refuses to construct without
  `KEEPERHUB_API_KEY` and raises `NotImplementedError` on use until wired (no silent
  fallback to unsafe behavior).

## Architecture
- **Client behind a protocol** (`KeeperHubClient`): the engine depends on an interface,
  so swapping mock → real in Task 7 touches one factory line, not the engine.
- **Policy engine reused** (not duplicated): `evaluate_opportunity` from Task 4 is the
  single source of truth for allow/deny.
- **Domain logic in `agent/`**, orchestration in `backend/app/services/` — consistent
  with the existing layout and the `services/__init__` docstring.
- Ranking and filtering are pure (sort keys, same-protocol exclusion) and unit-testable.

## Dependencies
- No new dependencies.

## Configuration
- Mock vs real driven by existing `KEEPERHUB_MOCK` setting; no new config knobs needed.

## Recommendations (non-blocking)
- Persist scan results (a `decisions`/`recommendations` table) before Task 9 so the audit
  dashboard can show history, not just a live recompute.
- Add a stale-position flag when a wallet/position hasn't refreshed in N hours.
- Consider a soft cap on candidate explosion (top-K per asset) once live market data is
  wired.

# TASK 7 — KeeperHub Real Integration

## Completed
The full real-mode KeeperHub wiring. `KEEPERHUB_MOCK=false` now routes the app through
a production MCP client that speaks the KeeperHub Streamable-HTTP protocol with the
real API key, discovers opportunities from DefiLlama yields, submits migrations as
protocol actions, and polls receipts to completion. A local fake KeeperHub MCP server
replicates the real tool surface so the whole transport is exercised in CI without
credentials.

## What changed
- **`agent/keeperhub/mcp_client.py`** — `KeeperHubMCPClient`, the real client:
  - Fresh authenticated MCP session per tool call (Bearer key), MCP SDK 2.x
    (`mcp` >= 2.0 with its vendored `httpx2`; falls back to plain `httpx` on older SDKs).
  - `_call_tool` with exponential backoff + jitter over retryable transport failures;
    typed `KeeperHubError` subclasses (auth/not-found/execution) are never retried.
  - The SDK masks HTTP statuses as generic `MCPError(-32603)`; an **async** response
    hook on the httpx client records the real HTTP status for correct 401/404
    classification.
  - `get_opportunities(asset, chain)` → DefiLlama yields (KeeperHub is execution-only).
  - `submit(action)` → preflights `list_integrations` for a `web3` wallet, then
    `execute_protocol_action` for `<source>/withdraw` and `<target>/supply` legs,
    returning a receipt whose reference encodes both execution ids.
  - `get_receipt(reference)` → bounded polling of `get_direct_execution_status` for
    each leg; terminal-status mapping with a poll budget that degrades to `submitted`.
- **`agent/keeperhub/errors.py`** — `KeeperHubError` hierarchy
  (`AuthenticationError`, `NotFoundError`, `UnavailableError`, `ExecutionError`) +
  `MarketDataUnavailableError`.
- **`agent/market/defillama.py`** (+ `__init__.py`) — DefiLlama yields source:
  chain aliases (Sepolia/Base-Sepolia → mainnet), protocol aliases
  (`morpho-blue→morpho`, `aave→aave-v3`), risk heuristic, cap on pools, gas default.
- **`agent/keeperhub/client.py`** — stub replaced with a factory
  `get_keeperhub_client(settings)` → `MockKeeperHubClient` (mock mode) or
  `KeeperHubMCPClient` (real mode, lazy import to avoid a cycle).
- **`backend/app/core/config.py`** + `.env.example` — new knobs: request timeout,
  retry count/backoff, poll interval/max attempts, market pool cap, default gas.
- **`tests/fakes/keeperhub_mcp.py`** — a real MCP server (same SDK, same transport)
  exposing the KeeperHub tool surface: `list_action_schemas`, `list_integrations`,
  `get_wallet_integration`, `search_protocol_actions`, `execute_protocol_action`,
  `get_direct_execution_status`, `tools_documentation`. Scriptable wallet presence,
  completion latency, token, and a first-request fault for retry tests.
- **`tests/test_keeperhub_mcp.py`** (12 tests) and **`tests/test_market_defillama.py`**
  (7 tests) — contract suite.
- `pyproject.toml`: added `S105/S106/S107` to the tests per-file-ignore (test token
  fixtures).

## Live contract discovery (read-only smoke, real endpoint)
Approved read-only smoke against `https://app.keeperhub.com/mcp` with the key from the
local `.env`. It revealed the documented surface was **out of date**, and the client +
fake + tests were aligned to the *real* schemas:

| Tool | Documented/assumed | Real (verified) |
|---|---|---|
| `list_integrations` | — | returns `[{id, name, type: "web3", address}]`; the org wallet is `yqvp8jdoxvf0fifwz7mh4` |
| `get_wallet_integration` | no args | **requires `integrationId`** (404 if unknown) |
| `execute_protocol_action` | flat kwargs | `{actionType, params}`; supply needs `network, asset, amount, onBehalfOf`; withdraw needs `network, asset, amount, to` |
| `get_direct_execution_status` | `executionId` | **`execution_id`** (snake_case) |
| `search_protocol_actions` | `chain` | `query`/`protocol` |
| `list_action_schemas` | `chain` | `category`/`includeChains` |

Also confirmed: 35 tools on the live server, `execute_*` tools return execution ids,
and the SDK wraps plain-string tool results as `structured_content={"result": "<json>"}`
(handled in `_parse_payload`). The HTTP-status hook was needed because the SDK masks
statuses — this surfaced as a `'NoneType' object can't be awaited` bug (response hooks
must be **async** in httpx2), which was fixed and verified against a live POST.

## Testing
- `pytest`: **87 passed** (19 new + 68 from Tasks 1–6). All green.
- Coverage: **94%** overall; `mcp_client.py` 89% (uncovered = defensive branches:
  legacy-httpx import, exception unwrapping edge cases).
- Contract tests exercise the exact production transport (Streamable HTTP + MCP
  SDK + Bearer auth) against the local fake server: submit legs + wallet preflight,
  poll-until-completed, bounded polls, missing wallet, unknown action type, wrong key
  → auth error, transient 500 → retry + recover, unreachable server → unavailable,
  opportunities delegation, factory mock/real selection.
- Live read-only smoke (real key): `list_integrations`, `get_wallet_integration`,
  `tools_documentation`, `list_action_schemas`, `search_protocol_actions`,
  DefiLlama yields — all PASS.
- `ruff check .`: **All checks passed**.

## Honest limits
- No live **write** was executed (no `execute_protocol_action` submitted on-chain).
  The `params` mapping is validated against the real `list_action_schemas` output and
  `search_protocol_actions`, but the exact execution-id response shape is inferred from
  the tool description; first real submission may need a one-line tweak in
  `_execute_leg`'s field parsing.
- DefiLlama pools are not price-adjusted yet; risk uses a category heuristic.
- The org has exactly one `web3` integration; `_get_wallet_integration` picks the first
  of that type.

## Next recommendation
TASK 8 — approval/scheduling (auto-approve flag, scheduled sweep, Telegram
notifications), or first a supervised live test of a single `execute_protocol_action`
on Sepolia when the user opts in.

---

# CODE AUDIT — TASK 7

**Status: PASS** ✅

## Security
- **Credentials**: API key only in `.env` (gitignored, verified not tracked); never
  logged — retry logs exclude headers/payload. No private keys pass through this layer
  (KeeperHub holds wallet custody).
- **Fault isolation**: authentication (401) and not-found (404) are classified from the
  real HTTP status via a response hook and raised as typed errors that are **never
  retried** — a bad key fails fast instead of hammering the endpoint.
- **Timeout/retry discipline**: bounded timeouts (30s), bounded retries (3) with
  exponential backoff + jitter — no unbounded loops; polling is capped at a configurable
  attempt budget and degrades to `submitted`, never blocking forever.
- **No injection**: leg params are built from a frozen dataclass; `actionType` is
  `f"{protocol}/withdraw"`/`supply` from allow-listed values in the service layer.

## Architecture
- Client contract (`submit`/`get_receipt`/`get_opportunities`) unchanged from Task 6;
  the service never sees MCP details — swapping mock↔real is one factory call.
- Stateless per-call sessions keep the client simple and robust to dropped sessions.
- Parsing is defensive: `_parse_payload`/`_parse_field` tolerate both `structured_content`
  and JSON text and the SDK's `{"result": "<json>"}` wrapper — resilient to transport
  shape drift.

## Dependencies
- New: `mcp` >= 2.0 (with vendored `httpx2`); optional plain `httpx` fallback. No other
  additions. (Audit note: the dependency change is required by this task and was already
  in the environment.)

## Configuration
- All behavior knobs are settings-driven with sane defaults; `.env.example` documents
  each. No knobs hardcode secrets.

## Recommendations (non-blocking)
- On the first approved live write, verify the `execute_protocol_action` return shape
  and the direct-execution status vocabulary; adjust `_parse_field` keys if needed.
- Add a **manual runbook** entry for rotating the KeeperHub API key (org-level token).
- Consider caching `list_integrations` (org wallet id) per session to shave one round
  trip per submission.
- When Sepolia goes live, add a canary test that submits the smallest allowed supply
  under a test wallet and asserts a real tx hash + explorer link.

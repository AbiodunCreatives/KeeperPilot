"""Real KeeperHub client over the Model Context Protocol.

Connects to the KeeperHub MCP server (``https://app.keeperhub.com/mcp``) with the
official MCP Python SDK, authenticating with a Bearer API key, and maps the
KeeperPilot client contract onto KeeperHub's tools:

- ``get_opportunities`` -> DefiLlama yields API. KeeperHub is execution-only;
  market data comes from a dedicated source (see ``agent.market.defillama``).
- ``submit`` -> preflights the wallet integration, then ``execute_protocol_action``
  for each leg of the migration (``<source>/withdraw`` then ``<target>/supply``).
  Each leg returns an execution id; the receipt reference encodes all ids.
- ``get_receipt`` -> bounded polling of ``get_direct_execution_status`` for every
  encoded execution id.

Transient transport failures are retried with exponential backoff + jitter.
Deterministic tool errors (e.g. missing wallet, unknown action, 401) surface as
typed ``KeeperHubError`` subclasses and are never retried.

Parameter shapes for the KeeperHub tools are the documented minimal mapping;
adjusting them to the live server's exact schema is a one-function change
(``_leg_params``).
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import StreamableHTTPError, streamable_http_client
from mcp.shared.exceptions import MCPError
from mcp.types import CallToolResult, TextContent

try:  # mcp >= 2.x ships a vendored httpx; older versions used the plain httpx
    from httpx2 import AsyncClient as _AsyncClient
    from httpx2 import HTTPError as _HTTPError
except ImportError:  # pragma: no cover - only hit with an older mcp SDK
    from httpx import AsyncClient as _AsyncClient
    from httpx import HTTPError as _HTTPError

from agent.keeperhub.client import ExecutionAction, ExecutionReceipt
from agent.keeperhub.errors import (
    KeeperHubAuthenticationError,
    KeeperHubError,
    KeeperHubExecutionError,
    KeeperHubNotFoundError,
    KeeperHubUnavailableError,
)
from agent.market.defillama import fetch_yields
from backend.app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    _HTTPError,
    OSError,
    TimeoutError,
    StreamableHTTPError,
)

_TERMINAL_STATUSES = frozenset({"completed", "succeeded", "success", "confirmed"})
_FAILED_STATUSES = frozenset({"failed", "error", "reverted", "cancelled", "expired"})


def _content_text(result: CallToolResult) -> str:
    return "".join(
        part.text for part in result.content if isinstance(part, TextContent)
    )


def _parse_payload(result: CallToolResult) -> Any | None:
    """Best-effort dict-or-list payload from structured or JSON text content."""
    structured = result.structured_content
    if isinstance(structured, list):
        return structured
    if isinstance(structured, dict):
        inner = structured.get("result")
        if isinstance(inner, str):
            text = inner
        else:
            return structured
    else:
        text = _content_text(result).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _parse_field(result: CallToolResult, *keys: str) -> Any | None:
    """Extract a field from structured content, falling back to JSON text."""
    payload = _parse_payload(result)
    if isinstance(payload, dict):
        for key in keys:
            if key in payload:
                return payload[key]
    return None


def _status_of(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None)


def _first_inner(exc: BaseException) -> BaseException:
    """Unwrap task-group exception bundles down to the first real cause."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return exc


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, _RETRYABLE_EXCEPTIONS) or isinstance(exc, MCPError)


def _classify_transport_error(exc: BaseException) -> str | None:
    """Map a transport/HTTP/MCP error to ``auth``/``notfound``/``None``."""
    status = _status_of(exc)
    if status == 401:
        return "auth"
    if status == 404:
        return "notfound"
    message = str(exc).lower()
    code = getattr(exc, "code", None)
    if (
        code == 401
        or "401" in message
        or "unauthorized" in message
        or "invalid or missing api key" in message
    ):
        return "auth"
    if code == 404 or "404" in message or "not found" in message:
        return "notfound"
    return None


def _classify_tool_error(text: str) -> KeeperHubError:
    lowered = text.lower()
    if (
        "401" in lowered
        or "invalid or missing api key" in lowered
        or "unauthorized" in lowered
    ):
        return KeeperHubAuthenticationError(text.strip())
    if "404" in lowered or "not found" in lowered:
        return KeeperHubNotFoundError(text.strip())
    return KeeperHubExecutionError(text.strip())


class KeeperHubMCPClient:
    """Production KeeperHub client speaking the MCP protocol.

    A fresh MCP session is opened per tool call (stateless usage), which keeps
    the client simple and robust to dropped sessions.
    """

    def __init__(
        self,
        api_key: str,
        mcp_url: str,
        *,
        settings: Settings | None = None,
        http_client: _AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise RuntimeError(
                "KEEPERHUB_MOCK is false but KEEPERHUB_API_KEY is not set"
            )
        self.api_key = api_key
        self.mcp_url = mcp_url
        self._settings = settings or get_settings()
        self._http_client = http_client
        self._owns_http_client = http_client is None
        # Latest HTTP status seen (the SDK masks HTTP statuses as MCPErrors,
        # so a response hook records the real status for classification).
        self._last_http_status: int | None = None

    # -- settings shortcuts --------------------------------------------------
    @property
    def _request_timeout(self) -> float:
        return self._settings.keeperhub_request_timeout

    @property
    def _max_retries(self) -> int:
        return self._settings.keeperhub_max_retries

    @property
    def _retry_backoff(self) -> float:
        return self._settings.keeperhub_retry_backoff

    @property
    def _poll_interval(self) -> float:
        return self._settings.keeperhub_poll_interval

    @property
    def _poll_max_attempts(self) -> int:
        return self._settings.keeperhub_poll_max_attempts

    @property
    def _max_pools(self) -> int:
        return self._settings.keeperhub_market_max_pools

    @property
    def _default_gas(self) -> float:
        return self._settings.keeperhub_default_gas_usd

    # -- transport -----------------------------------------------------------
    async def _record_response(self, response: Any) -> None:
        self._last_http_status = getattr(response, "status_code", None)

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[ClientSession]:
        """Open an authenticated MCP session for a single tool call."""
        client = self._http_client or _AsyncClient(
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self._request_timeout,
        )
        if self._record_response not in client.event_hooks.get("response", []):
            client.event_hooks.setdefault("response", []).append(
                self._record_response
            )
        try:
            async with streamable_http_client(
                self.mcp_url, http_client=client
            ) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    await session.initialize()
                    yield session
        finally:
            if self._owns_http_client:
                await client.aclose()

    async def _call_tool_once(
        self, name: str, arguments: dict[str, Any]
    ) -> CallToolResult:
        self._last_http_status = None
        async with self._session() as session:
            result = await session.call_tool(
                name,
                arguments,
                read_timeout_seconds=self._request_timeout,
            )
        if result.is_error:
            raise _classify_tool_error(_content_text(result))
        return result

    def _backoff(self, attempt: int) -> float:
        base = self._retry_backoff * (2**attempt)
        return base * (0.5 + random.random() * 0.5)  # noqa: S311 - jitter, not crypto

    async def _call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> CallToolResult:
        last: BaseException | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return await self._call_tool_once(name, arguments)
            except KeeperHubError:
                raise
            except BaseException as exc:
                inner = _first_inner(exc)
                kind = _classify_transport_error(inner)
                if kind is None and self._last_http_status == 401:
                    kind = "auth"
                elif kind is None and self._last_http_status == 404:
                    kind = "notfound"
                if kind == "auth":
                    raise KeeperHubAuthenticationError(
                        f"KeeperHub rejected the API key (401) on {name}"
                    ) from exc
                if kind == "notfound":
                    raise KeeperHubNotFoundError(
                        f"KeeperHub resource not found (404) on {name}"
                    ) from exc
                if not _is_retryable(inner):
                    raise
                last = exc
                if attempt < self._max_retries:
                    delay = self._backoff(attempt)
                    logger.warning(
                        "KeeperHub %s call failed (attempt %s/%s): %s; "
                        "retrying in %.2fs",
                        name,
                        attempt + 1,
                        self._max_retries + 1,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
        raise KeeperHubUnavailableError(
            f"KeeperHub {name} failed after {self._max_retries + 1} attempts: {last}"
        ) from last

    # -- KeeperPilot contract -------------------------------------------------
    async def get_opportunities(
        self, asset: str, chain: str
    ) -> list[Any]:
        """Real APY opportunities from DefiLlama (KeeperHub is execution-only)."""
        return await fetch_yields(
            asset,
            chain,
            max_pools=self._max_pools,
            default_gas=self._default_gas,
        )

    async def _get_wallet_integration(self) -> str:
        """Ensure an org wallet is configured; returns its integration id."""
        result = await self._call_tool("list_integrations", {})
        payload = _parse_payload(result)
        items = (
            payload
            if isinstance(payload, list)
            else payload.get("integrations") if isinstance(payload, dict) else None
        )
        wallet_ids = [
            str(item["id"])
            for item in items or []
            if isinstance(item, dict) and item.get("type") == "web3" and item.get("id")
        ]
        if not wallet_ids:
            raise KeeperHubExecutionError(
                "No KeeperHub wallet integration configured for this organization"
            )
        return wallet_ids[0]

    def _leg_params(self, action: ExecutionAction, action_type: str) -> dict[str, Any]:
        """Map an execution leg onto ``execute_protocol_action`` arguments.

        The live server expects ``{"actionType": ..., "params": {...}}``.
        Supply legs address the funds ``onBehalfOf`` the wallet; withdraw legs
        route them ``to`` the wallet.
        """
        params: dict[str, Any] = {
            "network": action.chain,
            "asset": action.asset,
            "amount": str(action.amount),
        }
        if action_type.endswith("/supply"):
            params["onBehalfOf"] = action.wallet_address
        elif action_type.endswith("/withdraw"):
            params["to"] = action.wallet_address
        return {"actionType": action_type, "params": params}

    async def _execute_leg(
        self, action: ExecutionAction, action_type: str
    ) -> str:
        result = await self._call_tool(
            "execute_protocol_action", self._leg_params(action, action_type)
        )
        execution_id = _parse_field(result, "executionId", "execution_id")
        if not execution_id:
            raise KeeperHubExecutionError(
                f"KeeperHub did not return an execution id for {action_type}"
            )
        return str(execution_id)

    async def submit(self, action: ExecutionAction) -> ExecutionReceipt:
        """Submit a full migration through KeeperHub.

        Preflights the wallet integration, then withdraws from the source
        protocol and supplies to the target protocol. The receipt reference
        encodes both execution ids for later polling.
        """
        await self._get_wallet_integration()
        legs = [
            f"{action.source_protocol}/withdraw",
            f"{action.target_protocol}/supply",
        ]
        execution_ids = [await self._execute_leg(action, leg) for leg in legs]
        reference = json.dumps({"executions": execution_ids})
        return ExecutionReceipt(tx_hash=reference, status="submitted")

    def _decode_reference(self, reference: str) -> list[str]:
        try:
            data = json.loads(reference)
            ids = data.get("executions")
            if isinstance(ids, list) and ids:
                return [str(item) for item in ids]
        except (json.JSONDecodeError, AttributeError):
            pass
        return [reference]

    @staticmethod
    def _map_status(raw: str) -> str:
        lowered = raw.strip().lower()
        if lowered in _TERMINAL_STATUSES:
            return "completed"
        if lowered in _FAILED_STATUSES:
            return "failed"
        return "submitted"

    async def _poll_execution(self, execution_id: str) -> str:
        result = await self._call_tool(
            "get_direct_execution_status", {"execution_id": execution_id}
        )
        raw = _parse_field(result, "status", "state")
        if not raw:
            raw = _content_text(result)
        return self._map_status(str(raw))

    async def get_receipt(self, reference: str) -> ExecutionReceipt:
        """Poll every leg until terminal, or the bounded poll budget runs out."""
        execution_ids = self._decode_reference(reference)
        for attempt in range(self._poll_max_attempts):
            statuses = [await self._poll_execution(eid) for eid in execution_ids]
            if all(status == "completed" for status in statuses):
                return ExecutionReceipt(tx_hash=reference, status="completed")
            if any(status == "failed" for status in statuses):
                return ExecutionReceipt(tx_hash=reference, status="failed")
            if attempt < self._poll_max_attempts - 1:
                await asyncio.sleep(self._poll_interval)
        return ExecutionReceipt(tx_hash=reference, status="submitted")

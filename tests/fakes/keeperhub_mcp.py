"""Local fake KeeperHub MCP server for contract-testing the real MCP client.

Serves KeeperHub's documented tool surface over Streamable HTTP using the MCP
SDK's ``MCPServer``, so tests exercise the exact transport the production
client uses (``tools/list`` + ``tools/call`` over JSON-RPC with a Bearer header)
without needing KeeperHub credentials.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
from typing import Any

import uvicorn
from mcp.server.mcpserver import MCPServer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

SUPPORTED_ACTIONS = frozenset(
    {
        "aave-v3/supply",
        "aave-v3/withdraw",
        "fluid/supply",
        "fluid/withdraw",
        "morpho/supply",
        "morpho/withdraw",
        "compound/supply",
        "compound/withdraw",
        "yearn/supply",
        "yearn/withdraw",
    }
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class FakeKeeperHubMCP:
    """Stateful, scriptable stand-in for the KeeperHub MCP server."""

    def __init__(
        self,
        *,
        wallet_configured: bool = True,
        completion_after_polls: int = 2,
        expected_token: str = "kh_test_key",
        fail_first_http_status: int | None = None,
    ) -> None:
        self.wallet_configured = wallet_configured
        self.completion_after_polls = completion_after_polls
        self.expected_token = expected_token
        self.fail_first_http_status = fail_first_http_status

        self.executions: dict[str, dict[str, Any]] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._http_requests: list[Request] = []
        self._next_execution = 1
        self._port = 0
        self._thread: threading.Thread | None = None

    # -- server lifecycle -----------------------------------------------------
    def _build_app(self):
        server = MCPServer("fake-keeperhub", version="1.0.0", log_level="WARNING")

        @server.tool()
        async def list_action_schemas(
            category: str | None = None,
            includeChains: bool = True,
        ) -> str:
            self.calls.append(
                ("list_action_schemas", {"category": category, "includeChains": includeChains})
            )
            return json.dumps(
                {"actions": sorted(SUPPORTED_ACTIONS)}
            )

        @server.tool()
        async def list_integrations() -> str:
            self.calls.append(("list_integrations", {}))
            if not self.wallet_configured:
                return json.dumps([])
            return json.dumps(
                [
                    {
                        "id": "wlt_integration_1",
                        "name": "0x0000000000000000000000000000000000000001",
                        "type": "web3",
                        "address": "0x0000000000000000000000000000000000000001",
                    }
                ]
            )

        @server.tool()
        async def get_wallet_integration(integrationId: str) -> str:
            self.calls.append(("get_wallet_integration", {"integrationId": integrationId}))
            if integrationId != "wlt_integration_1" or not self.wallet_configured:
                raise RuntimeError("API call failed: 404 Not Found - Integration not found")
            return json.dumps(
                {
                    "id": "wlt_integration_1",
                    "address": "0x0000000000000000000000000000000000000001",
                }
            )

        @server.tool()
        async def search_protocol_actions(
            query: str | None = None,
            protocol: str | None = None,
        ) -> str:
            self.calls.append(("search_protocol_actions", {"query": query, "protocol": protocol}))
            return json.dumps(
                {"count": len(SUPPORTED_ACTIONS), "actions": sorted(SUPPORTED_ACTIONS)}
            )

        @server.tool()
        async def execute_protocol_action(actionType: str, params: dict) -> str:
            arguments = {"actionType": actionType, "params": params}
            self.calls.append(("execute_protocol_action", arguments))
            if not self.wallet_configured:
                raise RuntimeError("Error: no wallet integration configured (400)")
            if actionType not in SUPPORTED_ACTIONS:
                raise RuntimeError(f"Error: unknown action type {actionType} (400)")
            execution_id = f"exe_{self._next_execution}"
            self._next_execution += 1
            self.executions[execution_id] = {
                "status": "submitted",
                "polls": 0,
                "tx_hash": None,
                "leg": actionType,
            }
            return json.dumps({"executionId": execution_id, "status": "submitted"})

        @server.tool()
        async def get_direct_execution_status(execution_id: str) -> str:
            self.calls.append(
                ("get_direct_execution_status", {"execution_id": execution_id})
            )
            record = self.executions.get(execution_id)
            if record is None:
                raise RuntimeError(f"Error: execution {execution_id} not found (404)")
            record["polls"] += 1
            if record["polls"] >= self.completion_after_polls:
                record["status"] = "completed"
                record["tx_hash"] = "0x" + "12" * 32
            return json.dumps(
                {
                    "executionId": execution_id,
                    "status": record["status"],
                    "transactionHash": record["tx_hash"],
                }
            )

        @server.tool()
        async def tools_documentation(tool: str | None = None) -> str:
            self.calls.append(("tools_documentation", {"tool": tool}))
            return "KeeperHub MCP tool documentation."

        app = server.streamable_http_app()

        async def _authz(request: Request, call_next):
            self._http_requests.append(request)
            if (
                self.fail_first_http_status is not None
                and len(self._http_requests) == 1
            ):
                return Response(status_code=self.fail_first_http_status)
            if self.expected_token is not None:
                if request.headers.get("Authorization") != (
                    f"Bearer {self.expected_token}"
                ):
                    return Response(
                        status_code=401, content="Invalid or missing API key"
                    )
            return await call_next(request)

        app.add_middleware(BaseHTTPMiddleware, dispatch=_authz)

        return app

    def start(self) -> str:
        """Start the server on a free port and return the MCP URL."""
        self._port = _free_port()
        app = self._build_app()
        config = uvicorn.Config(
            app, host="127.0.0.1", port=self._port, log_level="warning"
        )

        def run() -> None:
            asyncio.run(uvicorn.Server(config).serve())

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self._port), timeout=1):
                    return f"http://127.0.0.1:{self._port}/mcp"
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("fake KeeperHub MCP server failed to start")

    def stop(self) -> None:
        for instance in list(getattr(uvicorn.Server, "instances", set())):
            instance.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5)

    def reset(self, *, completion_after_polls: int | None = None) -> None:
        """Clear recorded state between tests."""
        self.executions.clear()
        self.calls.clear()
        self._http_requests.clear()
        self._next_execution = 1
        if completion_after_polls is not None:
            self.completion_after_polls = completion_after_polls

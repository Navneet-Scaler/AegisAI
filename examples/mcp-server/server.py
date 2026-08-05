#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=2.0,<3", "httpx"]
# ///
"""An MCP server whose tool calls are scored by AegisAI before they execute.

Point an MCP client (Claude Desktop, any MCP-compatible agent host) at this
server instead of a bare tool server, and every tools/call it sends passes
through POST /v1/guard first: on allow the tool actually runs, on hold or
block it returns a structured MCP result instead, never a raw HTTP error,
so the calling agent gets something it can reason about, not a crash.

This is the highest-leverage integration point right now because MCP is
becoming the default interop layer between agent hosts and tools: an
integrator who already speaks MCP gets AegisAI's chokepoint by pointing at
a different server, not by hand-writing a call to /v1/guard themselves.

Implemented against the official MCP Python SDK (mcp>=2.0,<3), JSON-RPC 2.0
over stdio, the same transport Claude Desktop uses. Pinned to that major
version deliberately: the spec is still evolving, and an adapter that
silently followed a breaking protocol change would be worse than one that
fails to install.

Setup:
    export AEGIS_BASE_URL=http://localhost:8000   # a running AegisAI instance
    export AEGIS_API_KEY=$(curl -s -X POST $AEGIS_BASE_URL/v1/keys \
        -H "Content-Type: application/json" -d '{}' | python3 -c \
        "import json,sys; print(json.load(sys.stdin)['key'])")

    uv run examples/mcp-server/server.py

Point your MCP client's config at this command. See README.md in this
directory for a Claude Desktop config example.
"""

from __future__ import annotations

import os
import sys

import httpx
import mcp.server.stdio
import mcp.types as types
from mcp.server import InitializationOptions, NotificationOptions, Server, ServerRequestContext

AEGIS_BASE_URL = os.environ.get("AEGIS_BASE_URL", "http://localhost:8000")
AEGIS_API_KEY = os.environ.get("AEGIS_API_KEY", "")

# The same six mock tools the rest of this repo's demo uses, implemented
# locally here rather than imported from the backend package: an MCP
# adapter has to work standalone, wrapping tools it has never seen, the
# same as any other integration.
_CUSTOMERS = {
    "CUST-1001": {"name": "Priya Sharma", "email": "priya@acmecorp.test", "balance": 120.0},
    "CUST-1002": {"name": "Diego Alvarez", "email": "diego@brightlabs.test", "balance": 0.0},
}
_TICKETS = {
    "TCK-4417": {
        "customer_id": "CUST-1001",
        "subject": "Overcharged on last invoice",
        "body": "I was billed $42 twice this month, please refund the duplicate charge.",
    }
}

TOOLS = [
    types.Tool(
        name="read_ticket",
        description="Fetch a support ticket by its ID.",
        inputSchema={
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    ),
    types.Tool(
        name="create_refund",
        description="Issue a refund to a customer.",
        inputSchema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "amount": {"type": "number"},
                "reason": {"type": "string"},
            },
            "required": ["customer_id", "amount", "reason"],
        },
    ),
    types.Tool(
        name="delete_customer",
        description="Permanently delete a customer record.",
        inputSchema={
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        },
    ),
]


def _execute_tool(name: str, arguments: dict) -> str:
    if name == "read_ticket":
        ticket = _TICKETS.get(arguments["id"])
        return str(ticket) if ticket else f"No ticket {arguments['id']}"
    if name == "create_refund":
        return f"Refunded {arguments['amount']} to {arguments['customer_id']}: {arguments['reason']}"
    if name == "delete_customer":
        deleted = _CUSTOMERS.pop(arguments["customer_id"], None)
        return "Deleted." if deleted else f"No customer {arguments['customer_id']}"
    return f"Unknown tool {name}"


async def _guard(tool_name: str, arguments: dict) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{AEGIS_BASE_URL}/v1/guard",
            json={"tool": tool_name, "args": arguments},
            headers={"Authorization": f"Bearer {AEGIS_API_KEY}"},
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()


async def on_list_tools(
    ctx: ServerRequestContext, params: types.PaginatedRequestParams | None
) -> types.ListToolsResult:
    return types.ListToolsResult(tools=TOOLS)


async def on_call_tool(
    ctx: ServerRequestContext, params: types.CallToolRequestParams
) -> types.CallToolResult:
    arguments = params.arguments or {}
    verdict = await _guard(params.name, arguments)

    if verdict["verdict"] == "block":
        return types.CallToolResult(
            isError=True,
            content=[
                types.TextContent(
                    type="text",
                    text=f"Blocked by AegisAI: {verdict['reasoning'] or 'policy violation'}",
                )
            ],
        )

    if verdict["verdict"] == "hold":
        return types.CallToolResult(
            isError=False,
            content=[
                types.TextContent(
                    type="text",
                    text=(
                        f"Held for human review by AegisAI (call_id={verdict['call_id']}). "
                        "Not executed. A reviewer needs to approve this before it can run."
                    ),
                )
            ],
        )

    result = _execute_tool(params.name, arguments)
    return types.CallToolResult(content=[types.TextContent(type="text", text=result)])


server = Server(
    "aegisai-guarded-tools",
    version="0.1.0",
    description="Mock CRM tools, every call scored by AegisAI before it executes.",
    on_list_tools=on_list_tools,
    on_call_tool=on_call_tool,
)


async def main() -> None:
    if not AEGIS_API_KEY:
        print(
            "Set AEGIS_API_KEY first. Mint one with POST /v1/keys against "
            f"{AEGIS_BASE_URL}.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="aegisai-guarded-tools",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    import anyio

    anyio.run(main)

#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=2.0,<3", "httpx"]
# ///
"""Exercises server.py's on_call_tool against a real, running AegisAI
instance, without going through the stdio/MCP transport at all: this only
proves the guard-then-forward logic itself, the same way
examples/openai-function-calling/test_guard_client.py proves that
integration's guard() call in isolation.

Run with a server up (docker compose up, or uv run uvicorn aegis.main:app):
    uv run examples/mcp-server/test_guard_integration.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
import server  # noqa: E402


def _mint_key(base_url: str) -> str:
    request = urllib.request.Request(
        f"{base_url}/v1/keys",
        data=json.dumps({"owner_label": "mcp-example-test"}).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())["key"]


class _FakeContext:
    """on_list_tools/on_call_tool's first argument, unused by this
    server's implementation, a real ServerRequestContext is only ever
    constructed by the SDK's own session machinery."""


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    server.AEGIS_BASE_URL = args.base_url
    server.AEGIS_API_KEY = os.environ.get("AEGIS_API_KEY") or _mint_key(args.base_url)

    tools = await server.on_list_tools(_FakeContext(), None)
    assert len(tools.tools) == 3, tools.tools
    print(f"tools/list -> {[t.name for t in tools.tools]}")

    allow_result = await server.on_call_tool(
        _FakeContext(),
        server.types.CallToolRequestParams(name="read_ticket", arguments={"id": "TCK-4417"}),
    )
    assert not allow_result.is_error
    print(f"read_ticket -> executed: {allow_result.content[0].text}")

    hold_result = await server.on_call_tool(
        _FakeContext(),
        server.types.CallToolRequestParams(
            name="delete_customer", arguments={"customer_id": "CUST-1002"}
        ),
    )
    assert not hold_result.is_error
    assert "Held for human review" in hold_result.content[0].text
    print(f"delete_customer -> {hold_result.content[0].text}")

    print("\nserver.py's guard-then-forward logic works against a live AegisAI instance.")


if __name__ == "__main__":
    asyncio.run(main())

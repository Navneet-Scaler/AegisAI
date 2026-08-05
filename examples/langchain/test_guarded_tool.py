# /// script
# requires-python = ">=3.11"
# dependencies = ["langchain-core>=0.3", "httpx"]
# ///
"""Exercises guard_tool() against a real, running AegisAI instance, no LLM
or agent loop needed: mints a key, wraps two plain LangChain tools, calls
them through the standard .run() surface, and checks the verdicts.

Run with a server up (docker compose up, or uv run uvicorn aegis.main:app):
    uv run examples/langchain/test_guarded_tool.py
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request

from guarded_tool import guard_tool
from langchain_core.tools import tool


def _mint_key(base_url: str) -> str:
    request = urllib.request.Request(
        f"{base_url}/v1/keys",
        data=json.dumps({"owner_label": "langchain-example-test"}).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())["key"]


@tool
def read_ticket(id: str) -> str:
    """Fetch a support ticket by its ID."""
    return f"ticket {id}: billed twice, please refund"


@tool
def delete_customer(customer_id: str) -> str:
    """Permanently delete a customer record."""
    return f"deleted {customer_id}"


@tool("delete_customer")
def bulk_delete_customers(customer_ids: list) -> str:
    """Delete many customer records in one call. Named delete_customer (not
    its Python function name) so AegisAI's destructive-delete and
    bulk-delete-block rules, which match on tool name, actually apply. Kept
    as a separate LangChain tool object from the single-id delete_customer
    above only so this test can exercise both the hold and block paths in
    one run; a real integration would have one delete_customer tool."""
    return f"deleted {len(customer_ids)} records"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    api_key = os.environ.get("AEGIS_API_KEY") or _mint_key(args.base_url)

    guarded_read = guard_tool(read_ticket, base_url=args.base_url, api_key=api_key)
    guarded_delete = guard_tool(delete_customer, base_url=args.base_url, api_key=api_key)

    # Same name/description as the wrapped tool: a drop-in replacement.
    assert guarded_read.name == "read_ticket"
    assert guarded_delete.name == "delete_customer"

    read_result = guarded_read.run({"id": "TCK-4417"})
    print(f"read_ticket -> {read_result}")
    assert "billed twice" in str(read_result)

    delete_result = guarded_delete.run({"customer_id": "CUST-1002"})
    print(f"delete_customer (1 id) -> {delete_result}")
    assert isinstance(delete_result, dict) and delete_result["status"] == "held_for_review"

    guarded_bulk_delete = guard_tool(
        bulk_delete_customers, base_url=args.base_url, api_key=api_key
    )
    bulk_result = guarded_bulk_delete.run({"customer_ids": [f"C{i}" for i in range(20)]})
    print(f"delete_customer (20 ids) -> {bulk_result}")
    assert "AegisAI blocked" in str(bulk_result)

    print("\nguard_tool() works against a live AegisAI instance through the standard .run() surface.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Exercises `guard()` from agent.py against a real, running AegisAI
instance. No OpenAI key needed, this only proves the AegisAI side of the
integration: mint a key, call guard() the same way agent.py does, check
the shape and the verdict.

Run with a server up (docker compose up, or uv run uvicorn aegis.main:app):
    python3 test_guard_client.py
    python3 test_guard_client.py --base-url https://aiaegis.vercel.app/api/backend
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request

import agent


def _mint_key(base_url: str) -> str:
    request = urllib.request.Request(
        f"{base_url}/v1/keys",
        data=json.dumps({"owner_label": "openai-example-test"}).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())["key"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    agent.AEGIS_BASE_URL = args.base_url
    agent.AEGIS_API_KEY = os.environ.get("AEGIS_API_KEY") or _mint_key(args.base_url)

    allow_case = agent.guard(
        tool_name="read_ticket",
        arguments={"id": "TCK-4417"},
        user_request="look into my last invoice",
        history=[],
    )
    assert allow_case["verdict"] in {"allow", "hold", "block"}, allow_case
    print(f"read_ticket -> {allow_case['verdict']} (score={allow_case['score']:.2f})")

    hold_case = agent.guard(
        tool_name="delete_customer",
        arguments={"customer_id": "8842"},
        user_request="clean up test accounts",
        history=[],
    )
    assert hold_case["verdict"] in {"hold", "block"}, hold_case
    print(f"delete_customer -> {hold_case['verdict']} (score={hold_case['score']:.2f})")

    print("\nagent.py's guard() call works against a live AegisAI instance.")


if __name__ == "__main__":
    main()

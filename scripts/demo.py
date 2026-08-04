#!/usr/bin/env python3
"""A client of the public API, exactly like any external caller would be.

This does not import anything from the `aegis` package. It talks to
POST /v1/keys and POST /v1/guard over plain HTTP, the same as an agent
written in Go or Ruby or curl would. That is the point: the API has to
work standalone, decoupled from this repo's own demo, or the pivot from
"internal middleware" to "hosted service" is not real.

Usage:
    uv run python scripts/demo.py
    python3 scripts/demo.py --base-url https://aiaegis.vercel.app/api/backend
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

SCENARIOS = [
    {
        "label": "a routine, read-only lookup",
        "tool": "read_ticket",
        "args": {"id": "TCK-4417"},
        "context": {"user_request": "look into my last invoice"},
    },
    {
        "label": "a small, unremarkable refund",
        "tool": "create_refund",
        "args": {"customer_id": "CUST-1001", "amount": 12.5, "reason": "goodwill"},
        "context": {"user_request": "please refund the small overcharge"},
    },
    {
        "label": "a destructive delete, held by policy regardless of context",
        "tool": "delete_customer",
        "args": {"customer_id": "8842"},
        "context": {"user_request": "clean up test accounts"},
    },
]


def _post(url: str, payload: dict, *, headers: dict | None = None) -> dict:
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json", **(headers or {})}
    )
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        print(f"  -> HTTP {exc.code}: {exc.read().decode()}", file=sys.stderr)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Where AegisAI is running. Defaults to a local docker compose instance.",
    )
    args = parser.parse_args()

    print(f"Minting a key against {args.base_url} ...")
    key_response = _post(f"{args.base_url}/v1/keys", {"owner_label": "scripts/demo.py"})
    api_key = key_response["key"]
    print(f"  key: {api_key[:20]}... (owner: {key_response['owner_label']})\n")

    for scenario in SCENARIOS:
        print(f"-> {scenario['label']}")
        result = _post(
            f"{args.base_url}/v1/guard",
            {"tool": scenario["tool"], "args": scenario["args"], "context": scenario["context"]},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        print(
            f"   verdict={result['verdict']:<6} score={result['score']:.2f}  "
            f"(rule={result['layers']['rule']:.2f} "
            f"pattern={result['layers']['pattern']:.2f} "
            f"judge={result['layers']['judge']:.2f})"
        )
        if result["reasoning"]:
            print(f"   judge: {result['reasoning']}")
        print()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""A plain OpenAI function-calling loop, guarded by AegisAI.

This is not a framework integration or a decorator, on purpose: the whole
point of the pivot to a hosted API is that guarding a tool call is one HTTP
request, so it drops into whatever agent code you already have, regardless
of what it's built on. This example uses the OpenAI SDK directly with no
framework in between, since a plain function-calling loop is the lowest
common denominator every agent eventually reduces to.

The shape that matters is `guard()` below: before any tool call executes,
it is scored by AegisAI first. Everything else here is standard OpenAI
function-calling boilerplate.

Setup:
    pip install openai
    export OPENAI_API_KEY=...
    export AEGIS_API_KEY=...          # from POST /v1/keys, see the README
    python3 agent.py "Refund the duplicate charge on ticket TCK-4417"

Not run as part of this repo's test suite: it depends on a real OpenAI key,
which this project does not have and should not require to demonstrate the
AegisAI side of the integration. `test_guard_client.py` next to this file
covers the `guard()` function itself against a real AegisAI instance,
without needing OpenAI at all.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

AEGIS_BASE_URL = os.environ.get("AEGIS_BASE_URL", "http://localhost:8000")
AEGIS_API_KEY = os.environ.get("AEGIS_API_KEY", "")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_ticket",
            "description": "Fetch a support ticket by its ID.",
            "parameters": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_refund",
            "description": "Issue a refund to a customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "amount": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["customer_id", "amount", "reason"],
            },
        },
    },
]


class GuardBlocked(Exception):
    """Raised when AegisAI blocks a call outright. A held call is not an
    error, a real integration surfaces it to a human reviewer instead of
    raising; this example keeps that branch simple since the point here is
    the OpenAI wiring, not a full approval UI."""


def guard(*, tool_name: str, arguments: dict, user_request: str, history: list[dict]) -> dict:
    """The one call that has to happen before any tool executes. Everything
    else in this file is standard OpenAI function-calling plumbing."""
    body = json.dumps(
        {
            "tool": tool_name,
            "args": arguments,
            "context": {"user_request": user_request, "history": history},
        }
    ).encode()

    request = urllib.request.Request(
        f"{AEGIS_BASE_URL}/v1/guard",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AEGIS_API_KEY}",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def execute_tool(tool_name: str, arguments: dict) -> str:
    """Stand-ins for whatever your agent's real tools do. AegisAI never
    calls these itself; it only ever returns a verdict."""
    if tool_name == "read_ticket":
        return json.dumps({"id": arguments["id"], "body": "Billed twice, please refund."})
    if tool_name == "create_refund":
        return json.dumps({"status": "refunded", **arguments})
    return json.dumps({"error": f"unknown tool {tool_name}"})


def run(user_request: str) -> None:
    from openai import OpenAI

    client = OpenAI()
    messages = [{"role": "user", "content": user_request}]
    history: list[dict] = []

    for _ in range(6):
        response = client.chat.completions.create(
            model="gpt-4o-mini", messages=messages, tools=TOOLS
        )
        choice = response.choices[0].message

        if not choice.tool_calls:
            print(choice.content)
            return

        messages.append(choice)
        for call in choice.tool_calls:
            arguments = json.loads(call.function.arguments)

            verdict = guard(
                tool_name=call.function.name,
                arguments=arguments,
                user_request=user_request,
                history=history,
            )
            print(
                f"[aegisai] {call.function.name} -> {verdict['verdict']} "
                f"(score={verdict['score']:.2f})",
                file=sys.stderr,
            )

            if verdict["verdict"] == "block":
                raise GuardBlocked(verdict["reasoning"] or "blocked by policy")
            if verdict["verdict"] == "hold":
                # A real integration would surface this to a human reviewer
                # and wait; this example stops here rather than fake an
                # approval, since guessing one would defeat the point.
                print(
                    f"[aegisai] held for review, not executing: {call.function.name}",
                    file=sys.stderr,
                )
                result = json.dumps({"status": "held_for_review", "call_id": verdict["call_id"]})
            else:
                result = execute_tool(call.function.name, arguments)

            history.append({"tool_name": call.function.name, "result": result})
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": result}
            )


if __name__ == "__main__":
    if not AEGIS_API_KEY:
        raise SystemExit(
            "Set AEGIS_API_KEY first. Mint one with:\n"
            f'  curl -X POST {AEGIS_BASE_URL}/v1/keys -H "Content-Type: application/json" -d "{{}}"'
        )
    run(" ".join(sys.argv[1:]) or "Refund the duplicate charge on ticket TCK-4417")

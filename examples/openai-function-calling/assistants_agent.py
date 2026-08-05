#!/usr/bin/env python3
"""The OpenAI Assistants API variant, guarded by AegisAI.

Structurally different from `agent.py`'s plain chat-completions loop: the
Assistants API is thread and run based, and a proposed tool call arrives as
`run.required_action.submit_tool_outputs.tool_calls` instead of a message's
`tool_calls`. The guarding discipline is identical either way: before any
tool output is submitted back to the run, it is scored by AegisAI first.
Listed as its own integration in the roadmap on purpose, since the wiring
is different enough from plain function-calling that "the same example
covers both" would be a stretch.

Reuses `TOOLS`, `guard()`, and `execute_tool()` from `agent.py` rather than
duplicating them: the guard call and the mock tool implementations don't
change between the two OpenAI API shapes, only how a proposed call is
received and how its output is submitted back.

Setup, same as agent.py:
    pip install openai
    export OPENAI_API_KEY=...
    export AEGIS_API_KEY=...          # from POST /v1/keys, see the README
    python3 assistants_agent.py "Refund the duplicate charge on ticket TCK-4417"

Not run as part of this repo's test suite, for the same reason as agent.py:
it needs a real OpenAI key. test_guard_client.py already covers the guard()
call this file also uses, without needing OpenAI at all.
"""

from __future__ import annotations

import json
import os
import sys
import time

from agent import TOOLS, execute_tool, guard

AEGIS_API_KEY = os.environ.get("AEGIS_API_KEY", "")
_POLL_INTERVAL_SECONDS = 1.0
_MAX_POLLS = 60


def run(user_request: str) -> None:
    from openai import OpenAI

    client = OpenAI()

    assistant = client.beta.assistants.create(
        name="AegisAI guarded assistant",
        instructions="You help resolve customer support tickets.",
        model="gpt-4o-mini",
        tools=TOOLS,
    )
    thread = client.beta.threads.create()
    client.beta.threads.messages.create(thread_id=thread.id, role="user", content=user_request)
    active_run = client.beta.threads.runs.create(thread_id=thread.id, assistant_id=assistant.id)

    for _ in range(_MAX_POLLS):
        active_run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=active_run.id)

        if active_run.status == "completed":
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            print(messages.data[0].content[0].text.value)
            return

        if active_run.status == "requires_action":
            tool_outputs = []
            for call in active_run.required_action.submit_tool_outputs.tool_calls:
                arguments = json.loads(call.function.arguments)

                verdict = guard(
                    tool_name=call.function.name,
                    arguments=arguments,
                    user_request=user_request,
                    history=[],
                )
                print(
                    f"[aegisai] {call.function.name} -> {verdict['verdict']} "
                    f"(score={verdict['score']:.2f})",
                    file=sys.stderr,
                )

                if verdict["verdict"] == "block":
                    output = json.dumps(
                        {"error": f"blocked by AegisAI: {verdict['reasoning'] or 'policy'}"}
                    )
                elif verdict["verdict"] == "hold":
                    output = json.dumps(
                        {"status": "held_for_review", "call_id": verdict["call_id"]}
                    )
                else:
                    output = execute_tool(call.function.name, arguments)

                tool_outputs.append({"tool_call_id": call.id, "output": output})

            active_run = client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread.id, run_id=active_run.id, tool_outputs=tool_outputs
            )
            continue

        if active_run.status in {"failed", "cancelled", "expired"}:
            raise RuntimeError(f"Run ended with status: {active_run.status}")

        time.sleep(_POLL_INTERVAL_SECONDS)

    raise TimeoutError("Run did not complete within the polling window.")


if __name__ == "__main__":
    if not AEGIS_API_KEY:
        raise SystemExit("Set AEGIS_API_KEY first. See agent.py's message for how.")
    run(" ".join(sys.argv[1:]) or "Refund the duplicate charge on ticket TCK-4417")

# /// script
# requires-python = ">=3.11"
# dependencies = ["langchain-core>=0.3", "httpx"]
# ///
"""Wrap any LangChain tool so POST /v1/guard runs before it executes.

LangChain remains one of the most widely used agent frameworks, and every
LangChain user without this re-derives the same boilerplate: intercept the
tool call, call guard, branch on the verdict. `guard_tool()` removes that,
meeting developers where they already are rather than requiring a framework
migration or a hand-written HTTP call.

Returns a real `StructuredTool`, a `BaseTool` subclass, so it drops into an
agent's existing tool list exactly like any other LangChain tool: same
`.run()` / `.invoke()` / `.arun()` / `.ainvoke()` surface, same
`args_schema`, same `name` and `description`. Call it through those methods,
not `._run()` directly, so LangChain's own callback manager still fires
(`on_tool_start` / `on_tool_end` / `on_tool_error`), which is what makes a
held or blocked call show up in an existing LangSmith or tracing setup
instead of disappearing silently.

A `block` verdict raises `ToolException`, LangChain's own mechanism for a
tool refusing to run. The returned tool sets `handle_tool_error=True`, so
that exception is caught by LangChain itself and surfaced as the tool's
string output rather than propagating, the same default most
`AgentExecutor` setups use so one blocked tool call doesn't crash an entire
run. The callback manager still fires `on_tool_error` before that happens,
so the block is still visible to LangSmith or any other tracing hooked into
the agent, it just also becomes something the agent can read and react to.
A `hold` verdict returns a value directly, never raises, since a call
awaiting review is not a tool failure.
"""

from __future__ import annotations

import httpx
from langchain_core.tools import BaseTool, StructuredTool, ToolException


class GuardHeld(RuntimeError):
    """Raised by the strict variant below. Most callers should prefer the
    default behaviour (return a value describing the hold) so their agent
    can keep reasoning about it; this is here for callers who would rather
    treat a hold the same as a hard stop."""


def guard_tool(
    tool: BaseTool,
    *,
    base_url: str,
    api_key: str,
    user_request: str = "",
    raise_on_hold: bool = False,
) -> BaseTool:
    """Wrap `tool` so every call is scored by AegisAI first.

    The returned tool has the same name, description, and args_schema as
    the one passed in: an agent that already has `tool` in its tool list
    can swap it for `guard_tool(tool, ...)` with no other code changes.
    """

    def _guard(kwargs: dict) -> dict:
        response = httpx.post(
            f"{base_url}/v1/guard",
            json={"tool": tool.name, "args": kwargs, "context": {"user_request": user_request}},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()

    async def _aguard(kwargs: dict) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/v1/guard",
                json={
                    "tool": tool.name,
                    "args": kwargs,
                    "context": {"user_request": user_request},
                },
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()

    def _handle_verdict(verdict: dict, kwargs: dict):
        if verdict["verdict"] == "block":
            raise ToolException(
                f"AegisAI blocked {tool.name}: {verdict['reasoning'] or 'policy violation'}"
            )
        if verdict["verdict"] == "hold":
            if raise_on_hold:
                raise GuardHeld(
                    f"AegisAI held {tool.name} for review (call_id={verdict['call_id']})"
                )
            return {
                "status": "held_for_review",
                "call_id": verdict["call_id"],
                "reasoning": verdict["reasoning"],
            }
        return None  # allow: caller executes the wrapped tool below

    def guarded_run(**kwargs) -> object:
        verdict = _guard(kwargs)
        held = _handle_verdict(verdict, kwargs)
        if held is not None:
            return held
        return tool.run(kwargs)

    async def guarded_arun(**kwargs) -> object:
        verdict = await _aguard(kwargs)
        held = _handle_verdict(verdict, kwargs)
        if held is not None:
            return held
        return await tool.arun(kwargs)

    return StructuredTool.from_function(
        func=guarded_run,
        coroutine=guarded_arun,
        name=tool.name,
        description=tool.description,
        args_schema=tool.args_schema,
        handle_tool_error=True,
    )

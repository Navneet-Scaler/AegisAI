"""Tool registry.

Tools declare themselves with the `@tool` decorator. The registry exports their
JSON schemas for the model and resolves a name back to its implementation.

The registry deliberately does not execute anything. Execution lives behind
`AegisAI.guard`, and keeping the two apart is what makes the chokepoint
structural rather than a convention.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

Destructiveness = Literal["read", "write", "external", "destructive"]

_PY_TO_JSON = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    destructiveness: Destructiveness
    fn: Callable[..., Any]
    parameters: dict[str, Any] = field(default_factory=dict)

    def schema(self) -> dict[str, Any]:
        """The declaration handed to the model."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name!r} is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def require(self, name: str) -> Tool:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name!r}")
        return tool

    def names(self) -> list[str]:
        return sorted(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        return [self._tools[name].schema() for name in self.names()]

    def __len__(self) -> int:
        return len(self._tools)


registry = ToolRegistry()

# An external caller's tool is not in AegisAI's own registry and carries no
# destructiveness hint in the public API's request schema. "write" is the
# moderate default: not as trusting as "read", not as alarmist as
# "destructive". Shared between the public scoring path and the policy
# dry-run engine so both treat an unregistered tool name identically.
_EXTERNAL_DEFAULT_DESTRUCTIVENESS: Destructiveness = "write"


def resolve_or_external(tool_name: str) -> Tool:
    known = registry.get(tool_name)
    if known is not None:
        return known
    return Tool(
        name=tool_name,
        description="External tool, not in AegisAI's own registry.",
        destructiveness=_EXTERNAL_DEFAULT_DESTRUCTIVENESS,
        fn=lambda **_: None,
    )


def tool(
    *, destructiveness: Destructiveness, description: str
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register a function as an agent tool.

    `destructiveness` is a first class property rather than something inferred
    from the name at scoring time. Inferring it from a `delete_` prefix would
    mean a tool called `purge_records` scores as harmless.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        registry.register(
            Tool(
                name=fn.__name__,
                description=description,
                destructiveness=destructiveness,
                fn=fn,
                parameters=_parameters_from_signature(fn),
            )
        )
        return fn

    return decorator


def _parameters_from_signature(fn: Callable[..., Any]) -> dict[str, Any]:
    """Build a JSON schema object from the function signature."""
    signature = inspect.signature(fn)
    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, parameter in signature.parameters.items():
        annotation = parameter.annotation
        origin = getattr(annotation, "__origin__", annotation)
        json_type = _PY_TO_JSON.get(origin, "string")

        entry: dict[str, Any] = {"type": json_type}
        if json_type == "array":
            args = getattr(annotation, "__args__", ())
            item_type = _PY_TO_JSON.get(args[0], "string") if args else "string"
            entry["items"] = {"type": item_type}
        properties[name] = entry

        if parameter.default is inspect.Parameter.empty:
            required.append(name)

    return {"type": "object", "properties": properties, "required": required}

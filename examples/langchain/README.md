# Example: a LangChain tool wrapper guarded by AegisAI

`guard_tool()` wraps any LangChain `BaseTool` so `POST /v1/guard` runs before
it executes. The result is a real `StructuredTool`: same `name`,
`description`, and `args_schema` as the tool you passed in, so it's a
drop-in replacement in an existing agent's tool list, not a new API to
learn.

```python
from guarded_tool import guard_tool

guarded = guard_tool(my_tool, base_url="http://localhost:8000", api_key=key)
agent_tools = [guarded, *other_tools]  # used exactly like any other tool
```

## Try it, no LLM needed

```bash
# with an AegisAI instance running (docker compose up, from the repo root)
cd examples/langchain
uv run test_guarded_tool.py
```

Wraps three plain LangChain tools and calls them through the standard
`.run()` surface, no agent loop, no LLM key required. Exercises all three
verdicts:

| Verdict | What `guarded.run()` returns |
|---|---|
| `allow` | The wrapped tool actually runs, its normal return value |
| `hold` | `{"status": "held_for_review", "call_id": ..., "reasoning": ...}` |
| `block` | LangChain's own `ToolException` mechanism, caught (`handle_tool_error=True`) and surfaced as the tool's string output, so one blocked call doesn't crash an entire agent run. `on_tool_error` still fires first, so tracing (LangSmith or otherwise) still sees it. |

## Use it with a real agent

```python
from guarded_tool import guard_tool
from langchain_core.tools import tool

@tool
def delete_customer(customer_id: str) -> str:
    """Permanently delete a customer record."""
    ...

guarded_delete = guard_tool(
    delete_customer,
    base_url="http://localhost:8000",
    api_key=API_KEY,
    user_request=the_users_original_message,
)

# guarded_delete now goes into your agent's tool list like any other tool.
```

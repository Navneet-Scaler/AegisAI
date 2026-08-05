# Example: an MCP server, every tool call scored by AegisAI first

MCP (Model Context Protocol) is becoming the default interop layer between
agent hosts and tools. This is the highest-leverage integration point right
now: point an MCP client at this server instead of a bare tool server, and
`tools/call` is scored by `POST /v1/guard` before anything executes, with no
application code changes on the client side.

Implemented against the official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
(`mcp>=2.0,<3`), JSON-RPC 2.0 over stdio, the same transport Claude Desktop
uses. Pinned to that major version: the protocol is still evolving, and an
adapter that silently followed a breaking change would be worse than one
that fails to install.

## Try the AegisAI side, no MCP client needed

```bash
# with an AegisAI instance running (docker compose up, from the repo root)
uv run examples/mcp-server/test_guard_integration.py
```

Mints a key, calls `on_list_tools` and `on_call_tool` directly, no stdio
transport involved. Proves the guard-then-forward logic works: a read
executes, a delete comes back "held for human review", never a raw error.

## Run the real MCP server

```bash
export AEGIS_BASE_URL=http://localhost:8000
export AEGIS_API_KEY=$(curl -s -X POST $AEGIS_BASE_URL/v1/keys \
  -H "Content-Type: application/json" -d '{}' | python3 -c \
  "import json,sys; print(json.load(sys.stdin)['key'])")

uv run examples/mcp-server/server.py
```

It speaks JSON-RPC 2.0 over stdin/stdout. To point Claude Desktop at it, add
to its MCP server config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "aegisai-guarded-tools": {
      "command": "uv",
      "args": ["run", "/absolute/path/to/examples/mcp-server/server.py"],
      "env": {
        "AEGIS_BASE_URL": "http://localhost:8000",
        "AEGIS_API_KEY": "aegis_live_..."
      }
    }
  }
}
```

## What happens on each verdict

| Verdict | MCP response |
|---|---|
| `allow` | The tool actually runs, result returned as normal |
| `hold` | A structured, non-error result: "held for human review", the call id, nothing executed |
| `block` | An MCP tool error with the judge's reasoning, nothing executed |

Held and blocked calls never crash the client with a raw HTTP error; they
come back as an MCP result the calling agent can read and reason about,
same as any other tool response.

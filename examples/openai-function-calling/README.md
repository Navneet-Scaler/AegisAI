# Example: a plain OpenAI function-calling loop, guarded by AegisAI

Not a framework adapter, a plain function-calling loop, since that is what
every agent framework eventually reduces to. `guard()` in `agent.py` is the
one call that matters: before any tool executes, it is scored by AegisAI
over HTTP first.

## Try the AegisAI side, no OpenAI key needed

```bash
# with an AegisAI instance running (docker compose up, from the repo root)
cd examples/openai-function-calling
python3 test_guard_client.py
```

This mints a key, calls `guard()` twice the same way `agent.py` does, and
prints the verdicts. It proves the integration point works standalone.

## Run the full agent

```bash
pip install openai
export OPENAI_API_KEY=sk-...
export AEGIS_API_KEY=$(curl -s -X POST http://localhost:8000/v1/keys \
  -H "Content-Type: application/json" -d '{}' | python3 -c "import json,sys; print(json.load(sys.stdin)['key'])")

python3 agent.py "Refund the duplicate charge on ticket TCK-4417"
```

Watch stderr: every tool call the model proposes is printed with the
verdict AegisAI gave it before `execute_tool()` ever runs.

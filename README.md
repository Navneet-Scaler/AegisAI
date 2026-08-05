<div align="center">

# AegisAI

### Constrain the architecture, not the prompt.

A middleware firewall that sits between an AI agent and its tools. Every tool call is
intercepted before it executes, scored by a layered risk engine, and then allowed, held
for a human, or blocked.

[![CI](https://github.com/Navneet-Scaler/AegisAI/actions/workflows/ci.yml/badge.svg)](https://github.com/Navneet-Scaler/AegisAI/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![Next.js 16](https://img.shields.io/badge/next.js-16-black)
![License MIT](https://img.shields.io/badge/license-MIT-green)

**[Live demo: aiaegis.vercel.app](https://aiaegis.vercel.app)** ·
**[Quickstart: wire it into your agent in 5 minutes](https://aiaegis.vercel.app/quickstart)** ·
**[Full writeup: constrain the architecture, not the prompt](WRITEUP.md)**

</div>

---

![The AegisAI dashboard: a held delete_customer call, its composite score broken down into the rule, pattern, and judge layers, and the approve/block controls](docs/assets/demo.gif)

*Recorded against a running instance: a refund auto allows, a delete is held by policy,
its full risk breakdown is inspected, and it is approved through the token protected
endpoint. Not a mockup, every frame is the real dashboard driven through the real API.*

---

## The problem

Agent safety today is mostly enforced by asking the model nicely. A system prompt saying
"never delete customer records" is advisory: it is one string in a context window,
competing with every other string in that window, including whatever text the agent reads
out of a support ticket.

Meanwhile the tools are real. They send email, issue refunds, and drop rows. Nothing
structural stands between a hijacked agent and the database.

AegisAI is that structure. It does not ask the agent to behave. It removes the code path
where misbehaving was possible.

## Run it yourself

```bash
git clone https://github.com/Navneet-Scaler/AegisAI
cd AegisAI
docker compose up
```

That's the whole setup. No API key, no signup, no `.env` file required: it falls back to
a mock LLM provider and SQLite automatically. Once it's up, mint a key and score a call:

```bash
KEY=$(curl -s -X POST http://localhost:8000/v1/keys -H "Content-Type: application/json" -d '{}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['key'])")

curl -s -X POST http://localhost:8000/v1/guard \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"tool": "delete_customer", "args": {"customer_id": "8842"},
       "context": {"user_request": "clean up test accounts"}}' | python3 -m json.tool
```

```json
{
  "verdict": "hold",
  "score": 0.57,
  "layers": { "rule": 0.6, "pattern": 0.1, "judge": 0.95 },
  "reasoning": "The conversation contains an embedded instruction override that did not come from the user...",
  "call_id": "c_9f2a..."
}
```

Interactive docs, with a filled-in example you can run from the browser, at
[localhost:8000/docs](http://localhost:8000/docs). The dashboard is at
`localhost:3000`.

## Who can use this

The repo is public and MIT licensed. Clone it, run it, fork it, or point your own agent's
tool calls through `AegisAI.guard()` — no account or API key is required to run the full
demo locally or to read the code. The one thing gated behind the demo token is the
approve/block action on a held call (`POST /calls/{id}/decide`); everything else, including
watching the live feed and reading the audit trail, is open.

![The AegisAI landing page: an animated diagram showing a call leaving the agent, passing through the AegisAI gate, and routing to allow, hold, or block](docs/assets/landing.png)

## The approach

```
User request
     |
     v
  Agent (LLM + tools)   proposes tool_call(name, args)
     |
     v
+--------------------------------+
|            AEGISAI             |
|   1. intercept                 |
|   2. score                     |
|   3. decide                    |
|   4. persist and learn         |
+--------------------------------+
     |
     +-- allow  -->  execute, return the result to the agent
     +-- hold   -->  pause, wait for a human, then execute or refuse
     +-- block  -->  refuse, return a structured reason to the agent
```

`AegisAI.guard(tool_call, context)` is the single chokepoint. The agent loop has no code
path to a tool executor that bypasses it, and a test asserts exactly that. This is the
whole claim of the project: the constraint lives in the architecture, so it holds even
when the prompt does not.

## Features

**Interception and control**
- One chokepoint that every tool call must pass through, regardless of agent framework
- Three way verdict on every call: allow, hold for a human, or block
- Held calls pause execution and surface to a reviewer with full context
- Blocked calls return a structured refusal the agent can read and adapt to

**Layered risk scoring**
- Static rule engine for hard policy that holds regardless of the model's decision
- Behavioural pattern model that flags argument shapes this agent has not used before
- LLM judge that checks whether a call actually follows from the user's original request
- One composite score per call, with every layer's sub score and reasoning kept attached

**Learning and audit**
- Online weight updates: every human approve or reject immediately moves the model
- Full audit trail of calls, scores, reasoning, and outcomes
- Block rate, drift, and per tool and per agent risk breakdowns

**Operations**
- Fails toward hold, never toward allow, on every dependency
- Bearer token on the control plane, restrictive CORS by default
- One command demo that runs offline with no API keys

## How risk is scored

Three independent signals, combined into one explainable number.

| Layer | What it asks | Signal |
|---|---|---|
| Rules | Does this violate a hard policy? | Declarative YAML, can force a verdict outright |
| Pattern | Has this agent done anything like this before? | Online `SGDClassifier` over call features |
| Judge | Does this follow from what the user actually asked? | A second model reading the conversation |

```
score = 0.35 * rule + 0.30 * pattern + 0.35 * judge

score >= 0.75          ->  block
0.40 <= score < 0.75   ->  hold for human approval
score <  0.40          ->  allow
any forcing rule       ->  that verdict wins
```

When no rule matches, the rule component contributes a baseline of **0.1**, not 0. Zero
would mean "affirmatively safe", which no rule ever asserted. 0.1 means "nothing known
against it", which is the honest reading and keeps the composite meaningful.

### Failure behaviour

Every layer and dependency degrades toward **hold**. There is no path where a failure
results in a silent allow.

| Failure | Result |
|---|---|
| Judge API error, timeout, or malformed response | hold |
| Pattern model missing or fails to load | hold |
| Rules or policy file missing or fails to parse | hold, and the app refuses to start in production |
| Database write fails | hold, the call does not execute |
| Human approval times out | block |
| `AEGIS_DATABASE_URL` is SQLite in production | the app refuses to start |

### A known, partly open threat model: online-learner poisoning

The pattern layer learns from every human decision, which is a real strength (fast
adaptation) and a real attack surface: a burst of decisions that all push the same
direction, whether from a compromised reviewer or a careless one, can walk the decision
boundary toward permissiveness a few degrees at a time. That is a textbook data-poisoning
vulnerability for any system that learns online from a human-in-the-loop signal.

`PatternModel` tracks how far the coefficient vector has moved over the last 5 decisions
and flags it when that shift crosses a threshold (`aegis/aegisai/model.py`). While flagged,
the pattern layer refuses to trust the classifier's own opinion and reports the neutral
"nothing known against it" baseline instead, the same instinct as an unmatched rule. This
is a detector, not a fix: it catches a boundary that has already moved, it does not stop a
single bad approval from moving it a little, and the threshold is a first pass, not
calibrated against real production traffic, since none exists yet. Verified against a live
server that it triggers on a scripted, identical-shape burst of approvals; verified that it
does **not** trigger on organically evolving ones, since the pattern layer's own
`prior_approval_rate` feature naturally moderates the gradient step as a track record
builds, which is informative on its own: this defense is strongest against a repeated,
mechanical abuse pattern and weaker against one that varies. Documented here as an open
problem rather than a solved one, on purpose.

## The public API

`POST /v1/guard` is the primary way to use AegisAI: score a proposed tool call and get a
verdict back, over plain HTTP, from any language. It is stateless. It does not execute
the tool, that stays entirely yours; it only decides.

| Endpoint | What it does |
|---|---|
| `POST /v1/keys` | Mint an API key. No signup. Rate limited to 3 per IP per hour. |
| `POST /v1/keys/rotate` | Mint a replacement key, revoke the presented one. Requires the key itself. |
| `POST /v1/keys/revoke` | Immediately invalidate the presented key. Requires the key itself. |
| `GET /v1/policies` | List the available policy ids. |
| `GET /v1/policies/{id}/rules` | The policy's current active rules. |
| `POST /v1/policies/{id}/dry-run` | Simulate proposed rules against recent history. No side effects. |
| `POST /v1/policies/{id}/draft` | Save a new policy version. Requires the demo token. |
| `POST /v1/policies/{id}/versions/{v}/activate` | Activate a version (rollback is activating an old one). |
| `POST /v1/guard` | Score a call. Requires `Authorization: Bearer <key>`. 60 requests/minute per key. |
| `GET /docs` | Interactive Swagger UI with a filled-in example for `/v1/guard`. |

**Policies are edited, dry run, and activated, not overwritten in place.** Every save is a
new version; every prior version stays on record, so rolling back is just activating an
older one again, not reconstructing a lost file. Before committing to a change, dry run it:
`POST /v1/policies/{id}/dry-run` re-evaluates proposed rules against the most recent
resolved calls that were actually scored under that policy, and reports which ones would
get a different forced verdict, the same "count mode before block mode" discipline a WAF
uses before flipping a rule to block. The dashboard's **Edit policy** page wraps this in a
JSON editor with a dry-run panel and a rollback-capable version history; the underlying
endpoints work the same over plain HTTP for anyone who'd rather script it.

**Every key is scoped to a policy**, not a single global rule set for every caller. Pass
`policy_id` when minting a key (defaults to `default`, the most restrictive baseline);
`GET /v1/policies` lists what's available. The same call scores differently depending on
which key sent it: a $150 refund allows under `default` (threshold $500) and holds under
`strict` (threshold $100), because the two keys are scored against genuinely different
rule sets, not a shared one with a flag.

**Keys carry a lifecycle.** `expires_in_days` at creation, `/v1/keys/rotate` to replace a
key without a gap in validity, `/v1/keys/revoke` to kill one immediately. Both rotate and
revoke require presenting the key itself as the bearer token, proof of possession, the
same bar Stripe and GitHub use, not a separate admin password.

**Calls can carry an agent identity, kept separate from the key.** Pass `context.agent_id`
if one key fronts more than one agent (a support bot and a billing bot, say); it is tracked
independently of the API key on every audit row, the same way OAuth keeps a client ID
separate from a subject claim.

Four runnable integrations, none of which import this repo's own package, since an
external caller never would either:
- `scripts/demo.py`: mints a key and scores three example calls over plain HTTP.
- `examples/mcp-server/`: an MCP server (the interop layer most agent hosts are
  converging on) whose `tools/call` is scored by `/v1/guard` before it executes. Point
  Claude Desktop, or any MCP client, at it instead of a bare tool server, no application
  code changes. Implemented against the official MCP Python SDK, JSON-RPC 2.0 over stdio.
- `examples/langchain/`: `guard_tool()` wraps any LangChain `BaseTool`. The result is a
  real `StructuredTool`, same name, description, and args schema, a drop-in replacement
  in an existing agent's tool list, not a new API to learn.
- `examples/openai-function-calling/`: `agent.py` is a plain chat-completions
  function-calling loop; `assistants_agent.py` is the Assistants API variant (thread and
  run based, a structurally different tool-call shape, same guarding discipline). Both
  call `/v1/guard` before executing any tool. `test_guard_client.py` exercises the
  AegisAI side of it without needing an OpenAI key.

One real, non-synthetic tool: every other tool in the demo (`aegis/tools/crm.py`) is an
in-memory mock, safe and predictable but never actually intercepted mid-flight to
anything with real latency or a real failure mode. `send_webhook_notification`
(`aegis/tools/webhook.py`) makes a genuine outbound HTTPS request to
[httpbin.org](https://httpbin.org), a public request-echoing sandbox built for exactly
this, never a production third-party account, carrying an idempotency key the same way
Stripe requires for anything that might be retried. Verified end to end against the real
service: scored by `AegisAI.guard()`, allowed, executed, and it actually got a real HTTP
200 back.

The internal `AegisAI.guard()` (`aegis/aegisai/core.py`) is a different, higher-level
thing: it owns execution too, running the tool itself on allow and blocking the caller's
own request until a human decides on hold. That is what the ReAct agent and dashboard
demo use internally. `/v1/guard` only scores, which is the right contract for a public
API that has never seen your tool's implementation.

## Exportable audit trail

`GET /calls/export.csv` exports the audit trail as CSV: who, what, when, the decision,
and the reasoning behind it, one row per call, timestamped and never mutated after the
fact, the shape SOC 2 or ISO 27001 audit evidence typically expects. The live dashboard
is for a human reviewing a hold right now; a compliance stakeholder wants a static,
shareable artifact instead. Filterable by `agent_name`, `api_key_id`, `verdict`,
`tool_name`, `since`, and `until`; public, like the rest of the read surface, since it has
no side effects. The analytics page has an **Export audit trail** button that links here
directly.

## Tech stack

| Component | Choice |
|---|---|
| Agent | ReAct loop over the Google Gemini API, with six mock CRM tools |
| Middleware | FastAPI, async, server sent events for the live feed |
| Risk engine | Python rule engine, scikit-learn `SGDClassifier`, Gemini judge |
| Storage | SQLite locally, Postgres in deployment |
| Dashboard | Next.js App Router, TypeScript, Tailwind, Framer Motion, Recharts |
| Auth | Self-built API keys (SHA-256 hashed, shown once), no third-party auth provider |
| Rate limiting | `slowapi`, in process (see caveat below) |
| Deployment | Single Vercel project (frontend + backend as two services, same origin), Docker Compose locally, Railway as an alternative backend host |

Every piece above runs on a free tier with no credit card: Vercel's Hobby plan, Gemini's
free API tier (judge calls are opt in and default to a mock provider), GitHub Actions'
free tier for public repos, and SQLite or any free-tier Postgres (Neon, Vercel Postgres)
for storage. Nothing here requires a paid plan to run or to deploy.

**Rate limiting caveat:** the per-key and per-IP limits are enforced with in-process
counters. On a long-lived single instance (Docker Compose, Railway) that holds; on a
serverless deployment, each cold function invocation starts a fresh process, and those
counters reset with it. Treat the advertised limits as accurate for the single-instance
deployment path, not the serverless one, until this moves to a shared backing store.

## How to run

### Docker, no API keys needed

```bash
git clone https://github.com/Navneet-Scaler/AegisAI.git
cd AegisAI
docker compose up --build
```

Dashboard at `http://localhost:3000`, API at `http://localhost:8000`. This runs in replay
mode, which serves recorded judge verdicts, so the full demo works offline.

### Local development

```bash
# Backend
cd backend
uv venv --python 3.12
uv pip install -e ".[dev]"
uv run uvicorn aegis.main:app --reload

# Frontend, in a second terminal
cd frontend
npm install
npm run dev
```

### Running against live Gemini

```bash
cp .env.example .env
# set AEGIS_LLM_MODE=live and AEGIS_GEMINI_API_KEY=<your key>
```

### Tests

```bash
cd backend && uv run pytest
cd frontend && npm run lint && npm run build
```

### Deploy your own

The live demo at [aiaegis.vercel.app](https://aiaegis.vercel.app) is this exact repo,
deployed with the steps below. The whole app deploys as one [Vercel](https://vercel.com)
project. The root `vercel.json`
declares two services, `frontend` (Next.js) and `backend` (FastAPI), and rewrites
`/api/backend/*` to the backend so both run on the same origin.

**Steps:**
1. Import this repo on Vercel. It detects both services from `vercel.json` automatically.
2. On the `backend` service, set `AEGIS_ENVIRONMENT=production`, `AEGIS_DATABASE_URL` to a
   Postgres connection string (`postgresql+asyncpg://` scheme; Vercel Postgres or any
   managed Postgres works), and `AEGIS_DEMO_TOKEN` to a real secret. Leave
   `AEGIS_LLM_MODE=replay` unless you're setting `AEGIS_GEMINI_API_KEY` for live judge calls.
   `AEGIS_DATABASE_URL` cannot be left as SQLite here: the app checks at startup and
   refuses to run with `AEGIS_ENVIRONMENT=production` on a SQLite URL, since SQLite does
   not survive more than one running instance and the held-call approval flow depends on
   durable, consistent database state.
3. On the `frontend` service, set `NEXT_PUBLIC_API_URL=/api/backend`. Same origin, so this
   is a relative path, not a separate host.
4. Deploy.

Because the backend is same-origin behind the rewrite, `AEGIS_CORS_ORIGINS` mostly stops
mattering for the deployed app; it's still enforced server-side as defense in depth, and
still matters for local development where the frontend and backend run on different ports.

`backend/railway.toml` is kept as an alternative if you'd rather run the backend as its own
service on [Railway](https://railway.app) instead (set the service root to `backend`, add a
Postgres plugin, and point the frontend's `NEXT_PUBLIC_API_URL` at its public URL). Not the
primary path documented here, but a plain FastAPI + Docker service, so it works the same way.

Because `AEGIS_LLM_MODE` defaults to `replay`, a deployment needs no Gemini key to run
the full demo; live judge calls are opt in.

## Example: calling it directly

With the backend running (`docker compose up` or `uv run uvicorn aegis.main:app --reload`),
here's the whole loop from the terminal, no dashboard needed.

In mock and replay mode (the default, no API key needed) the agent's own turns come from a
fixed, reviewable script rather than a live model, selected with the `scenario` field:
`"refund"` (default) always allows, `"delete"` always holds. Live mode (`AEGIS_LLM_MODE=live`)
ignores `scenario` and lets Gemini decide freely from `request` instead.

**1. Run the refund scenario.** It reads a support ticket, looks up the customer, and issues
a refund, three tool calls, each passing through `AegisAI.guard()`, all auto allowed:

```bash
curl -s -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{"request": "Refund the duplicate charge on ticket TCK-4417.", "scenario": "refund"}' \
  | python3 -m json.tool
```

```json
{
  "session_id": "294c950e-...",
  "final_answer": "Refunded the duplicate $42.00 charge for Priya Sharma at Acme Corp.",
  "steps_taken": 3,
  "stopped_reason": "final_answer",
  "history": [
    { "tool_name": "read_ticket", "verdict": "allow", "...": "..." },
    { "tool_name": "search_customers", "verdict": "allow", "...": "..." },
    { "tool_name": "create_refund", "verdict": "allow", "...": "..." }
  ]
}
```

**2. Inspect the audit trail**, including the per layer scores AegisAI attached to each call:

```bash
curl -s http://localhost:8000/calls | python3 -m json.tool
```

**3. Trigger a held call.** The `delete` scenario always calls `delete_customer`, which
`seed/rules.yaml`'s `destructive-delete` rule forces to at least hold, regardless of what
the other two layers say. This request will not return until the call is resolved, run it
in the background:

```bash
curl -s -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{"request": "Please remove the requested customer record.", "scenario": "delete"}' &
```

**4. Approve or block it** with the demo token (`aegis-local-dev-token` locally, from
`.env.example`), while that request is still waiting:

```bash
CALL_ID=$(curl -s http://localhost:8000/calls | python3 -c \
  "import json,sys; print([c for c in json.load(sys.stdin) if c['status']=='pending'][0]['id'])")

curl -s -X POST "http://localhost:8000/calls/$CALL_ID/decide" \
  -H "Authorization: Bearer aegis-local-dev-token" \
  -H "Content-Type: application/json" \
  -d '{"approve": true}'
```

Approve it once and a similar refund scores lower next time, the pattern layer's weights
update the moment you send that decision.

## Demo

The GIF at the top of this README is this exact sequence, captured against a running
instance, not a mockup.

1. Click "Run refund" on the dashboard. Three tool calls stream in, all auto allowed.
2. Click "Run delete". `delete_customer` is always held by `seed/rules.yaml`'s
   `destructive-delete` rule, regardless of what the pattern or judge layers say.
3. Select the held call to see why: the composite score broken into its three layers,
   the matched rules, and the judge's reasoning.
4. Approve it with the demo token. It executes, and the run completes.
5. Run it again, the pattern layer already updated from that one decision.

## Case study: a prompt injection, caught

![A prompt injected support ticket leads to an update_billing call; AegisAI holds it and the judge's reasoning names the injected instruction](docs/assets/case-study-injection.gif)

Ticket TCK-4419 has "ignore all previous instructions" embedded in the customer's own
message, asking for a $50 billing credit framed as routine goodwill. The rule layer alone
lets it through, there is no rule for this exact shape. The judge layer reads the call's
justification against the actual conversation and holds it, because the call follows the
injected text, not the user. Click "Run prompt injection" on the dashboard to run this
scenario live, or see `backend/tests/test_prompt_injection.py` for the proof, or read
[WRITEUP.md](WRITEUP.md) for the full walkthrough of why this generalizes.

## Roadmap

- Per agent identity and scoped policy
- Rule authoring UI with dry run against historical calls
- Adapters for popular agent frameworks
- Exportable audit reports
- Per-key scoped rules, so different callers can carry different policy

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and PRs are open.

## Changelog

See [CHANGELOG.md](CHANGELOG.md). Versioned with [semver](https://semver.org/).

## License

MIT. See [LICENSE](LICENSE).

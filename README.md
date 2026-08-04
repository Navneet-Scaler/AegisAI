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

</div>

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

## The approach

```
User request
     |
     v
  Agent (LLM + tools)   proposes tool_call(name, args)
     |
     v
+--------------------------------+
|            SENTINEL            |
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

`Sentinel.guard(tool_call, context)` is the single chokepoint. The agent loop has no code
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
| Rules file missing or fails to parse | hold, and the app refuses to start in production |
| Database write fails | hold, the call does not execute |
| Human approval times out | block |

## Tech stack

| Component | Choice |
|---|---|
| Agent | ReAct loop over the Google Gemini API, with six mock CRM tools |
| Middleware | FastAPI, async, server sent events for the live feed |
| Risk engine | Python rule engine, scikit-learn `SGDClassifier`, Gemini judge |
| Storage | SQLite locally, Postgres in deployment |
| Dashboard | Next.js App Router, TypeScript, Tailwind, Framer Motion, Recharts |
| Deployment | Single Vercel project (frontend + backend as two services, same origin), Docker Compose locally, Railway as an alternative backend host |

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

The whole app deploys as one [Vercel](https://vercel.com) project. The root `vercel.json`
declares two services, `frontend` (Next.js) and `backend` (FastAPI), and rewrites
`/api/backend/*` to the backend so both run on the same origin.

**Steps:**
1. Import this repo on Vercel. It detects both services from `vercel.json` automatically.
2. On the `backend` service, set `AEGIS_ENVIRONMENT=production`, `AEGIS_DATABASE_URL` to a
   Postgres connection string (`postgresql+asyncpg://` scheme; Vercel Postgres or any
   managed Postgres works), and `AEGIS_DEMO_TOKEN` to a real secret. Leave
   `AEGIS_LLM_MODE=replay` unless you're setting `AEGIS_GEMINI_API_KEY` for live judge calls.
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

## Demo

1. An agent processes a queue of customer support requests. Calls stream into the
   dashboard and most are auto approved.
2. A bulk account deletion arrives. It is held, and execution pauses.
3. The dashboard shows why: the agent has never issued a delete at this scale, and the
   judge flagged the call as inconsistent with what the user actually asked for.
4. Approve it once, then run a similar call. The score has dropped and it passes.

## Roadmap

- Per agent identity and scoped policy
- Rule authoring UI with dry run against historical calls
- Adapters for popular agent frameworks
- Exportable audit reports

## License

MIT. See [LICENSE](LICENSE).

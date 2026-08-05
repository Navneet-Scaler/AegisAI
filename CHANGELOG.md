# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning follows
[Semantic Versioning](https://semver.org/).

## [0.6.0]

### Added
- Rule authoring UI with dry-run, at `/policy` in the dashboard, plus the
  API underneath it usable directly:
  - `GET /v1/policies/{id}/rules`, `GET /v1/policies/{id}/versions`
  - `POST /v1/policies/{id}/dry-run`: re-evaluates proposed rules against
    the most recent resolved calls actually scored under that policy, no
    side effects, no auth required. The WAF "count mode before block
    mode" pattern: see the blast radius before committing.
  - `POST /v1/policies/{id}/draft` and
    `POST /v1/policies/{id}/versions/{v}/activate`: both require the demo
    token. Every save is a new `PolicyVersion`, never an in-place edit;
    rollback is activating an older version again.
- `ToolCall.policy_id` records which policy actually scored a call, so a
  dry run compares against the calls that were really scored under that
  policy, not the whole call log.
- `POST /demo/reset` now also clears saved policy versions.

### Fixed
- A real bug caught while testing dry-run: comparing a proposed policy's
  output against `ToolCall.verdict` was wrong, since that field can be
  mutated later by a timeout or a human approval and no longer reflects
  what the rule layer itself decided at scoring time. Dry-run now compares
  against `matched_rule_ids`, which is never touched after the fact.
- Test isolation: activating a policy version is durable state shared
  across the whole test run's SQLite file, unlike the mostly-additive rows
  other tests rely on; added an autouse fixture that resets
  `PolicyVersion` between tests so one test's activated policy can't leak
  into an unrelated one.

## [0.5.0]

### Added
- Online-learner poisoning defense: `PatternModel` tracks how far its
  coefficient vector has moved over a window of recent human decisions and
  flags it when the shift crosses a threshold. While flagged, the pattern
  layer degrades to the neutral baseline instead of trusting its own
  (possibly poisoned) opinion. Documented as a known, partly open threat
  model in the README, not a fully solved one. Verified against a live
  server: triggers on a scripted, identical-shape burst of approvals;
  does not trigger on organically evolving ones, since
  `prior_approval_rate` naturally moderates the gradient step as a track
  record builds.
- `GET /analytics/model` now reports `drift_detected` and
  `last_drift_magnitude`.
- The app refuses to start with `AEGIS_ENVIRONMENT=production` on a
  SQLite `AEGIS_DATABASE_URL`. SQLite does not survive more than one
  running instance, and the held-call approval flow depends on durable,
  consistent database state across restarts and instances.

## [0.4.0]

### Added
- `examples/mcp-server/`: an MCP server whose `tools/call` is scored by
  `POST /v1/guard` before executing, implemented against the official MCP
  Python SDK (JSON-RPC 2.0 over stdio, pinned to `mcp>=2.0,<3`). MCP is
  becoming the default interop layer between agent hosts and tools;
  pointing a client at this server requires no application code changes.
  Verified both the guard-then-forward logic directly and a real JSON-RPC
  handshake over stdio against a live AegisAI instance.
- `examples/langchain/`: `guard_tool()` wraps any LangChain `BaseTool`,
  returning a real `StructuredTool` with the same name, description, and
  args schema, a drop-in replacement in an existing tool list. Blocked
  calls raise LangChain's own `ToolException` (caught via
  `handle_tool_error=True` so one block doesn't crash an agent run, while
  `on_tool_error` still fires for tracing). Verified all three verdicts
  (allow, hold, block) against a live instance through the standard
  `.run()` surface.

## [0.3.0]

### Added
- Per-key scoped policy: `ApiKey.policy_id` attaches a named rule set
  (`backend/aegis/seed/policies/<id>.yaml`) to each key instead of one
  global rule set for every caller. New keys default to `default`, the
  most restrictive baseline. Ships with a second `strict` policy so the
  mechanism has something real to prove: the same call scores differently
  depending on which key sent it.
- `GET /v1/policies` lists the available policy ids.
- API key lifecycle: `expires_in_days` at creation, `POST /v1/keys/rotate`
  (mint a replacement, revoke the old one, no gap in validity), and
  `POST /v1/keys/revoke` (immediate). Both require presenting the key
  itself, proof of possession, not a separate admin path.
- Per-agent identity: `context.agent_id` on `POST /v1/guard`, persisted on
  `ToolCall.agent_name` and kept independent of `ToolCall.api_key_id`, so
  one key fronting several agents doesn't collapse their audit trails into
  one identity.

### Fixed
- SQLite drops timezone info on datetime round-trip; API key expiry checks
  now normalize a naive `expires_at` back to UTC before comparing, rather
  than raising.

## [0.2.0]

### Added
- Public, hosted API: `POST /v1/guard` scores a proposed tool call through
  the rule, pattern, and judge layers and returns a verdict, without
  executing anything itself. This is the primary way to use AegisAI now:
  any agent, in any language, calls this endpoint over HTTP.
- `POST /v1/keys`: no-signup API key creation, rate limited per IP.
- Per-key rate limiting on `/v1/guard` (`slowapi`, in-process, no external
  service).
- `/docs` and `/redoc` with a filled-in request example, so the API is
  usable directly from Swagger UI's "Try it out".
- `scripts/demo.py`: a client of the public API over plain HTTP, no import
  of this repo's own package, proving the API works standalone.
- `examples/openai-function-calling/`: a plain OpenAI function-calling loop
  guarded by `POST /v1/guard`, plus a test that exercises the AegisAI side
  without needing an OpenAI key.
- Landing page redesign: a shield logo mark, an animated diagram of the
  intercept mechanism, a sticky nav, a real demo GIF and screenshot in the
  README.
- `CONTRIBUTING.md`.

### Changed
- README rewritten around the hosted API as the primary integration path.

## [0.1.0]

Initial release: the internal middleware. `AegisAI.guard()` intercepts a
tool call inside an agent's own process, scores it (static rules, an online
pattern classifier, an LLM judge), and resolves it to allow, hold, or block.
Includes the Next.js dashboard, the Docker Compose demo, and the Vercel and
Railway deployment paths.

# Contributing

AegisAI is small and the bar is simple: does it work, is it tested, does it
read clearly to someone who did not write it.

## Setup

```bash
git clone https://github.com/Navneet-Scaler/AegisAI.git
cd AegisAI
docker compose up --build
```

For backend or frontend only development, see the README's "How to run" section.

## Before opening a PR

```bash
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd frontend && npm run lint && npm run build
```

CI runs the same checks; a green run there is the bar, not a suggestion.

## Conventions

- Conventional commit messages: `feat:`, `fix:`, `chore:`, `docs:`.
- No en dashes or em dashes in code, comments, or docs. Use commas, colons,
  parentheses, or "to" for ranges.
- New behavior gets a test alongside it in the same PR, not a follow-up.
- If you touch `aegis/aegisai/`, the chokepoint that every tool call passes
  through, re-run `tests/test_chokepoint.py` specifically; it exists to catch
  exactly the kind of change that quietly reopens a bypass.

## Reporting a bug or proposing a feature

Open an issue. A clear repro (a curl command, a failing test, or steps
against `docker compose up`) is worth more than a long description of
what you think went wrong.

## Scope

Pull requests that add a dependency, change the scoring formula's weights,
or touch the fail-closed behaviour in `aegis/aegisai/core.py` should explain
why in the PR description; those are the parts of this project where a
quiet regression matters most.

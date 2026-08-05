"""Persistence models.

`ToolCall` is the single source of truth for whether a call has been decided
and whether it may execute. Pending approvals are rows here, not in-process
state, so a restart mid approval leaves the row recoverable instead of
vanishing, and the SSE stream can be derived purely from database state.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class Verdict(StrEnum):
    ALLOW = "allow"
    HOLD = "hold"
    BLOCK = "block"


class CallStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"


class AgentSession(SQLModel, table=True):
    id: str = Field(primary_key=True)
    agent_name: str = Field(default="demo-agent", index=True)
    user_request: str
    created_at: datetime = Field(default_factory=_now)


class ToolCall(SQLModel, table=True):
    id: str = Field(primary_key=True)
    session_id: str = Field(index=True)
    agent_name: str = Field(default="demo-agent", index=True)
    # The authenticating API key, kept separate from agent_name the same way
    # OAuth keeps a client ID separate from a subject claim: agent_name is
    # who the caller says is making the call, api_key_id is the credential
    # that was actually presented. Null for calls made through the internal
    # ReAct demo loop, which has no API key at all.
    api_key_id: str | None = Field(default=None, index=True)
    # Which policy actually scored this call, so a later dry run can compare
    # a proposed policy edit against the calls that were really scored
    # under it, not the whole call log regardless of which policy applied.
    policy_id: str = Field(default="default", index=True)
    tool_name: str = Field(index=True)
    arguments: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    step_index: int = 0

    # Scoring
    rule_score: float | None = None
    pattern_score: float | None = None
    judge_score: float | None = None
    composite_score: float | None = None
    matched_rules: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    judge_reasoning: str | None = None
    failure_reason: str | None = None
    # The exact feature vector the pattern layer scored, kept so a later
    # human decision trains on what was actually evaluated rather than a
    # recomputation that could have drifted since.
    pattern_features: list[float] | None = Field(default=None, sa_column=Column(JSON))

    # Decision
    verdict: Verdict = Field(default=Verdict.HOLD)
    status: CallStatus = Field(default=CallStatus.PENDING, index=True)
    forced_by_rule: bool = False
    decided_by: str | None = None
    decided_at: datetime | None = None
    executed: bool = False
    result: str | None = None

    created_at: datetime = Field(default_factory=_now, index=True)


class PolicyVersion(SQLModel, table=True):
    """A saved edit to a policy's rule set, versioned rather than
    overwritten in place: policy changes get the same rigor as code
    changes, a reviewable diff and a rollback path, not a silent
    in-place edit to the file every key scored against that policy relies
    on. Exactly one version per `policy_id` has `is_active=True` at a time;
    activating a new one deactivates whichever was active before, and
    rolling back is just activating an older version again.

    `policy_id` values that were never edited through this table have no
    rows here at all; `aegisai/policy_store.py` falls back to the YAML
    file under `seed/policies/<policy_id>.yaml` for those, so shipping a
    new policy file continues to work without a database write.
    """

    id: str = Field(primary_key=True)
    policy_id: str = Field(index=True)
    version: int
    rules: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    description: str = ""
    created_by: str = "dashboard"
    created_at: datetime = Field(default_factory=_now, index=True)
    is_active: bool = Field(default=False, index=True)


class ModelState(SQLModel, table=True):
    """Persisted weights for the online pattern classifier, keyed so there is
    always exactly one live row. Reset by /demo/reset back to the seeded
    baseline."""

    id: str = Field(default="pattern-model", primary_key=True)
    weights: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=_now)


class ApiKey(SQLModel, table=True):
    """A public API key for POST /v1/guard. Only the SHA-256 hash is stored;
    the raw key is shown to the caller exactly once, at creation, the same
    pattern Stripe and GitHub use for their tokens."""

    id: str = Field(primary_key=True)
    key_hash: str = Field(index=True, unique=True)
    owner_label: str = "anonymous"
    # Which rule set (backend/aegis/seed/policies/<policy_id>.yaml) this
    # key's calls are scored against. Defaults to the most restrictive
    # baseline, not the most permissive, consistent with this project's
    # fail-closed philosophy: a new key should have to be deliberately
    # given a looser policy, never inherit one by accident.
    policy_id: str = "default"
    created_at: datetime = Field(default_factory=_now)
    revoked_at: datetime | None = None
    expires_at: datetime | None = None
    request_count: int = 0

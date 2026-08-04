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


class PolicyRule(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    description: str
    enabled: bool = True
    definition: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)


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
    created_at: datetime = Field(default_factory=_now)
    revoked_at: datetime | None = None
    request_count: int = 0

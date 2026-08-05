"""Rule authoring: view, dry-run, save, and activate policy versions.

Reads are public, the same as the rest of this API's read surface. Writes
(saving a draft, activating a version) require the demo token: this is the
control plane, the same bar as approving a held call, since a bad policy
edit can quietly make every future call under it more permissive than it
should be.

Dry-run is deliberately not gated behind the token even though it accepts
proposed rules: it has no side effects, the same reason `/calls` is public.
Seeing a policy's blast radius should not require a credential; committing
to it should.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.aegisai import policy_store
from aegis.auth import require_demo_token
from aegis.db import get_session
from aegis.models import PolicyVersion

router = APIRouter(prefix="/v1/policies", tags=["policy"])


class RulesResponse(BaseModel):
    policy_id: str
    rules: list[dict]
    source: str = Field(description="'saved' if a version was ever activated, else 'seed'")


@router.get("/{policy_id}/rules", response_model=RulesResponse)
async def get_active_rules_route(
    policy_id: str, session: AsyncSession = Depends(get_session)
) -> RulesResponse:
    active_version = await policy_store.get_active_version(session, policy_id)
    if active_version is not None:
        return RulesResponse(policy_id=policy_id, rules=active_version.rules, source="saved")

    try:
        rules = await policy_store.get_active_rules(session, policy_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"No such policy: {exc}") from None
    return RulesResponse(policy_id=policy_id, rules=rules, source="seed")


class VersionSummary(BaseModel):
    id: str
    version: int
    description: str
    created_by: str
    created_at: str
    is_active: bool


def _to_summary(v: PolicyVersion) -> VersionSummary:
    return VersionSummary(
        id=v.id,
        version=v.version,
        description=v.description,
        created_by=v.created_by,
        created_at=v.created_at.isoformat(),
        is_active=v.is_active,
    )


@router.get("/{policy_id}/versions", response_model=list[VersionSummary])
async def list_versions_route(
    policy_id: str, session: AsyncSession = Depends(get_session)
) -> list[VersionSummary]:
    versions = await policy_store.list_versions(session, policy_id)
    return [_to_summary(v) for v in versions]


class DryRunRequest(BaseModel):
    rules: list[dict] = Field(description="The proposed rule set, same shape as any policy file.")


class DryRunCallOut(BaseModel):
    call_id: str
    tool_name: str
    actual_verdict_tier: str
    proposed_forced_verdict: str | None
    matched_rule_ids: list[str]
    changed: bool


class DryRunResponse(BaseModel):
    sample_size: int
    would_change: int
    newly_forced_hold: int
    newly_forced_block: int
    no_longer_forced: int
    results: list[DryRunCallOut]


@router.post(
    "/{policy_id}/dry-run",
    response_model=DryRunResponse,
    summary="Simulate a proposed policy against recent history",
    description=(
        "Re-evaluates the proposed rules against the most recent resolved calls that "
        "were actually scored under this policy, and reports which ones would have "
        "gotten a different forced verdict. The WAF 'count mode before block mode' "
        "pattern: see the blast radius before committing to it, not after."
    ),
)
async def dry_run_route(
    policy_id: str, payload: DryRunRequest, session: AsyncSession = Depends(get_session)
) -> DryRunResponse:
    try:
        summary = await policy_store.dry_run(
            session, proposed_rules=payload.rules, policy_id=policy_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    return DryRunResponse(
        sample_size=summary.sample_size,
        would_change=summary.would_change,
        newly_forced_hold=summary.newly_forced_hold,
        newly_forced_block=summary.newly_forced_block,
        no_longer_forced=summary.no_longer_forced,
        results=[
            DryRunCallOut(
                call_id=r.call_id,
                tool_name=r.tool_name,
                actual_verdict_tier=r.actual_verdict_tier,
                proposed_forced_verdict=r.proposed_forced_verdict,
                matched_rule_ids=r.matched_rule_ids,
                changed=r.changed,
            )
            for r in summary.results
        ],
    )


class SaveDraftRequest(BaseModel):
    rules: list[dict]
    description: str = ""


@router.post(
    "/{policy_id}/draft",
    response_model=VersionSummary,
    dependencies=[Depends(require_demo_token)],
    summary="Save a new policy version, without activating it",
)
async def save_draft_route(
    policy_id: str, payload: SaveDraftRequest, session: AsyncSession = Depends(get_session)
) -> VersionSummary:
    try:
        version = await policy_store.save_draft(
            session, policy_id=policy_id, rules=payload.rules, description=payload.description
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _to_summary(version)


@router.post(
    "/{policy_id}/versions/{version_id}/activate",
    response_model=VersionSummary,
    dependencies=[Depends(require_demo_token)],
    summary="Activate a policy version",
    description=(
        "Makes this version the one new calls under this policy are scored against. "
        "Activating an older version is how a rollback works, there is no separate "
        "rollback endpoint."
    ),
)
async def activate_version_route(
    policy_id: str, version_id: str, session: AsyncSession = Depends(get_session)
) -> VersionSummary:
    try:
        version = await policy_store.activate_version(
            session, policy_id=policy_id, version_id=version_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return _to_summary(version)

"""The public, hosted surface: POST /v1/guard and POST /v1/keys.

This is the whole pivot. AegisAI is not shipped as a library to import;
it is a service any agent, in any language, calls over HTTP before it
executes a tool. `/v1/guard` is the same rules -> pattern -> judge ->
composite pipeline used internally, exposed as a stateless scoring call
rather than one that blocks and executes on your behalf.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.aegisai.public import score_public_call
from aegis.aegisai.rules import list_policy_ids
from aegis.db import get_session
from aegis.keys import (
    check_creation_rate_limit,
    create_key,
    require_api_key,
    revoke_key,
    rotate_key,
)
from aegis.models import ApiKey
from aegis.rate_limit import limiter

router = APIRouter(prefix="/v1", tags=["v1"])


def _extract_bearer(authorization: str | None) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token."
        )
    return authorization.removeprefix("Bearer ").strip()


class CreateKeyRequest(BaseModel):
    owner_label: str = Field(
        default="anonymous",
        description="A free-text label to tell your keys apart later. Not verified.",
        examples=["my-support-agent"],
    )
    policy_id: str = Field(
        default="default",
        description="Which rule set this key's calls are scored against. Defaults to "
        "the most restrictive baseline. See GET /v1/policies for the available ids.",
        examples=["default"],
    )
    expires_in_days: int | None = Field(
        default=None,
        description="Optional. If set, the key stops working after this many days. "
        "Unset means it never expires on its own, revoke it instead when it's done.",
    )


class CreateKeyResponse(BaseModel):
    key: str = Field(description="The raw API key. Shown once, here, and never again.")
    key_id: str
    owner_label: str
    policy_id: str
    expires_at: str | None = None


def _key_response(row: ApiKey, raw_key: str) -> CreateKeyResponse:
    return CreateKeyResponse(
        key=raw_key,
        key_id=row.id,
        owner_label=row.owner_label,
        policy_id=row.policy_id,
        expires_at=row.expires_at.isoformat() if row.expires_at else None,
    )


@router.post(
    "/keys",
    response_model=CreateKeyResponse,
    summary="Mint a new API key",
    description=(
        "No signup, no email, no payment: a fresh key immediately, so the API can be "
        "tried in one request. Rate limited to 3 keys per IP per hour, in process, to "
        "blunt casual abuse of the frictionless path. The raw key is only ever shown "
        "in this response; only its hash is stored."
    ),
)
async def create_key_route(
    payload: CreateKeyRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CreateKeyResponse:
    client_ip = request.client.host if request.client else "unknown"
    check_creation_rate_limit(client_ip)

    if payload.policy_id not in (list_policy_ids() or ["default"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown policy_id {payload.policy_id!r}. See GET /v1/policies.",
        )

    row, raw_key = await create_key(
        session,
        owner_label=payload.owner_label,
        policy_id=payload.policy_id,
        expires_in_days=payload.expires_in_days,
    )
    return _key_response(row, raw_key)


@router.get(
    "/policies",
    summary="List available policy ids",
    description="Pass one of these as policy_id when minting a key with POST /v1/keys.",
)
async def list_policies_route() -> list[str]:
    return list_policy_ids() or ["default"]


@router.post(
    "/keys/rotate",
    response_model=CreateKeyResponse,
    summary="Rotate an API key",
    description=(
        "Mints a replacement key carrying the same owner_label and policy_id, then "
        "revokes the presented key. Requires the key itself as the bearer token, the "
        "same proof-of-possession bar as revoking one, there is no separate admin path."
    ),
)
async def rotate_key_route(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> CreateKeyResponse:
    raw_key = _extract_bearer(authorization)
    row, new_raw_key = await rotate_key(session, raw_key=raw_key)
    return _key_response(row, new_raw_key)


class RevokeKeyResponse(BaseModel):
    key_id: str
    revoked_at: str


@router.post(
    "/keys/revoke",
    response_model=RevokeKeyResponse,
    summary="Revoke an API key",
    description=(
        "Immediately invalidates the presented key. Requires the key itself as the "
        "bearer token: revoking is proof-of-possession, not an admin action against "
        "someone else's key."
    ),
)
async def revoke_key_route(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> RevokeKeyResponse:
    raw_key = _extract_bearer(authorization)
    row = await revoke_key(session, raw_key=raw_key)
    assert row.revoked_at is not None
    return RevokeKeyResponse(key_id=row.id, revoked_at=row.revoked_at.isoformat())


class GuardContext(BaseModel):
    user_request: str = Field(
        default="",
        description="What the user actually asked for. The judge layer checks the "
        "proposed call against this, which is what catches a call that only "
        "followed from something injected into a tool result, not the user.",
    )
    history: list[dict] = Field(
        default_factory=list,
        description="Prior conversation turns, in whatever shape your agent already "
        "has them. Free-form: AegisAI reads this as text, it does not require a "
        "specific schema.",
    )
    agent_id: str | None = Field(
        default=None,
        description="Which agent or deployment is making this call, if you run more "
        "than one under a single key (e.g. a support bot and a billing bot). Kept "
        "separate from the API key: the key is the credential, this is who used it. "
        "Defaults to the key's owner_label when omitted.",
        examples=["support-bot-prod"],
    )


class GuardRequest(BaseModel):
    tool: str = Field(
        description="The tool your agent is about to call.", examples=["delete_customer"]
    )
    args: dict = Field(
        default_factory=dict,
        description="The arguments it's about to call that tool with.",
        examples=[{"customer_id": "8842"}],
    )
    context: GuardContext = Field(default_factory=GuardContext)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tool": "delete_customer",
                    "args": {"customer_id": "8842"},
                    "context": {
                        "user_request": "clean up test accounts",
                        "history": [{"role": "user", "content": "clean up test accounts"}],
                        "agent_id": "support-bot-prod",
                    },
                }
            ]
        }
    }


class GuardLayers(BaseModel):
    rule: float
    pattern: float
    judge: float


class GuardResponse(BaseModel):
    verdict: str = Field(description="allow, hold, or block.")
    score: float = Field(description="The composite score, 0 to 1.")
    layers: GuardLayers = Field(description="The three sub-scores the composite was built from.")
    reasoning: str | None = Field(
        default=None, description="The judge layer's explanation, when it ran and had one."
    )
    call_id: str = Field(description="Reference this call in the audit trail.")


@router.post(
    "/guard",
    response_model=GuardResponse,
    summary="Score a proposed tool call",
    description=(
        "Runs the call through AegisAI's rule engine, online pattern model, and LLM "
        "judge, and returns a verdict: allow, hold, or block. This endpoint only "
        "scores, it does not execute anything, the tool is yours and stays yours. "
        "A 'hold' verdict means a human should review it before your agent proceeds; "
        "'block' means don't. Scored against the policy your key was minted with. "
        "Rate limited to 60 requests per minute per key."
    ),
)
@limiter.limit("60/minute")
async def guard_route(
    request: Request,
    payload: GuardRequest,
    session: AsyncSession = Depends(get_session),
    api_key: ApiKey = Depends(require_api_key),
) -> GuardResponse:
    call = await score_public_call(
        session=session,
        owner_label=api_key.owner_label,
        api_key_id=api_key.id,
        policy_id=api_key.policy_id,
        tool_name=payload.tool,
        arguments=payload.args,
        user_request=payload.context.user_request,
        history=payload.context.history,
        agent_name=payload.context.agent_id,
    )
    return GuardResponse(
        verdict=call.verdict.value,
        score=call.composite_score or 0.0,
        layers=GuardLayers(
            rule=call.rule_score or 0.0,
            pattern=call.pattern_score or 0.0,
            judge=call.judge_score or 0.0,
        ),
        reasoning=call.judge_reasoning,
        call_id=call.id,
    )

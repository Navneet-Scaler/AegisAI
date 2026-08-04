"""The public, hosted surface: POST /v1/guard and POST /v1/keys.

This is the whole pivot. AegisAI is not shipped as a library to import;
it is a service any agent, in any language, calls over HTTP before it
executes a tool. `/v1/guard` is the same rules -> pattern -> judge ->
composite pipeline used internally, exposed as a stateless scoring call
rather than one that blocks and executes on your behalf.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.aegisai.public import score_public_call
from aegis.db import get_session
from aegis.keys import check_creation_rate_limit, create_key, require_api_key
from aegis.models import ApiKey
from aegis.rate_limit import limiter

router = APIRouter(prefix="/v1", tags=["v1"])


class CreateKeyRequest(BaseModel):
    owner_label: str = Field(
        default="anonymous",
        description="A free-text label to tell your keys apart later. Not verified.",
        examples=["my-support-agent"],
    )


class CreateKeyResponse(BaseModel):
    key: str = Field(description="The raw API key. Shown once, here, and never again.")
    key_id: str
    owner_label: str


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

    row, raw_key = await create_key(session, owner_label=payload.owner_label)
    return CreateKeyResponse(key=raw_key, key_id=row.id, owner_label=row.owner_label)


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
        "'block' means don't. Rate limited to 60 requests per minute per key."
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
        tool_name=payload.tool,
        arguments=payload.args,
        user_request=payload.context.user_request,
        history=payload.context.history,
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

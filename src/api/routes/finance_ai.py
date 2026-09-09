"""Read-only finance analysis API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.rbac import Permission, require_permissions
from src.services.core.finance.agents import create_agent

router = APIRouter(prefix="/api/finance/ai", tags=["finance-ai"])


class AgentRequest(BaseModel):
    agent: str = Field(min_length=1, max_length=40)
    payload: dict[str, Any]


@router.post("/analyze", dependencies=[require_permissions(Permission.FINANCE_READ)])
async def analyze_finance(request: AgentRequest) -> dict[str, Any]:
    try:
        agent = create_agent(request.agent)
        result = agent.process(request.payload)
    except KeyError:
        raise HTTPException(status_code=400, detail="Unknown finance agent") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return {"agent": request.agent, "result": result}

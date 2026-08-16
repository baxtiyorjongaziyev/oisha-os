'''Finance AI API routes.

Provides endpoints to interact with registered finance agents.
''' 

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.api.rbac import Permission, require_permissions
from src.services.core.finance.agents import get_agent

router = APIRouter(tags=["finance-ai"])

class AgentRequest(BaseModel):
    """Payload sent to a finance AI agent.

    The ``agent`` field selects which registered agent to use.  ``payload``
    contains the free‑form data passed to the agent's ``process`` method.
    """

    agent: str
    payload: dict

@router.post(
    "/api/finance/ai",
    dependencies=[require_permissions(Permission.FINANCE_WRITE)],
)
async def invoke_finance_agent(request: AgentRequest):
    """Invoke a registered finance AI agent.

    Returns the agent's result or an error if the agent is unknown.
    """
    try:
        agent = get_agent(request.agent)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "unknown_agent",
                "message": f"Agent '{request.agent}' is not registered.",
            },
        )
    # In a real implementation this could be async; our placeholder agents are sync.
    result = agent.process(request.payload)
    return {"agent": request.agent, "result": result}

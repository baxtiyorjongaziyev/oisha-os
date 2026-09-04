"""Client Q&A — ask a free-text question about one client, answered from every
connected data source (AmoCRM, Telegram, Airtable, Instagram)."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.rbac import Permission, require_permissions
from src.api.routes.state import api_state

router = APIRouter(
    prefix="/api/client-qa",
    tags=["client-qa"],
    dependencies=[require_permissions(Permission.DASHBOARD_READ)],
)
logger = logging.getLogger(__name__)


class ClientQuestionRequest(BaseModel):
    question: str
    lead_id: Optional[int] = None
    name: str = ""
    phone: str = ""


@router.post("/ask")
async def ask_about_client(payload: ClientQuestionRequest):
    """Answer a question about a client using AmoCRM + Telegram + Airtable + Instagram data."""
    from src.services.core.brain.client_qa import ClientQAError, answer_client_question

    amocrm = api_state.amocrm_instance
    if not amocrm:
        return JSONResponse(status_code=503, content={"error": "amocrm_not_configured"})

    try:
        answer = await answer_client_question(
            payload.question,
            amocrm=amocrm,
            db=api_state.db_instance,
            tg_client=api_state.user_client,
            lead_id=payload.lead_id,
            name=payload.name,
            phone=payload.phone,
        )
    except ClientQAError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except Exception as exc:
        logger.exception("[CLIENT_QA] ask_about_client failed: %s", exc)
        return JSONResponse(status_code=500, content={"error": "internal_error"})

    return {"answer": answer}

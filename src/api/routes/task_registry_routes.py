"""HTTP API for the shared task registry (/api/tasks).

Auth: per-bot bearer token from ``TASK_REGISTRY_TOKENS`` env, formatted as
``oisha:<token>,amina:<token>,mrjon:<token>``. The bot identity comes from the
token, never from the request body. Unset env => 503 (fail closed).
"""
from __future__ import annotations

import hmac
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from src.services.core.task_registry import TaskRegistryError, get_registry

router = APIRouter(prefix="/api/tasks", tags=["task-registry"])


def _tokens() -> Dict[str, str]:
    raw = os.environ.get("TASK_REGISTRY_TOKENS", "")
    pairs = (p.split(":", 1) for p in raw.split(",") if ":" in p)
    return {bot.strip().lower(): tok.strip() for bot, tok in pairs if tok.strip()}


def current_bot(authorization: str = Header(default="")) -> str:
    tokens = _tokens()
    if not tokens:
        raise HTTPException(status_code=503, detail="task_registry_not_configured")
    supplied = authorization.removeprefix("Bearer ").strip()
    for bot, token in tokens.items():
        if supplied and hmac.compare_digest(supplied, token):
            return bot
    raise HTTPException(status_code=401, detail="invalid_token")


class CreateTask(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    owner: str
    domain: str = "general"
    payload: Dict[str, Any] = Field(default_factory=dict)
    due_at: Optional[str] = None
    idempotency_key: Optional[str] = Field(default=None, max_length=200)


class CompleteTask(BaseModel):
    evidence: Dict[str, Any]


class FailTask(BaseModel):
    error: str = Field(min_length=1)


class ReassignTask(BaseModel):
    owner: str


async def _run(coro):
    try:
        return await coro
    except TaskRegistryError as exc:
        code = 404 if str(exc) == "task_not_found" else 409
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.post("")
async def create_task(body: CreateTask, bot: str = Depends(current_bot)):
    return await _run(get_registry().create(created_by=bot, **body.model_dump()))


@router.get("")
async def list_tasks(
    owner: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    bot: str = Depends(current_bot),
):
    return await _run(get_registry().list(owner=owner, status=status, limit=limit))


@router.get("/{task_id}")
async def get_task(task_id: str, bot: str = Depends(current_bot)):
    task = await get_registry().get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    return task


@router.post("/{task_id}/claim")
async def claim_task(task_id: str, bot: str = Depends(current_bot)):
    return await _run(get_registry().claim(task_id, bot))


@router.post("/{task_id}/complete")
async def complete_task(task_id: str, body: CompleteTask, bot: str = Depends(current_bot)):
    return await _run(get_registry().complete(task_id, bot, body.evidence))


@router.post("/{task_id}/fail")
async def fail_task(task_id: str, body: FailTask, bot: str = Depends(current_bot)):
    return await _run(get_registry().fail(task_id, bot, body.error))


@router.post("/{task_id}/reassign")
async def reassign_task(task_id: str, body: ReassignTask, bot: str = Depends(current_bot)):
    return await _run(get_registry().reassign(task_id, bot, body.owner))

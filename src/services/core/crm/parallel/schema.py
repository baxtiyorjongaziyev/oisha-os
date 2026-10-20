"""Validated amoCRM mirror and edit contracts."""
from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RemoteLead(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: int = Field(gt=0)
    name: str
    updated_at: int = Field(ge=0)
    pipeline_id: int = Field(gt=0)
    status_id: int = Field(gt=0)
    responsible_user_id: int = Field(gt=0)
    price: int | None = Field(default=None, ge=0)
    is_deleted: bool = False


class LeadPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str | None = Field(default=None, min_length=1, max_length=256)
    status_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("At least one non-null change is required")
        if self.name is not None and not self.name.strip():
            raise ValueError("Name cannot be blank")
        return self


class EditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    patch: LeadPatch


def revision(lead: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(lead, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def baseline(lead: dict[str, Any]) -> dict[str, Any]:
    return {key: lead.get(key) for key in (
        "name", "status_id", "pipeline_id", "responsible_user_id", "updated_at"
    )}


def matches(lead: dict, patch: dict) -> bool:
    return all(lead.get(key) == value for key, value in patch.items())

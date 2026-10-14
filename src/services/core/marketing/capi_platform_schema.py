"""Validated server-to-server CAPI intake; raw contact data is never persisted."""
from __future__ import annotations

import time
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from src.services.core.marketing.meta_capi import hash_email, hash_phone


class Conversion(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    source: Literal["website", "crm"]
    event_name: Literal["PageView", "ViewContent", "Lead", "QualifiedLead", "Purchase"]
    event_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    event_time: int
    event_source_url: str | None = Field(default=None, max_length=2048)
    client_user_agent: str | None = Field(default=None, max_length=1024)
    leadgen_id: str | None = Field(default=None, pattern=r"^[0-9]+$", max_length=64)
    phone: str = Field(default="", max_length=64, repr=False)
    email: str = Field(default="", max_length=254, repr=False)
    fbp: str | None = Field(default=None, max_length=256, pattern=r"^fb\.\d\.\d{10,13}\.\d+$")
    fbc: str | None = Field(default=None, max_length=256, pattern=r"^fb\.\d\.\d{10,13}\.[\w-]+$")
    value: float | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    consent: StrictBool

    @model_validator(mode="after")
    def check_conversion(self):
        now = int(time.time())
        if not now - 7 * 86400 <= self.event_time <= now:
            raise ValueError("event_time must be within the last seven days")
        if not self.consent:
            raise ValueError("consent is required")
        if self.source == "website":
            url = urlsplit(self.event_source_url or "")
            if url.scheme != "https" or not url.hostname or url.username or url.password:
                raise ValueError("website requires an HTTPS event_source_url")
            if url.query or url.fragment:
                raise ValueError("event_source_url must omit query and fragment")
            if not self.client_user_agent:
                raise ValueError("website requires client_user_agent")
            if not (hash_phone(self.phone) or hash_email(self.email) or self.fbp or self.fbc):
                raise ValueError("website requires a matching identifier")
        elif not self.leadgen_id:
            raise ValueError("crm requires leadgen_id")
        elif self.event_id != f"crm-{self.leadgen_id}-{self.event_name}":
            raise ValueError("CRM event_id must match the existing CRM integration")
        if self.source == "crm" and self.event_name not in {"Lead", "QualifiedLead", "Purchase"}:
            raise ValueError("unsupported CRM event")
        if self.event_name == "Purchase" and (self.value is None or self.currency is None):
            raise ValueError("Purchase requires positive value and currency")
        return self

    def meta_event(self) -> dict:
        user = {}
        for key, value in (("ph", hash_phone(self.phone)), ("em", hash_email(self.email))):
            if value:
                user[key] = [value]
        event = {"event_name": self.event_name, "event_id": self.event_id,
                 "event_time": self.event_time, "user_data": user}
        if self.source == "website":
            event.update(action_source="website", event_source_url=self.event_source_url)
            user["client_user_agent"] = self.client_user_agent
            for key in ("fbp", "fbc"):
                if getattr(self, key):
                    user[key] = getattr(self, key)
        else:
            user["lead_id"] = self.leadgen_id
            event.update(action_source="system_generated",
                         custom_data={"event_source": "crm", "lead_event_source": "Oisha-OS"})
        if self.event_name == "Purchase":
            event.setdefault("custom_data", {}).update(value=self.value, currency=self.currency)
        return event

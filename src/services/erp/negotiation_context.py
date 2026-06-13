from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from src.services.erp.context_guard import evaluate_context_access
from src.services.erp.identity_resolver import IdentityProfile


@dataclass(frozen=True)
class NegotiationContext:
    client_id: str
    lead_id: int
    chat_id: int
    verified_identity: dict[str, Any]
    identity_confidence: float
    telegram_messages: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    crm_history: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    approved_services: tuple[str, ...] = field(default_factory=tuple)
    approved_prices: dict[str, dict[str, float]] = field(default_factory=dict)
    commitments: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "lead_id": self.lead_id,
            "chat_id": self.chat_id,
            "verified_identity": dict(self.verified_identity),
            "identity_confidence": self.identity_confidence,
            "telegram_messages": [dict(item) for item in self.telegram_messages],
            "crm_history": [dict(item) for item in self.crm_history],
            "approved_services": list(self.approved_services),
            "approved_prices": {
                key: dict(value) for key, value in self.approved_prices.items()
            },
            "commitments": [dict(item) for item in self.commitments],
        }


class NegotiationContextBuilder:
    """Build a fail-closed client context without cross-client data leakage."""

    def build(
        self,
        *,
        client_id: str,
        lead_id: int,
        chat_id: int,
        reference_identity: IdentityProfile,
        context_identity: IdentityProfile,
        classification: str,
        context_kind: str,
        membership_verified: bool = False,
        telegram_messages: Iterable[dict[str, Any]] = (),
        crm_history: Iterable[dict[str, Any]] = (),
        approved_services: Iterable[str] = (),
        approved_prices: dict[str, dict[str, float]] | None = None,
        commitments: Iterable[dict[str, Any]] = (),
    ) -> NegotiationContext:
        decision = evaluate_context_access(
            reference_identity=reference_identity,
            context_identity=context_identity,
            context_kind=context_kind,
            classification=classification,
            membership_verified=membership_verified,
        )
        if not decision.allowed:
            raise ValueError(decision.reason)
        if not str(client_id or "").strip():
            raise ValueError("client_id_required")
        if int(lead_id or 0) <= 0:
            raise ValueError("lead_id_required")
        if int(chat_id or 0) == 0:
            raise ValueError("chat_id_required")

        return NegotiationContext(
            client_id=str(client_id),
            lead_id=int(lead_id),
            chat_id=int(chat_id),
            verified_identity=asdict(context_identity),
            identity_confidence=decision.resolution.confidence,
            telegram_messages=tuple(
                dict(item)
                for item in telegram_messages
                if str(item.get("client_id") or "") == str(client_id)
            ),
            crm_history=tuple(
                dict(item)
                for item in crm_history
                if str(item.get("client_id") or "") == str(client_id)
                and int(item.get("lead_id") or 0) == int(lead_id)
            ),
            approved_services=tuple(
                str(item).strip()
                for item in approved_services
                if str(item).strip()
            ),
            approved_prices={
                str(key): dict(value)
                for key, value in (approved_prices or {}).items()
            },
            commitments=tuple(
                dict(item)
                for item in commitments
                if str(item.get("client_id") or client_id) == str(client_id)
            ),
        )

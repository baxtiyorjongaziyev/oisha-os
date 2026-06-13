from __future__ import annotations

from dataclasses import dataclass

from src.services.erp.identity_resolver import (
    IdentityProfile,
    IdentityResolution,
    resolve_identity,
)


NON_CUSTOMER_CLASSIFICATIONS = frozenset(
    {
        "personal",
        "shaxsiy",
        "family",
        "oila",
        "team",
        "jamoa",
        "hamkor/jamoa",
        "candidate",
        "kandidat",
    }
)


@dataclass(frozen=True)
class ContextAccessDecision:
    allowed: bool
    reason: str
    resolution: IdentityResolution
    classification: str
    context_kind: str


def normalize_classification(value: str) -> str:
    return str(value or "unknown").strip().casefold()


def evaluate_context_access(
    *,
    reference_identity: IdentityProfile,
    context_identity: IdentityProfile,
    context_kind: str,
    classification: str = "client",
    membership_verified: bool = False,
) -> ContextAccessDecision:
    """Decide whether context may be used for a customer action."""
    normalized_classification = normalize_classification(classification)
    normalized_kind = str(context_kind or "unknown").strip().casefold()
    resolution = resolve_identity(reference_identity, context_identity)

    if normalized_classification in NON_CUSTOMER_CLASSIFICATIONS:
        return ContextAccessDecision(
            allowed=False,
            reason="non_customer_context",
            resolution=resolution,
            classification=normalized_classification,
            context_kind=normalized_kind,
        )
    if normalized_kind == "group" and not membership_verified:
        return ContextAccessDecision(
            allowed=False,
            reason="group_membership_unverified",
            resolution=resolution,
            classification=normalized_classification,
            context_kind=normalized_kind,
        )
    if "conflict" in resolution.strongest_evidence:
        return ContextAccessDecision(
            allowed=False,
            reason="identity_conflict",
            resolution=resolution,
            classification=normalized_classification,
            context_kind=normalized_kind,
        )
    if not resolution.verified:
        return ContextAccessDecision(
            allowed=False,
            reason="identity_confidence_too_low",
            resolution=resolution,
            classification=normalized_classification,
            context_kind=normalized_kind,
        )
    return ContextAccessDecision(
        allowed=True,
        reason="verified_identity_context",
        resolution=resolution,
        classification=normalized_classification,
        context_kind=normalized_kind,
    )

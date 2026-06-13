from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional


CLIENT_ACTION_THRESHOLD = 0.90

PHONE_EXACT = 1.00
TELEGRAM_USER_ID_EXACT = 1.00
AMO_CONTACT_LINK = 0.98
USERNAME_EXACT = 0.92
NAME_AND_COMPANY = 0.75
NAME_ONLY = 0.40
HONORIFIC_ONLY = 0.00

HONORIFICS = frozenset(
    {
        "aka",
        "opa",
        "ustoz",
        "janob",
        "xon",
        "jon",
        "bro",
    }
)


@dataclass(frozen=True)
class IdentityProfile:
    phone: str = ""
    telegram_user_id: Optional[int] = None
    amo_contact_id: Optional[int] = None
    username: str = ""
    name: str = ""
    company: str = ""


@dataclass(frozen=True)
class IdentityEvidence:
    evidence_type: str
    score: float
    value: str


@dataclass(frozen=True)
class IdentityResolution:
    confidence: float
    verified: bool
    strongest_evidence: str
    evidence: tuple[IdentityEvidence, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 9:
        digits = "998" + digits
    return digits if len(digits) >= 9 else ""


def normalize_username(value: str) -> str:
    return str(value or "").strip().lstrip("@").casefold()


def normalize_name(value: str) -> str:
    tokens = re.findall(r"[\w'-]+", str(value or "").casefold())
    meaningful = [token for token in tokens if token not in HONORIFICS]
    return " ".join(meaningful).strip()


def _same_nonempty(left: object, right: object) -> bool:
    return left not in (None, "") and right not in (None, "") and left == right


def _strong_conflicts(
    reference: IdentityProfile,
    candidate: IdentityProfile,
) -> list[str]:
    conflicts: list[str] = []
    ref_phone = normalize_phone(reference.phone)
    candidate_phone = normalize_phone(candidate.phone)
    ref_username = normalize_username(reference.username)
    candidate_username = normalize_username(candidate.username)

    pairs = (
        ("phone", ref_phone, candidate_phone),
        ("telegram_user_id", reference.telegram_user_id, candidate.telegram_user_id),
        ("amo_contact_id", reference.amo_contact_id, candidate.amo_contact_id),
        ("username", ref_username, candidate_username),
    )
    for label, left, right in pairs:
        if left not in (None, "") and right not in (None, "") and left != right:
            conflicts.append(f"{label}_conflict")
    return conflicts


def _best_evidence(evidence: Iterable[IdentityEvidence]) -> IdentityEvidence:
    return max(
        evidence,
        key=lambda item: item.score,
        default=IdentityEvidence("none", 0.0, ""),
    )


def resolve_identity(
    reference: IdentityProfile,
    candidate: IdentityProfile,
) -> IdentityResolution:
    """Resolve two identities conservatively.

    Strong identifier conflicts always win over weaker name similarities.
    Multiple weak fields do not get promoted into client-action confidence.
    """
    conflicts = _strong_conflicts(reference, candidate)
    if conflicts:
        return IdentityResolution(
            confidence=0.0,
            verified=False,
            strongest_evidence="conflict",
            reasons=tuple(conflicts),
        )

    evidence: list[IdentityEvidence] = []
    ref_phone = normalize_phone(reference.phone)
    candidate_phone = normalize_phone(candidate.phone)
    ref_username = normalize_username(reference.username)
    candidate_username = normalize_username(candidate.username)
    ref_name = normalize_name(reference.name)
    candidate_name = normalize_name(candidate.name)
    ref_company = normalize_name(reference.company)
    candidate_company = normalize_name(candidate.company)

    if _same_nonempty(ref_phone, candidate_phone):
        evidence.append(IdentityEvidence("phone_exact", PHONE_EXACT, ref_phone))
    if _same_nonempty(reference.telegram_user_id, candidate.telegram_user_id):
        evidence.append(
            IdentityEvidence(
                "telegram_user_id_exact",
                TELEGRAM_USER_ID_EXACT,
                str(reference.telegram_user_id),
            )
        )
    if _same_nonempty(reference.amo_contact_id, candidate.amo_contact_id):
        evidence.append(
            IdentityEvidence(
                "amo_contact_link",
                AMO_CONTACT_LINK,
                str(reference.amo_contact_id),
            )
        )
    if _same_nonempty(ref_username, candidate_username):
        evidence.append(
            IdentityEvidence("username_exact", USERNAME_EXACT, ref_username)
        )
    if _same_nonempty(ref_name, candidate_name):
        if _same_nonempty(ref_company, candidate_company):
            evidence.append(
                IdentityEvidence(
                    "name_and_company",
                    NAME_AND_COMPANY,
                    f"{ref_name}|{ref_company}",
                )
            )
        else:
            evidence.append(IdentityEvidence("name_only", NAME_ONLY, ref_name))

    best = _best_evidence(evidence)
    return IdentityResolution(
        confidence=best.score,
        verified=best.score >= CLIENT_ACTION_THRESHOLD,
        strongest_evidence=best.evidence_type,
        evidence=tuple(evidence),
        reasons=() if evidence else ("no_matching_identity_evidence",),
    )

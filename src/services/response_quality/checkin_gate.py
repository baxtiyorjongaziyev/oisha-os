"""Deterministic boundary for proactive staff messages."""
import html
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    reasons: tuple[str, ...]


def evaluate(text: str) -> Verdict:
    """Reject malformed or repetitive proactive prose before delivery."""
    clean = html.unescape(text or "").strip()
    reasons = []
    if not 20 <= len(clean) <= 700:
        reasons.append("length")
    if any(marker in clean.lower() for marker in ("```", "<skill=", "# mening xabarim", "no tool call", "gateway message origin")):
        reasons.append("internal_format")
    sentences = [re.sub(r"\W+", " ", s.lower()).strip() for s in re.split(r"[.!?\n]+", clean)]
    sentences = [s for s in sentences if len(s) >= 15]
    if len(sentences) != len(set(sentences)):
        reasons.append("repeated_sentence")
    words = re.findall(r"\w+", clean.lower())
    windows = [tuple(words[i:i + 8]) for i in range(max(0, len(words) - 7))]
    if len(windows) != len(set(windows)):
        reasons.append("repeated_phrase")
    if re.search(r"(?i)(qo.ng.iroq|savol)\s*:\s*[\"“]|javob\s*:\s*[\"“]", clean):
        reasons.append("unverified_dialogue")
    if re.search(r"(?i)\b(bonus|chegirma|imtiyoz)\b|rahbariyat bilan kelish", clean):
        reasons.append("unapproved_offer")
    return Verdict(not reasons, tuple(reasons))

"""Hermes Harness Loop Engine for Oisha-OS.

Implements Invariant Verification, Self-Healing Refinement Loops, Circuit Breaker,
and Telemetry for Hermes Agent in Jon Branding Agency operations.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("HermesHarness")

# AI Slop and robotic bot indicators that must never appear in human-like replies
_ROBOTIC_AI_PATTERNS = [
    r"sun['’`]?iy intellekt",
    r"ai (?:yordamchi|model|assistent)",
    r"til modeli(?:man)?",
    r"as an ai",
    r"albatta,? men sizga yordam berishdan xursandman",
    r"sizga yana qanday yordam bera olaman\??",
    r"har qanday savolingiz bo['’`]?lsa",
    r"men faqat virtual",
    r"dasturlanganman",
]

# Patterns for fake price claims or unrealistic absolute promises
_HALLUCINATION_PATTERNS = [
    r"\$\s*\d{1,3}\b(?!\s*(?:k|ming|million))",  # Tiny unrealistic dollar amounts like $10, $50
    r"\b100%\s*(?:kafolatli\s+natija|daromad|savdo\s+oshishi)\b",
    r"\bhech\s+qanday\s+xavf\s+yo['’`]?q\b",
]


@dataclass
class InvariantResult:
    """Result of an invariant check."""

    is_valid: bool
    violations: List[str] = field(default_factory=list)
    critic_prompt: Optional[str] = None


@dataclass
class HarnessTelemetry:
    """Telemetry counters for Hermes Harness executions."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    refinement_turns: int = 0
    circuit_breaker_trips: int = 0
    total_latency_seconds: float = 0.0

    def record_success(self, latency: float, was_refined: bool = False) -> None:
        self.total_requests += 1
        self.successful_requests += 1
        self.total_latency_seconds += latency
        if was_refined:
            self.refinement_turns += 1

    def record_failure(self, latency: float) -> None:
        self.total_requests += 1
        self.failed_requests += 1
        self.total_latency_seconds += latency

    def as_dict(self) -> Dict[str, Any]:
        avg_lat = (
            round(self.total_latency_seconds / self.total_requests, 2)
            if self.total_requests > 0
            else 0.0
        )
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "refinement_turns": self.refinement_turns,
            "circuit_breaker_trips": self.circuit_breaker_trips,
            "avg_latency_s": avg_lat,
        }


class HermesCircuitBreaker:
    """Protects the application from cascading freezes if Hermes hangs or fails repeatedly."""

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.consecutive_failures = 0
        self.last_failure_time: float = 0.0
        self.state: str = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def is_available(self) -> bool:
        """Check if circuit allows calls."""
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info("[HERMES-CIRCUIT] State transitioning from OPEN to HALF_OPEN")
                return True
            return False
        return True  # HALF_OPEN allows a single probe attempt

    def record_success(self) -> None:
        """Record successful execution."""
        if self.state in ("OPEN", "HALF_OPEN"):
            logger.info("[HERMES-CIRCUIT] Circuit successfully recovered to CLOSED")
        self.consecutive_failures = 0
        self.state = "CLOSED"

    def record_failure(self) -> None:
        """Record execution failure."""
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        if self.consecutive_failures >= self.failure_threshold:
            if self.state != "OPEN":
                logger.warning(
                    "[HERMES-CIRCUIT] Failure threshold (%d) reached. Circuit tripped to OPEN",
                    self.failure_threshold,
                )
            self.state = "OPEN"


class HermesInvariantEvaluator:
    """Evaluates candidate response text against Oisha-OS invariants."""

    @staticmethod
    def evaluate(
        text: str,
        destination: str = "general",
    ) -> InvariantResult:
        """Check text against Invariants (Zero Hallucination, Anti-Slop, Formatting)."""
        violations: List[str] = []
        clean = (text or "").strip()

        if not clean:
            return InvariantResult(False, ["Javob bo'sh qaytdi"], "Javob matni bo'sh bo'lmasligi kerak.")

        from src.services.response_quality.checkin_gate import evaluate
        quality = evaluate(clean)
        for reason in quality.reasons:
            if reason in {"repeated_sentence", "repeated_phrase", "internal_format"}:
                violations.append(reason)

        # Invariant 1: Anti-Slop / Robotic disclaimers
        for pattern in _ROBOTIC_AI_PATTERNS:
            if re.search(pattern, clean, re.IGNORECASE):
                violations.append("AI / robot yordamchi iborasi ishlatildi")
                break

        # Invariant 2: Zero Hallucination / Absurd guarantees
        for pattern in _HALLUCINATION_PATTERNS:
            if re.search(pattern, clean, re.IGNORECASE):
                violations.append("Asossiz kafolat yoki uydirma narx aniqlandi")
                break

        # Invariant 3: Destination formatting rules
        if destination in ("telegram_dm", "staff_copilot"):
            if "```" in clean and "kod" not in clean.lower():
                violations.append("Telegram DM uchun noo'rin kod bloklari (```) ishlatildi")
            if len(clean) > 1800:
                violations.append("Telegram DM uchun xabar keraksiz uzun (>1800 belgi)")

        if not violations:
            return InvariantResult(is_valid=True)

        critic = (
            "Eslatma (Oisha Harness Loop):\n"
            "Oldingi javobingizda quyidagi nomuvofiqliklar aniqlandi:\n"
            + "\n".join(f"- {v}" for v in violations)
            + "\nIltimos, ushbu xatolarni to'g'irlab, insoniy, samimiy va lo'nda qilib qayta yozing."
        )
        return InvariantResult(is_valid=False, violations=violations, critic_prompt=critic)

    @staticmethod
    def sanitize(text: str) -> str:
        """Clean minor filler slop as post-processing fallback."""
        res = text.strip()
        for pattern in _ROBOTIC_AI_PATTERNS:
            res = re.sub(pattern, "", res, flags=re.IGNORECASE)
        # Clean double spaces or trailing filler lines
        res = re.sub(r"\n{3,}", "\n\n", res)
        return res.strip()


class HermesHarnessLoop:
    """Executes the autonomous Harness Loop for Hermes Agent."""

    def __init__(
        self,
        circuit_breaker: Optional[HermesCircuitBreaker] = None,
        max_refinements: int = 2,
    ):
        self.circuit_breaker = circuit_breaker or HermesCircuitBreaker()
        self.evaluator = HermesInvariantEvaluator()
        self.telemetry = HarnessTelemetry()
        self.max_refinements = max_refinements

    async def execute_loop(
        self,
        generate_fn: Callable[[str, Optional[str]], Awaitable[Optional[str]]],
        prompt: str,
        system_instruction: Optional[str] = None,
        destination: str = "general",
    ) -> Optional[str]:
        """Run candidate generation through invariant check and self-healing loop."""
        if not self.circuit_breaker.is_available():
            logger.warning("[HERMES-HARNESS] Circuit breaker is OPEN. Fast-failing.")
            self.telemetry.circuit_breaker_trips += 1
            return None

        t0 = time.time()
        current_prompt = prompt
        was_refined = False

        for turn in range(self.max_refinements + 1):
            try:
                candidate = await generate_fn(current_prompt, system_instruction)
            except Exception as exc:
                logger.error("[HERMES-HARNESS] Generation turn %d error: %s", turn, exc)
                self.circuit_breaker.record_failure()
                self.telemetry.record_failure(time.time() - t0)
                return None

            if not candidate:
                self.circuit_breaker.record_failure()
                self.telemetry.record_failure(time.time() - t0)
                return None

            eval_res = self.evaluator.evaluate(candidate, destination=destination)
            if eval_res.is_valid:
                self.circuit_breaker.record_success()
                self.telemetry.record_success(time.time() - t0, was_refined=was_refined)
                return candidate.strip()

            # Self-healing iteration
            logger.info(
                "[HERMES-HARNESS] Turn %d invariants failed: %s. Initiating self-healing.",
                turn,
                eval_res.violations,
            )
            was_refined = True
            current_prompt = f"{prompt}\n\n{eval_res.critic_prompt}"

        # Refinements exhausted: only a sanitized text that now passes every
        # invariant may leave the harness. Otherwise fail closed (no reply).
        sanitized = self.evaluator.sanitize(candidate)
        final = self.evaluator.evaluate(sanitized, destination=destination)
        if not final.is_valid:
            logger.warning(
                "[HERMES-HARNESS] Refinements exhausted, still invalid: %s. Dropping reply.",
                final.violations,
            )
            self.telemetry.record_failure(time.time() - t0)
            return None
        self.circuit_breaker.record_success()
        self.telemetry.record_success(time.time() - t0, was_refined=True)
        return sanitized


_GLOBAL_HARNESS: Optional[HermesHarnessLoop] = None


def get_hermes_harness() -> HermesHarnessLoop:
    """Get singleton HermesHarnessLoop instance."""
    global _GLOBAL_HARNESS
    if _GLOBAL_HARNESS is None:
        _GLOBAL_HARNESS = HermesHarnessLoop()
    return _GLOBAL_HARNESS

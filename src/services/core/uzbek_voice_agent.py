"""Uzbek Entrepreneurs Voice Agent - Vapi.ai integration for auto-calling."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import httpx

from src.database_pool import db_pool
from src.services.core.hisobchi_schema import ensure_hisobchi_db

logger = logging.getLogger(__name__)


@dataclass
class VapiCallConfig:
    api_key: str
    phone_number_id: str
    assistant_id: str
    voice_url: str  # URL to pre-recorded voice message


@dataclass
class CallResult:
    call_id: str
    status: str
    pressed_digit: Optional[str]
    duration_seconds: int
    transcription: Optional[str]


class UzbekVoiceAgent:
    """Voice Agent for auto-calling Uzbek entrepreneurs."""

    def __init__(self, config: VapiCallConfig, db=None):
        self.config = config
        self._db = ensure_hisobchi_db(db if db is not None else db_pool)
        self._client = httpx.AsyncClient(
            base_url="https://api.vapi.ai",
            headers={"Authorization": f"Bearer {config.api_key}"},
            timeout=30.0,
        )

    async def initiate_call(
        self,
        entrepreneur_id: int,
        phone: str,
        name: str,
    ) -> Optional[CallResult]:
        """Initiate a Vapi.ai call to an entrepreneur."""
        try:
            logger.info(
                "[VOICE_AGENT] Initiating call to %s (%s) for entrepreneur #%s",
                name,
                phone,
                entrepreneur_id,
            )

            # Create Vapi call
            response = await self._client.post(
                "/call",
                json={
                    "assistantId": self.config.assistant_id,
                    "phoneNumberId": self.config.phone_number_id,
                    "customer": {
                        "number": phone,
                        "name": name,
                    },
                    "assistantOverrides": {
                        "firstMessage": f"Assalomu alaykum {name}, men Jon Branding agentligidan qo'ng'iroq qilyapman.",
                        "variableValues": {
                            "entrepreneur_name": name,
                            "entrepreneur_id": str(entrepreneur_id),
                        },
                    },
                },
            )

            if response.status_code != 200:
                logger.error(
                    "[VOICE_AGENT] Vapi call failed: %s", response.text
                )
                return None

            call_data = response.json()
            call_id = call_data.get("id")

            logger.info("[VOICE_AGENT] Call initiated: %s", call_id)

            # Wait for call completion (polling)
            result = await self._wait_for_call_completion(call_id)

            # Log call result
            await self._log_call_result(
                entrepreneur_id=entrepreneur_id,
                call_id=call_id,
                result=result,
            )

            # Update entrepreneur status
            await self._update_entrepreneur_status(
                entrepreneur_id=entrepreneur_id,
                call_result=result,
            )

            return result

        except Exception as e:
            logger.error("[VOICE_AGENT] Call initiation failed: %s", e)
            return None

    async def _wait_for_call_completion(
        self, call_id: str, max_wait_seconds: int = 120
    ) -> CallResult:
        """Poll Vapi API for call completion."""
        for _ in range(max_wait_seconds // 2):
            await asyncio.sleep(2)

            try:
                response = await self._client.get(f"/call/{call_id}")
                if response.status_code != 200:
                    continue

                call_data = response.json()
                status = call_data.get("status")

                if status in ["completed", "failed", "ended"]:
                    analysis = call_data.get("analysis", {})
                    return CallResult(
                        call_id=call_id,
                        status=status,
                        pressed_digit=analysis.get("pressedDigit"),
                        duration_seconds=call_data.get("endedAt", 0) - call_data.get("startedAt", 0),
                        transcription=analysis.get("transcript"),
                    )

            except Exception as e:
                logger.warning("[VOICE_AGENT] Polling error: %s", e)
                continue

        # Timeout fallback
        return CallResult(
            call_id=call_id,
            status="timeout",
            pressed_digit=None,
            duration_seconds=0,
            transcription=None,
        )

    async def _log_call_result(
        self,
        entrepreneur_id: int,
        call_id: str,
        result: CallResult,
    ) -> None:
        """Log call result to database."""
        try:
            await self._db.execute(
                """
                INSERT INTO entrepreneur_call_logs
                (entrepreneur_id, call_date, call_duration_seconds, call_result,
                 pressed_digit, transferred_to_operator, vapi_call_id, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    entrepreneur_id,
                    datetime.now().isoformat(),
                    result.duration_seconds,
                    result.status,
                    result.pressed_digit,
                    1 if result.pressed_digit == "1" else 0,
                    call_id,
                    result.transcription,
                ],
            )
            await self._db.commit()
            logger.info(
                "[VOICE_AGENT] Call logged: #%s → %s (digit: %s)",
                entrepreneur_id,
                result.status,
                result.pressed_digit,
            )

        except Exception as e:
            logger.error("[VOICE_AGENT] Failed to log call: %s", e)

    async def _update_entrepreneur_status(
        self,
        entrepreneur_id: int,
        call_result: CallResult,
    ) -> None:
        """Update entrepreneur call status in database."""
        try:
            if call_result.pressed_digit == "1":
                new_status = "interested"
            elif call_result.pressed_digit == "2":
                new_status = "callback"
            elif call_result.status in ["failed", "disconnected"]:
                new_status = "disconnected"
            else:
                new_status = "called"

            await self._db.execute(
                """
                UPDATE uzbek_entrepreneurs
                SET call_status = ?,
                    call_attempts = call_attempts + 1,
                    last_call_date = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                [new_status, entrepreneur_id],
            )
            await self._db.commit()
            logger.info(
                "[VOICE_AGENT] Entrepreneur #%s status updated to: %s",
                entrepreneur_id,
                new_status,
            )

        except Exception as e:
            logger.error("[VOICE_AGENT] Failed to update status: %s", e)

    async def get_pending_calls(self, limit: int = 10) -> list[dict]:
        """Get list of entrepreneurs pending calls."""
        try:
            rows = await self._db.execute(
                """
                SELECT id, full_name, phone, country, lead_score
                FROM uzbek_entrepreneurs
                WHERE call_status = 'pending' AND phone IS NOT NULL
                ORDER BY lead_score DESC, created_at ASC
                LIMIT ?
                """,
                [limit],
            )
            return [dict(row) for row in rows]

        except Exception as e:
            logger.error("[VOICE_AGENT] Failed to get pending calls: %s", e)
            return []

    async def run_call_campaign(self, limit: int = 10) -> dict[str, int]:
        """Run automated call campaign for pending entrepreneurs."""
        entrepreneurs = await self.get_pending_calls(limit)

        results = {
            "total": len(entrepreneurs),
            "interested": 0,
            "callback": 0,
            "disconnected": 0,
            "called": 0,
        }

        for entrepreneur in entrepreneurs:
            try:
                result = await self.initiate_call(
                    entrepreneur_id=entrepreneur["id"],
                    phone=entrepreneur["phone"],
                    name=entrepreneur["full_name"],
                )

                if result:
                    if result.pressed_digit == "1":
                        results["interested"] += 1
                    elif result.pressed_digit == "2":
                        results["callback"] += 1
                    elif result.status in ["failed", "disconnected"]:
                        results["disconnected"] += 1
                    else:
                        results["called"] += 1

                # Rate limiting between calls
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(
                    "[VOICE_AGENT] Campaign call failed for #%s: %s",
                    entrepreneur["id"],
                    e,
                )

        logger.info("[VOICE_AGENT] Campaign results: %s", results)
        return results

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()


def get_vapi_config() -> Optional[VapiCallConfig]:
    """Load Vapi configuration from environment."""
    import os

    api_key = os.getenv("VAPI_API_KEY")
    phone_number_id = os.getenv("VAPI_PHONE_NUMBER_ID")
    assistant_id = os.getenv("VAPI_ASSISTANT_ID")
    voice_url = os.getenv("VAPI_VOICE_URL")

    if not all([api_key, phone_number_id, assistant_id]):
        logger.warning("[VOICE_AGENT] Vapi configuration incomplete")
        return None

    return VapiCallConfig(
        api_key=api_key,
        phone_number_id=phone_number_id,
        assistant_id=assistant_id,
        voice_url=voice_url or "",
    )

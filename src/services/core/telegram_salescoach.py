"""Telegram business-dialog orchestration for SalesCoach analysis."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Literal, Mapping, Optional

from src.services.core.telegram_salescoach_store import ConversationAnalysisRecord


logger = logging.getLogger("TelegramSalesCoach")
_VALID_MODES = {"shadow", "approval", "auto"}


@dataclass(frozen=True)
class TelegramConversationMessage:
    id: int
    role: Literal["manager", "customer"]
    text: str
    sent_at: datetime


@dataclass(frozen=True)
class CrmMatch:
    lead_id: int
    contact_id: int | None
    responsible_user_id: int
    confidence: float
    crm_status: str = ""


def _hash_value(value: Any) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def conversation_fingerprint(
    lead_id: int,
    messages: Iterable[TelegramConversationMessage],
) -> str:
    """Stable fingerprint that stores only hashes of message text."""
    parts = [f"lead={int(lead_id)}"]
    for message in messages:
        sent_at = message.sent_at
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        timestamp = sent_at.astimezone(timezone.utc).replace(microsecond=0).isoformat()
        text_hash = hashlib.sha256(message.text.encode("utf-8")).hexdigest()
        parts.append(
            f"{int(message.id)}|{message.role}|{timestamp}|{text_hash}"
        )
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _normalize_message(value: Any) -> Optional[TelegramConversationMessage]:
    if isinstance(value, TelegramConversationMessage):
        text = value.text.strip()
        if not text:
            return None
        return TelegramConversationMessage(
            id=int(value.id),
            role=value.role,
            text=text,
            sent_at=value.sent_at,
        )
    if not isinstance(value, Mapping):
        return None

    role = value.get("role")
    text = str(value.get("text") or "").strip()
    sent_at = _parse_datetime(value.get("sent_at") or value.get("sentAt"))
    try:
        message_id = int(value.get("id"))
    except (TypeError, ValueError):
        return None
    if role not in {"manager", "customer"} or not text or sent_at is None:
        return None
    return TelegramConversationMessage(
        id=message_id,
        role=role,
        text=text,
        sent_at=sent_at,
    )


class TelegramSalesCoach:
    """Filters, batches, scores and safely routes Telegram sales conversations."""

    def __init__(
        self,
        *,
        store: Any,
        salescoach_sync: Any,
        crm_matcher: Any,
        task_writer: Any,
        message_loader: Any,
        personal_sender_checker: Optional[Callable[[Any], Any]] = None,
        internal_user_ids: Iterable[int] = (),
        approval_notifier: Any = None,
        enabled: bool = False,
        mode: str = "shadow",
        idle_seconds: int = 600,
    ):
        self.store = store
        self.salescoach_sync = salescoach_sync
        self.crm_matcher = crm_matcher
        self.task_writer = task_writer
        self.message_loader = message_loader
        self.personal_sender_checker = personal_sender_checker
        self.internal_user_ids = {int(item) for item in internal_user_ids}
        self.approval_notifier = approval_notifier
        self.enabled = bool(enabled)
        self.mode = self._normalize_mode(mode)
        self.idle_seconds = max(0, int(idle_seconds))
        self._debounce_tasks: dict[int, asyncio.Task[Any]] = {}

    @staticmethod
    def _normalize_mode(mode: str) -> str:
        normalized = str(mode or "shadow").strip().lower()
        if normalized not in _VALID_MODES:
            logger.warning("Invalid Telegram SalesCoach mode; falling back to shadow")
            return "shadow"
        return normalized

    @property
    def pending_user_ids(self) -> set[int]:
        return set(self._debounce_tasks)

    async def _peer_for_event(self, event: Any, sender: Any, client: Any) -> Any:
        chat_id = int(getattr(event, "chat_id", 0) or 0)
        if getattr(sender, "id", None) == chat_id:
            return sender
        getter = getattr(client, "get_entity", None)
        if callable(getter) and chat_id:
            try:
                return await _maybe_await(getter(chat_id))
            except Exception:
                return sender
        return sender

    async def handle_private_event(
        self,
        event: Any,
        *,
        sender: Any,
        client: Any,
    ) -> None:
        if not self.enabled or not bool(getattr(event, "is_private", False)):
            return

        telegram_user_id = int(getattr(event, "chat_id", 0) or 0)
        if telegram_user_id <= 0:
            return

        get_me = getattr(client, "get_me", None)
        if callable(get_me):
            try:
                me = await _maybe_await(get_me())
                if int(getattr(me, "id", 0) or 0) == telegram_user_id:
                    return
            except Exception:
                return

        peer = await self._peer_for_event(event, sender, client)
        peer_id = int(getattr(peer, "id", telegram_user_id) or telegram_user_id)
        if bool(getattr(peer, "bot", False)):
            return
        if peer_id in self.internal_user_ids or telegram_user_id in self.internal_user_ids:
            return
        if self.personal_sender_checker is not None:
            try:
                is_personal = await _maybe_await(self.personal_sender_checker(peer))
            except Exception as exc:
                logger.warning(
                    "Personal-folder check failed for %s: %s",
                    _hash_value(telegram_user_id)[:12],
                    type(exc).__name__,
                )
                return
            if is_personal:
                return

        previous = self._debounce_tasks.pop(telegram_user_id, None)
        if previous is not None and not previous.done():
            previous.cancel()
        task = asyncio.create_task(
            self._delayed_analyze(telegram_user_id),
            name=f"telegram_salescoach:{_hash_value(telegram_user_id)[:12]}",
        )
        self._debounce_tasks[telegram_user_id] = task

    async def _delayed_analyze(self, telegram_user_id: int) -> None:
        current_task = asyncio.current_task()
        try:
            if self.idle_seconds:
                await asyncio.sleep(self.idle_seconds)
            await self.analyze_dialog_now(telegram_user_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "Telegram SalesCoach analysis failed for %s: %s",
                _hash_value(telegram_user_id)[:12],
                type(exc).__name__,
            )
        finally:
            if self._debounce_tasks.get(telegram_user_id) is current_task:
                self._debounce_tasks.pop(telegram_user_id, None)

    async def _match_crm(self, telegram_user_id: int) -> Optional[CrmMatch]:
        matcher = getattr(self.crm_matcher, "match", None)
        if callable(matcher):
            value = await _maybe_await(matcher(telegram_user_id))
        elif callable(self.crm_matcher):
            value = await _maybe_await(self.crm_matcher(telegram_user_id))
        else:
            return None
        if value is None:
            return None
        if isinstance(value, CrmMatch):
            return value
        if isinstance(value, Mapping):
            try:
                return CrmMatch(
                    lead_id=int(value.get("lead_id") or value.get("leadId")),
                    contact_id=(
                        int(value.get("contact_id") or value.get("contactId"))
                        if value.get("contact_id") or value.get("contactId")
                        else None
                    ),
                    responsible_user_id=int(
                        value.get("responsible_user_id")
                        or value.get("responsibleUserId")
                    ),
                    confidence=float(value.get("confidence") or 0),
                    crm_status=str(value.get("crm_status") or value.get("crmStatus") or ""),
                )
            except (TypeError, ValueError):
                return None
        return None

    async def _load_messages(
        self, telegram_user_id: int
    ) -> list[TelegramConversationMessage]:
        loader = getattr(self.message_loader, "load", None)
        if callable(loader):
            raw = await _maybe_await(loader(telegram_user_id))
        elif callable(self.message_loader):
            raw = await _maybe_await(self.message_loader(telegram_user_id))
        else:
            return []
        messages = [
            normalized
            for item in (raw or [])
            if (normalized := _normalize_message(item)) is not None
        ]
        messages.sort(key=lambda item: (item.sent_at, item.id))
        return messages[-50:]

    @staticmethod
    def _analysis_confidence(analysis: Mapping[str, Any]) -> float:
        try:
            return max(0.0, min(float(analysis.get("confidence") or 0), 1.0))
        except (TypeError, ValueError):
            return 0.0

    async def analyze_dialog_now(
        self, telegram_user_id: int
    ) -> Optional[dict[str, Any]]:
        if not self.enabled:
            return None

        match = await self._match_crm(telegram_user_id)
        if match is None or match.confidence < 0.60:
            return None

        messages = await self._load_messages(telegram_user_id)
        roles = {message.role for message in messages}
        if len(messages) < 2 or roles != {"manager", "customer"}:
            return None

        fingerprint = conversation_fingerprint(match.lead_id, messages)
        if await self.store.fingerprint_exists(fingerprint):
            return None

        payload_messages = [
            {
                "id": message.id,
                "role": message.role,
                "text": message.text,
                "sentAt": (
                    message.sent_at
                    if message.sent_at.tzinfo is not None
                    else message.sent_at.replace(tzinfo=timezone.utc)
                ).isoformat(),
            }
            for message in messages
        ]
        analysis = await self.salescoach_sync.analyze_conversation(
            lead_id=match.lead_id,
            manager_id=str(match.responsible_user_id),
            crm_status=match.crm_status,
            messages=payload_messages,
        )
        if not isinstance(analysis, Mapping):
            return None

        source_ids = [message.id for message in messages]
        overall_score = int(
            analysis.get("overallScore") or analysis.get("overall_score") or 0
        )
        analysis_confidence = self._analysis_confidence(analysis)
        analysis_id = await self.store.save_analysis(
            ConversationAnalysisRecord(
                conversation_hash=_hash_value(
                    f"{telegram_user_id}:{source_ids[0]}:{source_ids[-1]}"
                ),
                telegram_user_hash=_hash_value(telegram_user_id),
                lead_id=match.lead_id,
                manager_id=str(match.responsible_user_id),
                fingerprint=fingerprint,
                overall_score=overall_score,
                confidence=analysis_confidence,
                source_message_ids=source_ids,
                rollout_mode=self.mode,
                analysis=dict(analysis),
                status="pending" if self.mode == "approval" else "analyzed",
            )
        )

        result: dict[str, Any] = {
            "analysis_id": analysis_id,
            "lead_id": match.lead_id,
            "fingerprint": fingerprint,
            "analysis": dict(analysis),
            "mode": self.mode,
        }

        if self.mode == "approval":
            sender = getattr(self.approval_notifier, "send", None)
            if callable(sender):
                await _maybe_await(
                    sender(
                        analysis_id=analysis_id,
                        lead_id=match.lead_id,
                        score=overall_score,
                        risk=analysis.get("dealRisk") or analysis.get("deal_risk"),
                        next_action=analysis.get("nextBestAction")
                        or analysis.get("next_best_action"),
                        recommended_tasks=analysis.get("recommendedTasks")
                        or analysis.get("recommended_tasks")
                        or [],
                    )
                )
            return result

        if (
            self.mode == "auto"
            and match.confidence >= 0.85
            and analysis_confidence >= 0.80
        ):
            result["task_results"] = await self.task_writer.apply_analysis(
                analysis_id=analysis_id,
                lead_id=match.lead_id,
                responsible_user_id=match.responsible_user_id,
                conversation_fingerprint=fingerprint,
                analysis=dict(analysis),
                mode="auto",
            )

        return result

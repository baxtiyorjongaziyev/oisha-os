from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)

BotApiTransport = Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]


BOT_API_10_ALLOWED_UPDATES: List[str] = [
    "message",
    "edited_message",
    "callback_query",
    "inline_query",
    "business_connection",
    "business_message",
    "edited_business_message",
    "deleted_business_messages",
    "guest_message",
    "managed_bot",
    "message_reaction",
    "message_reaction_count",
    "purchased_paid_media",
]


@dataclass(frozen=True)
class TelegramAIFeature:
    key: str
    title_uz: str
    official_name: str
    oisha_use: str
    implementation: str
    status_source: str
    manual_step: str = ""


@dataclass(frozen=True)
class GuestMessageContext:
    update_id: int
    guest_query_id: str
    text: str
    caller_user: Dict[str, Any]
    caller_chat: Dict[str, Any]
    raw_message: Dict[str, Any]


class TelegramBotAPIError(RuntimeError):
    def __init__(
        self,
        method: str,
        description: str,
        *,
        error_code: Optional[int] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(f"{method} failed: {description}")
        self.method = method
        self.description = description
        self.error_code = error_code
        self.parameters = parameters or {}


FEATURE_MATRIX: List[TelegramAIFeature] = [
    TelegramAIFeature(
        key="guest_mode",
        title_uz="Guest Mode: Oisha istalgan chatda @username orqali chaqiriladi",
        official_name="Guest Bots / guest_message / answerGuestQuery",
        oisha_use=(
            "Mijoz yoki jamoa Oisha botni guruhga qo'shmasdan @mention qiladi; "
            "Oisha faqat shu xabar kontekstida javob beradi."
        ),
        implementation="raw_bot_api_10",
        status_source="getMe.supports_guest_queries",
    ),
    TelegramAIFeature(
        key="bot_to_bot",
        title_uz="Bot-to-bot: Oisha boshqa botlar bilan ish oqimi qiladi",
        official_name="Bot-to-Bot Communication",
        oisha_use=(
            "CRM, booking, payment yoki audit botlari bilan loop-safeguard orqali "
            "nazoratli agentlararo muloqot."
        ),
        implementation="raw_sendMessage_to_username",
        status_source="BotFather setting + getMe flags",
    ),
    TelegramAIFeature(
        key="streaming_responses",
        title_uz="Streaming: javob yozilayotganda draft ko'rinadi",
        official_name="sendMessageDraft",
        oisha_use=(
            "Uzun audit yoki negotiation javobida foydalanuvchi 30 soniyalik "
            "jonli draft/Thinking holatini ko'radi."
        ),
        implementation="raw_sendMessageDraft_then_sendMessage",
        status_source="Bot API method availability",
    ),
    TelegramAIFeature(
        key="chat_automation",
        title_uz="Chat Automation: bot profilga ulanib biznes chatlarni boshqaradi",
        official_name="Telegram Business / Chat Automation",
        oisha_use=(
            "Shaxsiy akkauntdagi ruxsat berilgan chatlarda lead/mijozlarni "
            "saralash, javob draft qilish va follow-up nazorati."
        ),
        implementation="business_connection_updates",
        status_source="getMe.can_connect_to_business",
        manual_step="Telegram Settings > Chat Automation ichida bot ulanishi kerak.",
    ),
    TelegramAIFeature(
        key="quick_action_bar",
        title_uz="Quick Action Bar: mijoz chatidan Oisha boshqaruviga tez o'tish",
        official_name="Manage Bot deep link: /start bizChat<user_chat_id>",
        oisha_use=(
            "Chat tepasidagi Manage Bot orqali aynan shu mijoz bo'yicha CRM, "
            "task va tavsiya oynasini ochish."
        ),
        implementation="deep_link_parser_ready",
        status_source="business_connection_updates",
        manual_step="Business mode ulanganidan keyin Telegram o'zi chiqaradi.",
    ),
    TelegramAIFeature(
        key="managed_bots",
        title_uz="Suggested/Managed bots: mijozlar uchun maxsus agent bot yaratish",
        official_name="Managed Bots",
        oisha_use=(
            "Kelajakda har bir kompaniya yoki loyiha uchun alohida yordamchi bot "
            "yaratish va kirishni cheklash."
        ),
        implementation="get/setManagedBotAccessSettings",
        status_source="getMe.can_manage_bots",
        manual_step="BotFather MiniApp'da Bot Management Mode yoqilishi kerak.",
    ),
    TelegramAIFeature(
        key="private_topics",
        title_uz="Private topics: xususiy chat ichida mavzularga ajratish",
        official_name="Starting in Topics / private chat topics",
        oisha_use=(
            "Bitta mijoz bilan chat ichida Brif, To'lov, Feedback, Fayllar kabi "
            "mavzularni tartibga solish."
        ),
        implementation="message_thread_id_support",
        status_source="getMe.has_topics_enabled",
        manual_step="BotFather'da Topics yoqilishi kerak.",
    ),
    TelegramAIFeature(
        key="profile_context",
        title_uz="Profil konteksti: birthdate, location, personal chat xabarlarini o'qish",
        official_name="Birthdate / Location / getUserPersonalChatMessages",
        oisha_use=(
            "Ruxsatli profil ma'lumotlari orqali mijoz kontekstini boyitish, "
            "lekin shaxsiy hayot filtrlarini saqlash."
        ),
        implementation="getChat + getUserPersonalChatMessages",
        status_source="permissioned_data",
        manual_step="Telegram faqat ruxsatli/ko'rinadigan profil ma'lumotini beradi.",
    ),
    TelegramAIFeature(
        key="monetization",
        title_uz="Monetizatsiya: Stars, paid media va paid broadcast",
        official_name="Telegram Stars / Paid Media / allow_paid_broadcast",
        oisha_use=(
            "Kurs, audit yoki premium konsultatsiyalarni Telegram ichida sotish; "
            "zarur bo'lsa pulli tez broadcast."
        ),
        implementation="sendInvoice/sendPaidMedia/allow_paid_broadcast",
        status_source="payment_provider_and_stars",
        manual_step="Stars/payment sozlamalari va huquqiy narx siyosati kerak.",
    ),
    TelegramAIFeature(
        key="moderation_and_polls",
        title_uz="Poll limitlari va reaction moderation",
        official_name="country_codes, members_only, deleteMessageReaction",
        oisha_use=(
            "Jamoa so'rovnomalari, lead segmentatsiyasi va guruh moderatsiyasida "
            "aniq nazorat."
        ),
        implementation="sendPoll/deleteMessageReaction/deleteAllMessageReactions",
        status_source="admin_rights_required",
        manual_step="Guruh/channel admin huquqlari kerak.",
    ),
    TelegramAIFeature(
        key="custom_ai_styles",
        title_uz="Custom AI Styles: Telegram text editor uchun Oisha uslubi",
        official_name="Custom AI Styles",
        oisha_use=(
            "Jon Branding tone-of-voice promptlarini Telegram AI Text Editor ichida "
            "standart yozish uslubiga aylantirish."
        ),
        implementation="telegram_client_feature",
        status_source="manual_telegram_app",
        manual_step="Telegram AI Text Editor > Style > Create ichida qo'lda yaratiladi.",
    ),
    TelegramAIFeature(
        key="emoji_sticker_search",
        title_uz="Emoji/sticker search: 100M+ sticker ichidan tez qidirish",
        official_name="Expanded Emoji and Sticker Search",
        oisha_use=(
            "Jamoa va mijoz chatlarida brend ohangiga mos sticker/emoji tanlash; "
            "Bot API emas, Telegram ilovasi imkoniyati."
        ),
        implementation="telegram_client_feature",
        status_source="telegram_app",
    ),
    TelegramAIFeature(
        key="poll_statistics",
        title_uz="Poll statistics: ovozlar dinamikasini ko'rish",
        official_name="Statistics for Polls",
        oisha_use=(
            "Katta guruhlarda feedback va jamoa qarorlarining vaqt bo'yicha "
            "o'zgarishini kuzatish."
        ),
        implementation="telegram_admin_ui",
        status_source="telegram_poll_ui",
        manual_step="Telegram poll statistikasi 100+ ovozdan keyin ko'rinadi.",
    ),
    TelegramAIFeature(
        key="silent_scheduled_messages",
        title_uz="Silent scheduled messages: rejalangan xabarlar bezovta qilmasin",
        official_name="Silent Scheduled Messages / disable_notification",
        oisha_use=(
            "Kecha yoki dam olish payti yuboriladigan eslatmalarni ovozsiz qilish; "
            "bot xabarlarida disable_notification ishlatiladi."
        ),
        implementation="send_methods_disable_notification",
        status_source="bot_send_parameters_or_client_schedule",
    ),
]


def feature_matrix_payload() -> List[Dict[str, Any]]:
    return [asdict(item) for item in FEATURE_MATRIX]


def clean_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not payload:
        return {}
    return {key: value for key, value in payload.items() if value is not None}


def build_text_article_result(
    text: str,
    *,
    title: str = "Oisha javobi",
    result_id: Optional[str] = None,
    parse_mode: Optional[str] = "HTML",
    description: Optional[str] = None,
) -> Dict[str, Any]:
    input_message_content: Dict[str, Any] = {
        "message_text": text or " ",
        "link_preview_options": {"is_disabled": True},
    }
    if parse_mode:
        input_message_content["parse_mode"] = parse_mode
    return {
        "type": "article",
        "id": result_id or uuid4().hex,
        "title": title,
        "description": description or text[:120],
        "input_message_content": input_message_content,
    }


def extract_guest_message_context(update: Dict[str, Any]) -> Optional[GuestMessageContext]:
    message = update.get("guest_message")
    if not isinstance(message, dict):
        return None
    guest_query_id = str(message.get("guest_query_id") or "").strip()
    if not guest_query_id:
        return None
    text = str(message.get("text") or message.get("caption") or "").strip()
    return GuestMessageContext(
        update_id=int(update.get("update_id") or 0),
        guest_query_id=guest_query_id,
        text=text,
        caller_user=message.get("guest_bot_caller_user") or {},
        caller_chat=message.get("guest_bot_caller_chat") or {},
        raw_message=message,
    )


def classify_update(update: Dict[str, Any]) -> str:
    for update_type in BOT_API_10_ALLOWED_UPDATES:
        if update_type in update:
            return update_type
    return "unknown"


def build_offline_feature_status() -> Dict[str, Any]:
    return {
        "bot_api_version_target": "10.0",
        "botfather_activated": True,
        "code_ready": {
            "guest_mode": True,
            "streaming_responses": True,
            "bot_to_bot": True,
            "business_chat_automation": True,
            "managed_bot_access": True,
            "private_topics": True,
            "profile_context": True,
            "monetization": True,
            "moderation_and_polls": True,
            "custom_ai_styles": True,
            "emoji_sticker_search": True,
            "poll_statistics": True,
            "silent_scheduled_messages": True,
        },
        "allowed_updates": list(BOT_API_10_ALLOWED_UPDATES),
        "features": feature_matrix_payload(),
    }


def build_live_feature_status(me: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "guest_mode": bool(me.get("supports_guest_queries")),
        "business_chat_automation": bool(me.get("can_connect_to_business")),
        "main_mini_app": bool(me.get("has_main_web_app")),
        "private_topics": bool(me.get("has_topics_enabled")),
        "managed_bots": bool(me.get("can_manage_bots")),
        "inline_queries": bool(me.get("supports_inline_queries")),
        "raw_get_me": me,
    }


class TelegramBotAPI10Client:
    """Small raw Bot API client for methods not yet exposed by local libraries."""

    def __init__(
        self,
        token: str,
        *,
        base_url: str = "https://api.telegram.org",
        timeout: float = 15.0,
        transport: Optional[BotApiTransport] = None,
    ):
        self.token = token.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    async def call(self, method: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        cleaned = clean_payload(payload)
        if self.transport is not None:
            response_payload = await self.transport(method, cleaned)
        else:
            url = f"{self.base_url}/bot{self.token}/{method}"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=cleaned)
                response_payload = response.json()

        if not isinstance(response_payload, dict) or not response_payload.get("ok"):
            description = (
                response_payload.get("description")
                if isinstance(response_payload, dict)
                else "invalid Bot API response"
            )
            raise TelegramBotAPIError(
                method,
                str(description or "unknown error"),
                error_code=(
                    response_payload.get("error_code")
                    if isinstance(response_payload, dict)
                    else None
                ),
                parameters=(
                    response_payload.get("parameters")
                    if isinstance(response_payload, dict)
                    else None
                ),
            )
        return response_payload.get("result")

    async def get_me(self) -> Dict[str, Any]:
        result = await self.call("getMe")
        return result if isinstance(result, dict) else {}

    async def get_webhook_info(self) -> Dict[str, Any]:
        result = await self.call("getWebhookInfo")
        return result if isinstance(result, dict) else {}

    async def set_webhook(
        self,
        url: str,
        *,
        secret_token: Optional[str] = None,
        allowed_updates: Optional[Iterable[str]] = None,
        drop_pending_updates: bool = False,
    ) -> bool:
        result = await self.call(
            "setWebhook",
            {
                "url": url,
                "secret_token": secret_token,
                "allowed_updates": list(allowed_updates or BOT_API_10_ALLOWED_UPDATES),
                "drop_pending_updates": drop_pending_updates,
            },
        )
        return bool(result)

    async def answer_guest_query(
        self,
        guest_query_id: str,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        sent = await self.call(
            "answerGuestQuery",
            {"guest_query_id": guest_query_id, "result": result},
        )
        return sent if isinstance(sent, dict) else {}

    async def send_message_draft(
        self,
        chat_id: int,
        draft_id: int,
        *,
        text: str = "",
        message_thread_id: Optional[int] = None,
        parse_mode: Optional[str] = None,
    ) -> bool:
        result = await self.call(
            "sendMessageDraft",
            {
                "chat_id": chat_id,
                "message_thread_id": message_thread_id,
                "draft_id": draft_id,
                "text": text,
                "parse_mode": parse_mode,
            },
        )
        return bool(result)

    async def finalize_streamed_message(
        self,
        chat_id: int,
        text: str,
        *,
        message_thread_id: Optional[int] = None,
        parse_mode: Optional[str] = "HTML",
    ) -> Dict[str, Any]:
        message = await self.call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "message_thread_id": message_thread_id,
                "text": text,
                "parse_mode": parse_mode,
            },
        )
        return message if isinstance(message, dict) else {}

    async def send_to_bot(
        self,
        bot_username: str,
        text: str,
        *,
        business_connection_id: Optional[str] = None,
        reply_parameters: Optional[Dict[str, Any]] = None,
        parse_mode: Optional[str] = "HTML",
    ) -> Dict[str, Any]:
        username = bot_username if bot_username.startswith("@") else f"@{bot_username}"
        message = await self.call(
            "sendMessage",
            {
                "business_connection_id": business_connection_id,
                "chat_id": username,
                "text": text,
                "parse_mode": parse_mode,
                "reply_parameters": reply_parameters,
            },
        )
        return message if isinstance(message, dict) else {}

    async def get_managed_bot_access_settings(self, user_id: int) -> Dict[str, Any]:
        result = await self.call(
            "getManagedBotAccessSettings",
            {"user_id": user_id},
        )
        return result if isinstance(result, dict) else {}

    async def set_managed_bot_access_settings(
        self,
        user_id: int,
        *,
        is_access_restricted: bool,
        added_user_ids: Optional[List[int]] = None,
    ) -> bool:
        result = await self.call(
            "setManagedBotAccessSettings",
            {
                "user_id": user_id,
                "is_access_restricted": is_access_restricted,
                "added_user_ids": added_user_ids,
            },
        )
        return bool(result)

    async def get_user_personal_chat_messages(
        self,
        user_id: int,
        *,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        bounded_limit = max(1, min(int(limit), 20))
        result = await self.call(
            "getUserPersonalChatMessages",
            {"user_id": user_id, "limit": bounded_limit},
        )
        return result if isinstance(result, list) else []

    async def delete_message_reaction(
        self,
        chat_id: int | str,
        message_id: int,
        user_id: int,
    ) -> bool:
        result = await self.call(
            "deleteMessageReaction",
            {"chat_id": chat_id, "message_id": message_id, "user_id": user_id},
        )
        return bool(result)

    async def delete_all_message_reactions(
        self,
        chat_id: int | str,
        message_id: int,
    ) -> bool:
        result = await self.call(
            "deleteAllMessageReactions",
            {"chat_id": chat_id, "message_id": message_id},
        )
        return bool(result)

    async def send_poll(
        self,
        chat_id: int | str,
        question: str,
        options: List[Dict[str, Any]],
        *,
        is_anonymous: bool = True,
        type: str = "regular",
        allows_multiple_answers: bool = False,
        members_only: Optional[bool] = None,
        country_codes: Optional[List[str]] = None,
        disable_notification: bool = False,
        message_thread_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send poll with Bot API 10 limit parameters (members_only, country_codes)."""
        result = await self.call(
            "sendPoll",
            {
                "chat_id": chat_id,
                "question": question,
                "options": options,
                "is_anonymous": is_anonymous,
                "type": type,
                "allows_multiple_answers": allows_multiple_answers,
                "members_only": members_only,
                "country_codes": country_codes,
                "disable_notification": disable_notification,
                "message_thread_id": message_thread_id,
            },
        )
        return result if isinstance(result, dict) else {}

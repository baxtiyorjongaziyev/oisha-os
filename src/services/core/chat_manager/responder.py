"""Agent javobini yaratish — faqat qoralama, hech qachon mijozga yuborilmaydi.

- `draft_reply`: Testlash (sozlamalar sahifasi) va kelajakdagi AI qoralamalar uchun.
- `run_followups`: "Proaktiv dojimlar" yoqilgan bo'lsa, jim qolgan dialoglarga
  eslatma qoralamasi yozadi (dialog boshiga ko'pi bilan 2 ta). Operator panelda
  ko'rib, o'zi yuboradi.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from src.services.core.chat_manager import store
from src.services.core.chat_manager.prompt import build_instructions

logger = logging.getLogger(__name__)

_REPLY_TOKENS = {1: 120, 2: 200, 3: 320, 4: 480, 5: 700}
_AUTHOR = {"client": "Mijoz", "ai_draft": "Agent", "operator": "Agent"}


def _system() -> str:
    settings = store.get_settings()
    instructions = build_instructions(settings, store.list_knowledge())
    return (
        "Sen Jon Branding agentligining mijozlar bilan yozishadigan sotuv agentisan.\n"
        + instructions
        + "\nFaqat mijozga yuboriladigan javob matnini yoz, izohsiz."
    )


def _max_tokens() -> int:
    return _REPLY_TOKENS.get(int(store.get_settings().get("reply_length", 3)), 320)


async def draft_reply(router: Any, message: str = "",
                      history: Optional[List[Dict[str, Any]]] = None,
                      task: str = "") -> str:
    """`message` — mijozning yangi xabari; `task` — mijoz yozmagan holda vazifa."""
    system = await asyncio.to_thread(_system)
    tokens = await asyncio.to_thread(_max_tokens)
    lines = [f"{_AUTHOR.get(m['author'], 'Mijoz')}: {m['text']}" for m in (history or [])[-20:]]
    if message.strip():
        lines.append(f"Mijoz: {message.strip()}")
    if task:
        lines.append(f"[Vazifa: {task}]")
    result = await router.generate_text(
        "\n".join(lines) + "\nAgent:", system=system, max_tokens=tokens, temperature=0.4
    )
    return (getattr(result, "text", "") or "").strip()


_FOLLOWUP_PROMPT = (
    "Mijoz oxirgi javobimizdan keyin jim qoldi. Unga bitta qisqa, bosimsiz eslatma "
    "yoz: oldingi suhbatga bog'la va keyingi qadamni taklif qil. Yangi fakt qo'shma."
)


async def run_followups(router: Any, idle_sec: float = 86400) -> int:
    """Eslatma qoralamalari soni. Sozlama o'chiq bo'lsa hech narsa qilmaydi."""
    from src.services.utils.free_ai_router import AllProvidersUnavailableError

    settings = await asyncio.to_thread(store.get_settings)
    if not settings.get("follow_ups"):
        return 0
    dialogs = await asyncio.to_thread(store.dialogs_needing_followup, idle_sec)
    made = 0
    for dialog in dialogs:
        history = await asyncio.to_thread(store.get_messages, dialog["id"], 30)
        try:
            text = await draft_reply(router, history=history, task=_FOLLOWUP_PROMPT)
        except AllProvidersUnavailableError as exc:
            logger.warning("[chat-manager] follow-up: AI mavjud emas: %s", exc)
            break
        # Bo'sh javob kvotani sarflamaydi; dialog o'zgargan bo'lsa saqlanmaydi.
        if await asyncio.to_thread(
            store.save_followup_draft, dialog["id"], dialog["last_at"], text
        ):
            made += 1
    return made

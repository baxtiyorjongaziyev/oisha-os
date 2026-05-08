"""
Surgical Negotiator Integration
Mavjud Oisha tizimiga ulash uchun integration layer
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from src.settings import settings

try:
    from src.agents.surgical_negotiator import get_surgical_negotiator
except Exception as exc:  # pragma: no cover - production safety net
    get_surgical_negotiator = None
    _SURGICAL_IMPORT_ERROR = exc
else:
    _SURGICAL_IMPORT_ERROR = None


class SurgicalIntegration:
    """
    Mavjud Oisha message controller bilan integratsiya

    Bu class yangi Surgical Negotiator'ni eski tizimga ulash uchun
    adapter vazifasini bajaradi.
    """

    def __init__(self):
        self.negotiator = get_surgical_negotiator() if get_surgical_negotiator else None
        self.enabled = bool(getattr(settings, "SURGICAL_MODE", False) and self.negotiator)
        self.autonomy_threshold = getattr(settings, "AUTONOMY_THRESHOLD", 0.6)

    async def process_message(
        self, user_id: str, message: str, context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Xabarni qayta ishlash - asosiy integratsiya nuqtasi

        Returns:
            {
                "response": str,  # Mijozga yuboriladigan javob
                "mode": str,     # "surgical" yoki "legacy"
                "requires_human": bool,
                "deal_info": dict
            }
        """

        if not self.enabled or not self.negotiator:
            # Legacy mode - return None to indicate no handling
            reason = type(_SURGICAL_IMPORT_ERROR).__name__ if _SURGICAL_IMPORT_ERROR else "disabled"
            return {"mode": "disabled", "reason": reason}

        try:
            # Get user info from context
            user_info = context.get("user_info", {}) if context else {}

            # Process through surgical negotiator
            result = await self.negotiator.handle_lead(
                user_id=user_id,
                message=message,
                user_info=user_info,
                source=context.get("source", "telegram") if context else "telegram",
            )

            # Determine if human takeover needed
            requires_human = (
                result.get("requires_approval", False)
                or result["assessment"].get("close_probability", 0) < 0.2
                or result["assessment"].get("objection") == "legal"
            )

            return {
                "response": result["response"],
                "mode": "surgical",
                "requires_human": requires_human,
                "deal_info": {
                    "deal_id": result.get("deal_id"),
                    "stage": result.get("stage"),
                    "probability": result["assessment"].get("close_probability"),
                    "actions": result.get("actions", []),
                },
                "contract": result.get("contract"),
                "raw_assessment": result["assessment"],
            }

        except Exception as e:
            # Log error and fall back to legacy
            print(f"[SURGICAL] Error: {e}")
            return {"mode": "error", "error": str(e)}

    def should_use_surgical(self, user_id: str, message: str) -> bool:
        """
        Bu xabar uchun surgical mode ishlatish kerakmi?

        Heuristics:
        - Savdo/so'rovga aloqador xabarlar
        - Narx, xizmat, shartnoma so'zlari
        """

        if not self.enabled or not self.negotiator:
            return False

        sales_keywords = [
            "narx",
            "narxi",
            "price",
            "budget",
            "budjet",
            "xizmat",
            "service",
            "ish",
            "loyiha",
            "project",
            "shartnoma",
            "contract",
            "agreement",
            "taklif",
            "offer",
            "proposal",
            "buyurtma",
            "order",
            "savdo",
            "sale",
            "qancha",
            "how much",
            "cost",
            "web",
            "sayt",
            "site",
            "branding",
            "design",
            "marketing",
            "reklama",
            "advertising",
            "kerak",
            "need",
            "want",
            "xohlayman",
        ]

        message_lower = message.lower()

        # Check for sales keywords
        for keyword in sales_keywords:
            if keyword in message_lower:
                return True

        # Check for intent indicators
        intent_markers = [
            "?",  # Questions
            "qilasizmi",
            "bormi",
            "mumkinmi",  # Inquiries
        ]

        for marker in intent_markers:
            if marker in message_lower:
                return True

        return False

    async def get_dashboard_summary(self) -> Dict[str, Any]:
        """Dashboard ma'lumotlari"""
        return self.negotiator.get_dashboard()

    async def run_daily_tasks(self) -> Dict[str, Any]:
        """Kunlik avtomatlashtirish vazifalari"""
        return await self.negotiator.run_daily_cycle()


# Singleton
_integration: Optional[SurgicalIntegration] = None


def get_surgical_integration() -> SurgicalIntegration:
    """Global integration instance"""
    global _integration
    if _integration is None:
        _integration = SurgicalIntegration()
    return _integration


# Legacy compatibility wrapper
async def enhanced_get_response(
    user_id: str, message: str, context: Dict[str, Any] = None
) -> str:
    """
    Mavjud get_response funksiyasini kengaytirish

    Usage:
        # Eski kod:
        response = await get_response(user_id, message)

        # Yangi kod:
        response = await enhanced_get_response(user_id, message, context)
    """

    integration = get_surgical_integration()

    # Check if surgical should handle this
    if integration.should_use_surgical(user_id, message):
        result = await integration.process_message(user_id, message, context)

        if result.get("mode") == "surgical":
            # Log the autonomous handling
            print(f"[SURGICAL] Autonomous response for {user_id}")

            # If contract generated, handle it
            if result.get("contract"):
                contract = result["contract"]
                print(f"[SURGICAL] Contract generated: {contract['contract_id']}")

                # Could send contract to user here

            return result["response"]

    # Fall back to legacy handling
    # (This would call the original get_response)
    return "[LEGACY MODE] " + message  # Placeholder


# Quick test function
async def test_integration():
    """Integratsiyani test qilish"""

    integration = get_surgical_integration()

    test_cases = [
        ("user_1", "Salom, web sayt uchun narx necha pul?"),
        ("user_2", "Brandbook qancha turadi?"),
        ("user_3", "Marketing xizmatlaringiz bor mi?"),
        ("user_4", "Rahmat, gapirmang"),  # Non-sales
    ]

    print("=" * 60)
    print("SURGICAL INTEGRATION TEST")
    print("=" * 60)

    for user_id, message in test_cases:
        print(f"\nUser: {user_id}")
        print(f"Message: {message}")

        should_use = integration.should_use_surgical(user_id, message)
        print(f"Surgical Mode: {'YES' if should_use else 'NO'}")

        if should_use:
            result = await integration.process_message(user_id, message)
            print(f"Response: {result.get('response', 'N/A')[:100]}...")
            print(f"Stage: {result.get('deal_info', {}).get('stage', 'N/A')}")
            print(
                f"Probability: {result.get('deal_info', {}).get('probability', 0):.0%}"
            )


if __name__ == "__main__":
    asyncio.run(test_integration())

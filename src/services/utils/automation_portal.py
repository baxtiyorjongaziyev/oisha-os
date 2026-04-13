import requests # type: ignore
import logging
import json

logger = logging.getLogger(__name__)

class AutomationBridge:
    """N8N, Make (Integromat) va Zapier bilan bog'lanish moduli."""

    @staticmethod
    def trigger_n8n_webhook(webhook_url, data):
        """N8N workflow'ni ishga tushirish."""
        try:
            response = requests.post(webhook_url, json=data, timeout=15)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"[N8N ERROR] {e}")
            return False

    @staticmethod
    def trigger_make_webhook(webhook_url, data):
        """Make.com (Integromat) workflow'ni ishga tushirish."""
        try:
            response = requests.post(webhook_url, json=data, timeout=15)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"[MAKE ERROR] {e}")
            return False

    @staticmethod
    def send_to_zapier(webhook_url, data):
        """Zapier Catch Hook ishga tushirish."""
        try:
            response = requests.post(webhook_url, json=data, timeout=15)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"[ZAPIER ERROR] {e}")
            return False

class AIPortal:
    """OpenAI, Claude va Gemini ga 'Proxy' sifatida ulanish."""

    @staticmethod
    def fast_consult(platform, query, api_key=None):
        """Boshqa AI dan 'ikkinchi fikr' olish (Oisha orqali)."""
        if not api_key:
            return "API key topilmadi."

        if platform.lower() == "openai":
            # Real-time OpenAI call
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            data = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": query}]
            }
            try:
                res = requests.post(url, headers=headers, json=data, timeout=20)
                return res.json()['choices'][0]['message']['content']
            except: return "OpenAI bilan bog'lanib bo'lmadi."

        elif platform.lower() == "claude":
            # Real-time Claude call
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            data = {
                "model": "claude-3-haiku-20240307",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": query}]
            }
            try:
                res = requests.post(url, headers=headers, json=data, timeout=20)
                return res.json()['content'][0]['text']
            except: return "Claude bilan bog'lanib bo'lmadi."

        return "Unknown platforma."

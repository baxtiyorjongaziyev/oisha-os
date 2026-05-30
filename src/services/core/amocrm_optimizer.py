"""
AmoCRM Optimizer — CRM ichki imkoniyatlarini maksimal darajaga chiqaradi.
Webhooklar, Triggerlar va Native Automation'ni sozlash.
"""

import logging
import requests
from src.services.core.amocrm_sync import AmoCRMSync

logger = logging.getLogger("AmoOptimizer")


class AmoOptimizer:
    def __init__(self, amo: AmoCRMSync):
        self.amo = amo

    async def setup_native_webhooks(self, webhook_url: str) -> dict:
        """
        AmoCRM ichki webhooklarini sozlash.
        Lid yaratilganda, status o'zgarganda Oishaga xabar kelsin.
        """
        if not webhook_url:
            return {"ok": False, "error": "Webhook URL is required"}

        # Subscriptions endpoint
        url = f"{self.amo.base_url}/api/v4/webhooks"
        
        try:
            headers = self.amo._get_headers()
            response = requests.get(url, headers=headers, timeout=25)
            if response.status_code == 401 and self.amo.refresh_token():
                headers = self.amo._get_headers()
                response = requests.get(url, headers=headers, timeout=25)
            
            existing_webhooks = []
            if response.status_code == 200:
                existing_webhooks = response.json().get("_embedded", {}).get("webhooks", []) or []
            
            # If already subscribed to this URL, skip registration
            for wh in existing_webhooks:
                if wh.get("destination") == webhook_url:
                    logger.info(f"[Webhook Check] Webhook already registered for {webhook_url}")
                    return {"ok": True, "status": "already_registered", "webhook": wh}
            
            # Subscriptions payload
            payload = {
                "destination": webhook_url,
                "settings": [
                    "add_lead",
                    "status_lead",
                    "add_contact",
                    "update_contact"
                ]
            }
            
            # Register new webhook
            response = requests.post(url, headers=headers, json=payload, timeout=25)
            if response.status_code == 401 and self.amo.refresh_token():
                headers = self.amo._get_headers()
                response = requests.post(url, headers=headers, json=payload, timeout=25)
                
            if response.status_code in [200, 201]:
                logger.info(f"[Webhook OK] Webhook successfully registered for {webhook_url}")
                return {"ok": True, "status": "registered", "webhook": response.json()}
            
            logger.error(f"[Webhook Error] Failed to register webhook: HTTP {response.status_code} - {response.text}")
            return {"ok": False, "error": f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            logger.error(f"[Webhook Exception] {e}")
            return {"ok": False, "error": str(e)}

    def get_active_leads_count(self) -> int:
        """
        Aktiv (ochiq) bitimlar sonini hisoblash.
        Basic plandagi 500 ta limitni nazorat qilish uchun juda muhim.
        """
        url = f"{self.amo.base_url}/api/v4/leads"
        active_count = 0
        limit = 250
        page = 1
        
        try:
            headers = self.amo._get_headers()
            while True:
                params = {"limit": limit, "page": page}
                response = requests.get(url, headers=headers, params=params, timeout=25)
                if response.status_code == 401 and self.amo.refresh_token():
                    headers = self.amo._get_headers()
                    response = requests.get(url, headers=headers, params=params, timeout=25)
                
                if response.status_code != 200:
                    break
                    
                payload = response.json()
                batch = payload.get("_embedded", {}).get("leads", []) or []
                if not batch:
                    break
                    
                for lead in batch:
                    status_id = int(lead.get("status_id") or 0)
                    if status_id not in [142, 143]:  # STATUS_WON and STATUS_LOST are excluded
                        active_count += 1
                        
                if "next" not in (payload.get("_links") or {}):
                    break
                page += 1
                
            return active_count
        except Exception as e:
            logger.error(f"[Capacity Count Exception] {e}")
            return -1

    def get_automation_manual(self) -> str:
        """
        AmoCRM ichida qo'lda sozlanishi kerak bo'lgan eng muhim 3 ta narsa.
        """
        return """
        🚀 AMO-CRM NATIVE OPTIMIZATION (Qo'llanma - Basic Tarif):
        
        1. **Pipeline Stage Clarity (Hunilarni qisqartirish):**
           - Basic tarifda ko'pi bilan 10 ta pipeline ochish mumkin, lekin operatsion chalkashliklarni
             oldini olish uchun pipelines sonini 3 tagacha minimallashtiring:
             A) Hunter (Yangi so'rovlar saralash va uchrashuv)
             B) Setter/Closer (KP yuborish, shartnoma va yopilish)
             C) Reactivation (Sovuq baza / qayta tiriltirish)
        
        2. **Required Fields (Majburiy maydonlar):**
           - "Sotuv sababi" (Loss reason) va "Mijoz tabiati" custom maydonlarini barcha Pipelines
             uchun majburiy (Required) qiling. Sdelka yopilayotganda bu ma'lumot kiritilmasa, 
             tizim statusni o'zgartirishga yo'l qo'ymasin. Bu Oisha-OS uchun ideal data yetkazadi.
        
        3. **External Digital Funnel Integration:**
           - Basic tarifda "Цифровая воронка" (avtomatik vazifa, trigger) yopiq bo'lsa-da, 
             Oisha-OS orqali tashqi webhooklarni ulash orqali barcha sdelkalar o'zgarganda
             orqa fonda avtomatik vazifa yaratish va AI muzokara tahlilini mutlaqo tekinga yoqishingiz mumkin.
        """


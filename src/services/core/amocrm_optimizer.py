"""
AmoCRM Optimizer — CRM ichki imkoniyatlarini maksimal darajaga chiqaradi.
Webhooklar, Triggerlar va Native Automation'ni sozlash.
"""

import logging
from src.services.core.amocrm_sync import AmoCRMSync

logger = logging.getLogger("AmoOptimizer")


class AmoOptimizer:
    def __init__(self, amo: AmoCRMSync):
        self.amo = amo

    async def setup_native_webhooks(self):
        """
        AmoCRM ichki webhoklarini sozlash.
        Lid yaratilganda, status o'zgarganda Oishaga xabar kelsin.
        """
        url = f"{self.amo.base_url}/api/v4/webhooks"
        data = {
            "destination": f"https://{self.amo.subdomain}.oisha.uz/api/amocrm/webhook",
            "settings": [
                "add_lead",
                "status_lead",
                "add_contact",
                "add_message",  # Chat integratsiyasi uchun
            ],
        }
        # AmoCRM native webhook registration
        # res = requests.post(url, json=data, headers=...)
        pass

    async def ensure_native_tasks(self, lead_id: int):
        """
        Agar lid 'Negotiation' statusida bo'lsa,
        AmoCRM native 'Task' yaratish (tashqi kodsiz).
        """
        # Bu mantiqni AmoCRM Digital Pipeline'da sozlash yaxshiroq,
        # lekin API orqali ham nazorat qilsa bo'ladi.
        pass

    def get_automation_manual(self) -> str:
        """
        AmoCRM ichida qo'lda sozlanishi kerak bo'lgan eng muhim 3 ta narsa.
        """
        return """
        🚀 AMO-CRM NATIVE OPTIMIZATION (Qo'llanma):
        
        1. **Digital Pipeline Triggers:**
           - 'Lid yaratildi' statusiga: 'Sotuvchi uchun 15 daqiqalik vazifa ochish' triggerini qo'shing.
           - 'Qarovsiz qoldi' statusiga: 'Menejerni tag qilish' triggerini qo'shing.
        
        2. **Salesbot (Native):**
           - Chatga birinchi marta yozganlarga: 'Assalomu alaykum, ismingizni yozib qoldiring' deb 
             avtomatik javob qaytarishni yoqing.
        
        3. **Custom Fields Alignment:**
           - 'Sotuv sababi', 'Mijoz tipi' kabi maydonlarni (fields) majburiy qiling (Required).
             Busiz menejer statusni o'zgartira olmasin.
        """

import logging
import json
import os
from .core import BaseAgent
from typing import Optional, Dict, Any
from google.genai import types

logger = logging.getLogger(__name__)

class SalesAgent(BaseAgent):
    """Mijozlar bilan sotuv va kelishuvlarni olib boruvchi agent (Agentic Negotiation)."""
    
    def __init__(self, agent_id: str, system_prompt: str, api_keys: Dict[str, str], executor: Optional[Any] = None, db: Optional[Any] = None):
        super().__init__(agent_id, system_prompt, api_keys, executor, db)
        self.products = self._load_products()

    def _load_products(self) -> Dict[str, Any]:
        """Agentlik xizmatlari haqida ma'lumotni yuklash."""
        path = os.path.join("data", "agency_products.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"[SALES AGENT] KB yuklashda xato: {e}")
        return {}

    async def process_task(self, user_id: int, task_description: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Processes a sales interaction, providing a DRAFT for the manager instead of a direct reply.
        """
        products_context = json.dumps(self.products, indent=2, ensure_ascii=False)
        
        system_instruction = f"""
        👸 **OISHA-OS: SALES SHADOW ADVISOR (DRAFT MODE)** 👸
        
        Sizning vazifangiz — Jon.Branding agentligi sotuv menejerlariga eng zo'r javobni DRAFT (qoralama) qilib berishdir.
        Siz mijoz bilan TO'G'RIDAN-TO'G'RI gaplashmaysiz. Sizning xabaringizni menejer o'qiydi va kerak bo'lsa nusxalab yuboradi.
        
        🎯 MAQSAD: Mijozni "Strategik sessiya"ga olib kelish.
        
        AGENTLIK BILIMLAR BAZASI (Xizmatlar va Narxlar):
        {products_context}
        
        QOIDALAR:
        1. **Draft formati**: Javobingizni har doim `✍️ [DRAFT]` deb boshlang.
        2. **Strategik maslahat**: Draftdan keyin menejerga `💡 [TIP]` sarlavhasi bilan qisqa maslahat bering (masalan: "U narxdan shubhalanyapti, unga portfolio-ni ko'rsatishni taklif qiling").
        3. **To'liq avtonomiya (Internal)**: Agar mijozning ehtiyoji aniq bo'lsa, statusni o'zgartirishni (update_lead_status) taklif qiling yoki bajaring.
        4. O'zbek tilida, 'High-Service' darajasida, professional va samimiy yozing.
        """
        
        # Pull history from DB if not in context
        history = self.get_session_history(user_id) if hasattr(self, 'get_session_history') else []
        history_text = "\n".join([f"{h['role']}: {h['content']}" for h in history[-5:]])
        
        prompt = f"Suhbat tarixi:\n{history_text}\n\nKeyingi xabar: {task_description}\n\nManager uchun draft va tip yarating."
        
        # Use BaseAgent call_ai_with_fallback
        return await self.call_ai_with_fallback(prompt, system_instruction)

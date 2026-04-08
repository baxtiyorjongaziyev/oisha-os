
import logging
from .core import BaseAgent
from typing import Optional, Dict, Any
from google.genai import types

logger = logging.getLogger(__name__)

class PMAgent(BaseAgent):
    """Loyihalarni boshqarish va nazorat qilish agenti (Project Manager)."""
    
    def __init__(self, agent_id: str, system_prompt: str, api_keys: Dict[str, str], executor: Optional[Any] = None, db: Optional[Any] = None):
        super().__init__(agent_id, system_prompt, api_keys, executor, db)
        self.team_system_prompt = """
Siz JonBranding agentligining **Project Manager** (PM) assistentisiz. 
Sizning vazifangiz:
1. Jamoa a'zolariga topshiriqlar bo'yicha yordam berish.
2. Loyiha muddatlarini (deadlines) kuzatish.
3. Jamoa ichidagi muloqotda "siz" va "aka/opa" deb murojaat qilish.
4. Professional, qat'iy va intizomli bo'ling.
"""

    async def process_task(self, user_id: int, task_description: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Loyiha boshqaruvi bo'yicha muloqotni boshqarish."""
        self.update_history(user_id, "user", task_description)
        
        # Kontekstga qarab qo'shimcha ko'rsatmalarni tanlash
        is_team = context and context.get("role") == "Jamoa"
        active_instruction = (
            "\n\n[AGENT MISSION: PROJECT MANAGER]\n"
            "Siz hozirda Project Manager (PM) sifatida ishlayapsiz. Jamoaga yordam bering, muddatlarni kuzating va muloqotda Oisha bo'lib qoling."
        ) if is_team else ""
        
        # Tarixni Gemini formatiga o'tkazish
        history = self.get_session_history(user_id)
        contents = []
        for turn in history:
            role = "user" if turn["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": turn["content"]}]})
            
        # Asosiy prompga qo'shish
        original_prompt = self.system_prompt
        self.system_prompt = original_prompt + active_instruction
        
        reply = await self.call_ai_with_fallback(contents, user_id)
        
        # Qayta tiklash
        self.system_prompt = original_prompt
        
        self.update_history(user_id, "assistant", reply)
        return reply

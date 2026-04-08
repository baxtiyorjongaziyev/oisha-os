import logging
import os
from typing import Optional, Dict, Any
from .core import BaseAgent

logger = logging.getLogger(__name__)

class SupportAgent(BaseAgent):
    """FAQ va texnik yordam ko'rsatuvchi agent."""
    
    async def process_task(self, user_id: int, task_description: str, context: Optional[Dict[str, Any]] = None) -> str:
        self.update_history(user_id, "user", task_description)
        
        # Bilimlar bazasini o'qish (Grounded responses)
        knowledge_base = ""
        if os.path.exists("training_data.txt"):
            with open("training_data.txt", "r", encoding="utf-8") as f:
                knowledge_base = f.read()

        # Tarixni Gemini formatiga o'tkazish
        history = self.get_session_history(user_id)
        contents = []
        for turn in history:
            role = "user" if turn["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": turn["content"]}]})
            
        # Kontekst va Bilimlar bazasini tizim ko'rsatmasiga qo'shish
        full_context = f"\n\n[INTERNAL KNOWLEDGE BASE]:\n{knowledge_base}"
        if context:
            full_context += f"\n\n[USER CONTEXT]: {context.get('crm_status', 'Yangi mijoz')}"
            
        original_prompt = self.system_prompt
        self.system_prompt += full_context
        
        reply = await self.call_ai_with_fallback(contents, user_id)
        
        # Prompni qayta tiklash
        self.system_prompt = original_prompt
        
        self.update_history(user_id, "assistant", reply)
        return reply

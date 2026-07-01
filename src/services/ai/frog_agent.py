"""Eat That Frog AI Logic.
Identifies the most profitable task for the day.
"""
from typing import Dict, Any, List
import structlog
import os
from google import genai
from pydantic import BaseModel

logger = structlog.get_logger()

class TaskPriorityAnalysis(BaseModel):
    most_important_task_id: int
    profit_estimate: int
    reason: str
    motivation_message: str

class FrogAgent:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        
    async def identify_frog(self, tasks: List[Dict[str, Any]]) -> TaskPriorityAnalysis:
        if not tasks:
            return None
            
        prompt = "Siz Oisha-OS ning 'Eat That Frog' (Qurbaqani Yeyish) agentisiz.\n"
        prompt += "Vazifalar ro'yxatini ko'rib chiqing va eng katta foyda olib keladigan bitta vazifani tanlang.\n\n"
        
        for t in tasks:
            prompt += f"ID: {t.get('id')} | Sarlavha: {t.get('title')} | Izoh: {t.get('description')} | Ustuvorlik: {t.get('priority')} | Kutilayotgan foyda: ${t.get('profit_estimate', 0)}\n"
            
        prompt += "\nJavobni JSON formatida qaytaring: {most_important_task_id: int, profit_estimate: int, reason: str, motivation_message: str}. "
        prompt += "motivation_message - bu telegram xabar matni bo'lib, o'zbek tilida, energiya beradigan, motivatsion bo'lsin. 'Xayrli tong, Bosing! Bugungi Qurbaqa...' kabi."
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config={
                    'response_mime_type': 'application/json',
                    'response_schema': TaskPriorityAnalysis,
                },
            )
            return response.parsed
        except Exception as e:
            logger.error(f"[FROG_AGENT] Error identifying frog: {e}")
            return None

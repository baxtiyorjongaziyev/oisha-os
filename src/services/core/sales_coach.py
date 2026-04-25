"""
SalesCoach AI — Har bir qo'ng'iroqni 'pixel'ma-pixel tahlil qiladi.
Metasell Gold Standard asosida ishlaydi.
"""

import logging
import json
from typing import Dict, Any, List
from src.settings import settings

logger = logging.getLogger("SalesCoach")

class SalesCoach:
    def __init__(self, ai_provider=None):
        self.ai = ai_provider
        # Metasell Scoring Rubric
        self.rubrics = {
            "opening": "Salomlashish va kontakt o'rnatish. Menejer o'zini tanitdimi? Mijoz ismini so'radimi?",
            "needs_discovery": "Ehtiyojni aniqlash. Mijozning og'riqli nuqtalarini topish uchun savollar berildimi?",
            "presentation": "Mahsulot/xizmat taqdimoti. Ehtiyojdan kelib chiqib taklif berildimi?",
            "objection_handling": "E'tirozlar bilan ishlash. 'Qimmat' yoki 'O'ylab ko'raman' degan javoblarga tayyor edimi?",
            "closing": "Kelishuvni yakunlash. Keyingi qadam aniq belgilandimi?"
        }

    async def analyze_call(self, transcript: str) -> Dict[str, Any]:
        """
        GPT-4o orqali qo'ng'iroqni tahlil qilish.
        """
        if not transcript:
            return {"error": "Transcript bo'sh"}

        prompt = f"""
        Siz professional Sales Coach-siz. Quyidagi savdo qo'ng'irog'i transcriptini Metasell standartlari asosida tahlil qiling.
        
        Transcript:
        {transcript}
        
        Quyidagi formatda JSON qaytaring:
        {{
            "total_score": 0-100 gacha ball,
            "metrics": {{
                "opening": {{"score": 0-20, "comment": "qisqa izoh"}},
                "needs_discovery": {{"score": 0-20, "comment": "qisqa izoh"}},
                "presentation": {{"score": 0-20, "comment": "qisqa izoh"}},
                "objection_handling": {{"score": 0-20, "comment": "qisqa izoh"}},
                "closing": {{"score": 0-20, "comment": "qisqa izoh"}}
            }},
            "summary": "Umumiy xulosa",
            "next_steps": ["1-qadam", "2-qadam"],
            "red_flags": ["Xato 1", "Xato 2"]
        }}
        Faqat JSON qaytaring.
        """
        
        try:
            # Clean transcript for the prompt
            clean_text = transcript[:5000] # Limit to avoid context overflow
            
            # AI request
            response = await self.ai.generate_content(prompt)
            
            # Extract JSON from response (handling potential markdown formatting)
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"[COACH] Analysis failed: {e}")
            return {
                "total_score": 0,
                "metrics": {
                    "opening": {"score": 0, "comment": "Tahlil qilishda xatolik yuz berdi"},
                    "needs_discovery": {"score": 0, "comment": "-"},
                    "presentation": {"score": 0, "comment": "-"},
                    "objection_handling": {"score": 0, "comment": "-"},
                    "closing": {"score": 0, "comment": "-"}
                },
                "summary": f"Tahlil to'xtab qoldi: {str(e)}",
                "next_steps": ["Tizimni tekshirish"],
                "red_flags": ["AI Provider error"]
            }

    def calculate_forecast(self, leads: List[Dict]) -> Dict[str, Any]:
        """
        Lidlar ehtimolligiga qarab tushumni bashorat qilish.
        """
        total_forecast = 0
        confidence_levels = {
            "Lead": 0.1,
            "Meeting": 0.3,
            "Offer": 0.6,
            "Negotiation": 0.8
        }
        
        for lead in leads:
            status = lead.get("status_name", "Lead")
            price = lead.get("price", 0) or 0
            prob = confidence_levels.get(status, 0.1)
            total_forecast += price * prob
            
        return {
            "estimated_revenue": total_forecast,
            "confidence": "Medium",
            "logic": "Lid statuslari va tarixiy konversiyaga asoslangan"
        }

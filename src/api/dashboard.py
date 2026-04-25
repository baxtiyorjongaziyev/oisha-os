from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from src.settings import settings
import libsql_client
import json

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

class CallMetric(BaseModel):
    label: str
    score: int  # 0-100
    status: str # "success", "warning", "danger"

class Entity(BaseModel):
    key: str
    value: str

class CallDetails(BaseModel):
    call_id: str
    lead_name: str
    summary: str
    sentiment: str
    metrics: List[CallMetric]
    entities: List[Entity]
    transcript: List[dict] # {speaker: str, text: str, timestamp: str}
    next_steps: List[str]

@router.get("/call/{call_id}", response_model=CallDetails)
async def get_call_analytics(call_id: str):
    """
    Metasell uslubida qo'ng'iroq tahlilini qaytaradi.
    Hozircha Turso DB dan ma'lumotlarni oladi yoki mock qiladi.
    """
    try:
        # Haqiqiy loyihada Turso DB dan olinadi:
        # url = settings.TURSO_DATABASE_URL
        # token = settings.TURSO_AUTH_TOKEN
        # client = libsql_client.create_client_sync(url=url, auth_token=token)
        # res = client.execute("SELECT * FROM calls WHERE call_id = ?", (call_id,))
        
        # Mock data (Metasell dizaynini sinash uchun)
        return CallDetails(
            call_id=call_id,
            lead_name="Baxtiyorjon Gaziyev",
            summary="Mijoz Oisha-OS integratsiyasi bo'yicha qiziqish bildirdi. Asosiy ehtiyoj - CRM dagi bitimlarni avtomatlashtirish va menejerlar ishini nazorat qilish.",
            sentiment="Positive / High Intent",
            metrics=[
                CallMetric(label="Salomlashish", score=100, status="success"),
                CallMetric(label="Ehtiyoj aniqlash", score=85, status="success"),
                CallMetric(label="E'tirozlar bilan ishlash", score=40, status="warning"),
                CallMetric(label="Narx taklif qilish", score=20, status="danger"),
                CallMetric(label="Keyingi qadamni tayinlash", score=90, status="success"),
            ],
            entities=[
                Entity(key="Kompaniya", value="Metasell AI"),
                Entity(key="Byudjet", value="5,000,000 UZS"),
                Entity(key="Pain Point", value="Menejerlar bitimlarni o'z vaqtida yopmayapti"),
            ],
            transcript=[
                {"speaker": "Manager", "text": "Assalomu alaykum, Baxtiyor aka. Oisha-OS loyihasi bo'yicha bog'lanayotgan edim.", "timestamp": "00:01"},
                {"speaker": "Client", "text": "Vaalaykum assalom. Ha, kutyapman. Bizga aynan Bitrix24 yoki amoCRM bilan integratsiya kerak.", "timestamp": "00:05"},
                {"speaker": "Manager", "text": "Tushunarli. Bizda amoCRM uchun tayyor integratsiya bor. Hozirgi tarifingiz qanday?", "timestamp": "00:12"},
            ],
            next_steps=[
                "Demo taqdimot yuborish",
                "Dushanba kuni soat 10:00 da qayta aloqaga chiqish",
            ]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_general_stats():
    """Dashboardning tepa qismidagi umumiy statistika"""
    return {
        "total_calls": 1240,
        "avg_score": 76,
        "high_intent_leads": 45,
        "efficiency_growth": "+12%"
    }

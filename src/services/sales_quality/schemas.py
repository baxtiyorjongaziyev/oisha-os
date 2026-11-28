"""
Sales quality API schemas.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SalesQualityAnalysisRequest(BaseModel):
    secret_key: str
    call_id: str
    lead_id: Optional[int] = None
    manager_id: Optional[int] = None
    manager_name: str = ""
    client_name: Optional[str] = None
    duration_seconds: int = 0
    overall_score: int
    category: Optional[str] = None
    scores: List[Dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    client_mood: str = "neutral"
    client_interest_level: int = 0
    objections_raised: List[str] = Field(default_factory=list)
    outcome: str = "unknown"
    next_steps: List[str] = Field(default_factory=list)
    recommended_tasks: List[Dict[str, Any]] = Field(default_factory=list)
    transcript: str = ""
    audio_url: Optional[str] = None
    source: str = "external"
    analyzed_at: Optional[str] = None


class SalesChatAskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    days: Optional[int] = Field(default=None, ge=1, le=365)
    history: List[Dict[str, Any]] = Field(default_factory=list)


class SalesChatVoiceRequest(BaseModel):
    audio_base64: str = Field(..., min_length=8, max_length=14_000_000)
    mime_type: str = Field(default="audio/webm", max_length=64)
    days: Optional[int] = Field(default=None, ge=1, le=365)
    history: List[Dict[str, Any]] = Field(default_factory=list)

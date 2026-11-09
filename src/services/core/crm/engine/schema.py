"""Oisha CRM — Pydantic maʼlumotlar modellari va sxemalari.

Ushbu modul amoCRM oʻrnini bosuvchi mustaqil Oisha CRM tizimining
barcha asosiy obyektlarini (Voronkalar, Bosqichlar, Bitimlar,
Kontaktlar, Kompaniyalar, Vazifalar va Hodisalar) belgilaydi.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StageModel(BaseModel):
    """Voronka bosqichi modeli."""
    id: int
    pipeline_id: int
    name: str
    slug: str
    color: str = "#4c8bf7"
    sort_order: int = 0
    is_won: bool = False
    is_lost: bool = False


class PipelineModel(BaseModel):
    """Savdo voronkasi modeli."""
    id: int
    name: str
    slug: str
    is_main: bool = False
    is_archive: bool = False
    stages: List[StageModel] = Field(default_factory=list)


class CompanyModel(BaseModel):
    """Mijoz korxonasi modeli."""
    id: Optional[int] = None
    name: str
    industry: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    inn: Optional[str] = None
    address: Optional[str] = None
    custom_fields: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None


class ContactModel(BaseModel):
    """Jismoniy shaxs / Masʼul vakil modeli."""
    id: Optional[int] = None
    company_id: Optional[int] = None
    name: str
    phone: str
    email: Optional[str] = None
    position: Optional[str] = None
    telegram_username: Optional[str] = None
    custom_fields: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None


class DealCreate(BaseModel):
    """Yangi bitim yaratish soʻrovi."""
    name: str
    pipeline_id: int = 1
    stage_id: int = 1
    price: float = 0.0
    responsible_user_id: Optional[int] = None
    responsible_name: Optional[str] = "Shahnoza Abdijabborova"
    contact_name: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    source: str = "Veb-sayt"
    tags: List[str] = Field(default_factory=list)
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


class DealUpdate(BaseModel):
    """Mavjud bitimni tahrirlash soʻrovi."""
    name: Optional[str] = None
    pipeline_id: Optional[int] = None
    stage_id: Optional[int] = None
    price: Optional[float] = None
    responsible_user_id: Optional[int] = None
    responsible_name: Optional[str] = None
    contact_name: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class DealModel(BaseModel):
    """Toʻliq bitim modeli."""
    id: int
    name: str
    pipeline_id: int
    stage_id: int
    stage_name: Optional[str] = None
    price: float = 0.0
    responsible_user_id: Optional[int] = None
    responsible_name: Optional[str] = None
    contact_id: Optional[int] = None
    contact_name: Optional[str] = None
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    source: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    custom_fields: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    next_task_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TaskCreate(BaseModel):
    """Vazifa qoʻshish soʻrovi."""
    deal_id: int
    title: str
    task_type: str = "Qoʻngʻiroq qilish"
    responsible_name: str = "Shahnoza Abdijabborova"
    due_at: str
    notes: Optional[str] = None


class TaskModel(BaseModel):
    """Toʻliq vazifa modeli."""
    id: int
    deal_id: int
    deal_name: Optional[str] = None
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    title: str
    task_type: str
    responsible_name: str
    due_at: str
    is_completed: bool = False
    result_text: Optional[str] = None
    created_at: Optional[str] = None


class TimelineEventCreate(BaseModel):
    """Kartochka tasmaga yangi hodisa yozish."""
    deal_id: int
    event_type: str = "note"  # note, call, message, stage_change, task, ai_mission
    author: str = "Tizim"
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TimelineEventModel(BaseModel):
    """Toʻliq kartochka hodisasi modeli."""
    id: int
    deal_id: int
    event_type: str
    author: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


class IntakeLeadPayload(BaseModel):
    """Tashqi manbalardan (Sayt, Bot, Meta, CAPI) kiruvchi yangi lid."""
    name: str = "Yangi Murojaat"
    phone: str
    email: Optional[str] = None
    company_name: Optional[str] = None
    comment: Optional[str] = None
    source: str = "Veb-sayt"
    tags: List[str] = Field(default_factory=list)
    custom_fields: Dict[str, Any] = Field(default_factory=dict)

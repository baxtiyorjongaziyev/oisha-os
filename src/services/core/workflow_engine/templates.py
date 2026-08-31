"""
Jon Branding workflow step definitions and templates mixin.
"""
from __future__ import annotations

import logging
from typing import List

from src.services.core.workflow_engine.models import Role, WorkflowStep

logger = logging.getLogger("MandatoryWorkflow")


def _get_hunter_workflow() -> List[WorkflowStep]:
    return [
        WorkflowStep(id="h_1", name="Kunlik rejani olish", description="Direktordan kunlik Surgical Mission olish", role=Role.HUNTER, order=1, estimated_time=15, crm_pipeline_id="hunter"),
        WorkflowStep(id="h_2", name="Lead qidirish", description="50 ta yangi lead topish", role=Role.HUNTER, order=2, estimated_time=120, blocked_until="h_1"),
        WorkflowStep(id="h_3", name="Birinchi kontakt", description="20 ta lead bilan aloqa qilish", role=Role.HUNTER, order=3, estimated_time=90, blocked_until="h_2"),
        WorkflowStep(id="h_4", name="CRM'ga yuklash", description="Barcha leadlarni AmoCRM'ga kiritish", role=Role.HUNTER, order=4, estimated_time=30, blocked_until="h_3"),
        WorkflowStep(id="h_5", name="Setter'ga topshirish", description="Iliq leadlarni Setter'ga o'tkazish", role=Role.HUNTER, order=5, estimated_time=15, blocked_until="h_4"),
        WorkflowStep(id="h_6", name="Kunlik hisobot", description="Direktorga kunlik natijalarni yuborish", role=Role.HUNTER, order=6, estimated_time=15, blocked_until="h_5"),
    ]


def _get_setter_workflow() -> List[WorkflowStep]:
    return [
        WorkflowStep(id="s_1", name="Leadlarni qabul qilish", description="Hunter'dan yangi leadlarni tekshirish", role=Role.SETTER, order=1, estimated_time=20, crm_pipeline_id="setter"),
        WorkflowStep(id="s_2", name="Kvalifikatsiya qo'ng'irog'i", description="Mijoz ehtiyojini aniqlash", role=Role.SETTER, order=2, estimated_time=60, blocked_until="s_1"),
        WorkflowStep(id="s_3", name="Uchrashuv belgilash", description="Closer bilan uchrashuv vaqtini kelishish", role=Role.SETTER, order=3, estimated_time=30, blocked_until="s_2"),
        WorkflowStep(id="s_4", name="Brif to'ldirish", description="Mijoz haqida to'liq ma'lumot kiritish", role=Role.SETTER, order=4, estimated_time=30, blocked_until="s_3"),
        WorkflowStep(id="s_5", name="Eslatma yuborish", description="Uchrashuvdan 2 soat oldin mijozga eslatma", role=Role.SETTER, order=5, estimated_time=10, blocked_until="s_4"),
    ]


def _get_closer_workflow() -> List[WorkflowStep]:
    return [
        WorkflowStep(id="c_1", name="Uchrashuvga tayyorgarlik", description="Brif va mijoz ma'lumotlarini o'rganish", role=Role.CLOSER, order=1, estimated_time=30, crm_pipeline_id="closer"),
        WorkflowStep(id="c_2", name="Prezentatsiya o'tkazish", description="Taklif va portfolioni taqdim etish", role=Role.CLOSER, order=2, estimated_time=60, blocked_until="c_1"),
        WorkflowStep(id="c_3", name="Etirozlar bilan ishlash", description="Mijoz savollariga to'liq javob berish", role=Role.CLOSER, order=3, estimated_time=30, blocked_until="c_2"),
        WorkflowStep(id="c_4", name="Shartnoma va hisob-faktura", description="Yuridik hujjatlarni rasmiylashtirish", role=Role.CLOSER, order=4, estimated_time=30, blocked_until="c_3"),
        WorkflowStep(id="c_5", name="Oldindan to'lovni qabul qilish", description="Kassaga pul tushganini tasdiqlash", role=Role.CLOSER, order=5, estimated_time=15, blocked_until="c_4"),
    ]


def _get_pm_workflow() -> List[WorkflowStep]:
    return [
        WorkflowStep(id="pm_1", name="Loyiha brifingi", description="Closer'dan loyihani to'liq qabul qilish", role=Role.PM, order=1, estimated_time=30, crm_pipeline_id="production"),
        WorkflowStep(id="pm_2", name="Dizaynerga topshiriq", description="Texnik topshiriqni (TT) tuzish", role=Role.PM, order=2, estimated_time=45, blocked_until="pm_1"),
        WorkflowStep(id="pm_3", name="Oraliq nazorat", description="Dizayn jarayonini kuzatish", role=Role.PM, order=3, estimated_time=30, blocked_until="pm_2"),
        WorkflowStep(id="pm_4", name="Mijozga taqdimot", description="Dastlabki natijalarni mijozga ko'rsatish", role=Role.PM, order=4, estimated_time=45, blocked_until="pm_3"),
        WorkflowStep(id="pm_5", name="Tuzatishlar kiritish", description="Mijoz fikrlari asosida tuzatishlar", role=Role.PM, order=5, estimated_time=60, blocked_until="pm_4"),
        WorkflowStep(id="pm_6", name="Yakuniy topshirish", description="Loyihani to'liq topshirish va akt imzolash", role=Role.PM, order=6, estimated_time=30, blocked_until="pm_5"),
    ]


def _get_designer_workflow() -> List[WorkflowStep]:
    return [
        WorkflowStep(id="d_1", name="TT o'rganish", description="Vazifa va brend talablarini chuqur o'rganish", role=Role.DESIGNER, order=1, estimated_time=30, crm_pipeline_id="design"),
        WorkflowStep(id="d_2", name="Konsept yaratish", description="3 ta boshlang'ich vizual variant chizish", role=Role.DESIGNER, order=2, estimated_time=180, blocked_until="d_1"),
        WorkflowStep(id="d_3", name="PM bilan kelishish", description="Konseptlarni PM ko'rigidan o'tkazish", role=Role.DESIGNER, order=3, estimated_time=30, blocked_until="d_2"),
        WorkflowStep(id="d_4", name="Final fayllar", description="Barcha formatlarni (vektor/raster) tayyorlash", role=Role.DESIGNER, order=4, estimated_time=60, blocked_until="d_3"),
    ]


class WorkflowTemplatesMixin:
    """Configures default workflows for Hunter, Setter, Closer, PM, and Designer."""

    def _setup_jon_branding_workflows(self):
        """Jon.Branding uchun qat'iy ish jarayonlari"""
        self.workflows["hunter_daily"] = _get_hunter_workflow()
        self.workflows["setter_daily"] = _get_setter_workflow()
        self.workflows["closer_deal"] = _get_closer_workflow()
        self.workflows["pm_project"] = _get_pm_workflow()
        self.workflows["designer_task"] = _get_designer_workflow()

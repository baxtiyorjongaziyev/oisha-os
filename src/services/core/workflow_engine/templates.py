"""
Jon Branding workflow step definitions and templates mixin.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.services.core.workflow_engine.models import (
    Role,
    TaskStatus,
    UserTask,
    WorkflowStep,
)

logger = logging.getLogger("MandatoryWorkflow")


class WorkflowTemplatesMixin:
    """Configures default workflows for Hunter, Setter, Closer, PM, and Designer."""

    def _setup_jon_branding_workflows(self):
        """Jon.Branding uchun qat'iy ish jarayonlari"""

        # HUNTER workflow - Lead ovlash
        self.workflows["hunter_daily"] = [
            WorkflowStep(
                id="h_1",
                name="Kunlik rejani olish",
                description="Direktordan kunlik Surgical Mission olish",
                role=Role.HUNTER,
                order=1,
                estimated_time=15,
                crm_pipeline_id="hunter",
            ),
            WorkflowStep(
                id="h_2",
                name="Lead qidirish",
                description="50 ta yangi lead topish (Telegram, LinkedIn, Instagram)",
                role=Role.HUNTER,
                order=2,
                estimated_time=120,
                blocked_until="h_1",
            ),
            WorkflowStep(
                id="h_3",
                name="Birinchi kontakt",
                description="20 ta lead bilan aloqa qilish (cold outreach)",
                role=Role.HUNTER,
                order=3,
                estimated_time=90,
                blocked_until="h_2",
            ),
            WorkflowStep(
                id="h_4",
                name="CRM'ga yuklash",
                description="Barcha leadlarni AmoCRM'ga kiritish",
                role=Role.HUNTER,
                order=4,
                estimated_time=30,
                blocked_until="h_3",
                crm_stage_id=53729371,
            ),
            WorkflowStep(
                id="h_5",
                name="Kunlik hisobot",
                description="Direktorga natijalar haqida hisobot",
                role=Role.HUNTER,
                order=5,
                estimated_time=15,
                blocked_until="h_4",
                requires_approval=True,
                approver_role=Role.DIRECTOR,
            ),
        ]

        # SETTER workflow - Uchrashuv belgilash
        self.workflows["setter_daily"] = [
            WorkflowStep(
                id="s_1",
                name="Kvalifikatsiya tekshirish",
                description="CRM'dagi leadlarni saralash (qualified vs unqualified)",
                role=Role.SETTER,
                order=1,
                estimated_time=30,
                crm_pipeline_id="setter",
            ),
            WorkflowStep(
                id="s_2",
                name="Qo'ng'iroq qilish",
                description="15 ta qualified leadga qo'ng'iroq qilish",
                role=Role.SETTER,
                order=2,
                estimated_time=90,
                blocked_until="s_1",
            ),
            WorkflowStep(
                id="s_3",
                name="Uchrashuv belgilash",
                description="Kamida 3 ta uchrashuv (strategy session) belgilash",
                role=Role.SETTER,
                order=3,
                estimated_time=60,
                blocked_until="s_2",
                crm_stage_id=142,
            ),
            WorkflowStep(
                id="s_4",
                name="Kalendar tasdiqlash",
                description="Uchrashuvlarni kalendar'ga qo'shish va tasdiqlash",
                role=Role.SETTER,
                order=4,
                estimated_time=15,
                blocked_until="s_3",
            ),
            WorkflowStep(
                id="s_5",
                name="Eslatma yuborish",
                description="Mijozlarga uchrashuv eslatmasi yuborish",
                role=Role.SETTER,
                order=5,
                estimated_time=15,
                blocked_until="s_4",
                crm_stage_id=143,
            ),
        ]

        # CLOSER workflow - Bitim yopish
        self.workflows["closer_meeting"] = [
            WorkflowStep(
                id="c_1",
                name="Tayyorgarlik",
                description="Mijoz haqida research qilish (sayti, ijtimoiy tarmoqlari)",
                role=Role.CLOSER,
                order=1,
                estimated_time=30,
            ),
            WorkflowStep(
                id="c_2",
                name="Portfolio tayyorlash",
                description="Mos portfolio cases'ni tanlash",
                role=Role.CLOSER,
                order=2,
                estimated_time=20,
                blocked_until="c_1",
            ),
            WorkflowStep(
                id="c_3",
                name="Strategy Session",
                description="Uchrashuv o'tkazish (60 daqiqa)",
                role=Role.CLOSER,
                order=3,
                estimated_time=60,
                blocked_until="c_2",
                crm_stage_id=53729384,
            ),
            WorkflowStep(
                id="c_4",
                name="Taklif yuborish",
                description="Kommersiya taklifi (proposal) yuborish",
                role=Role.CLOSER,
                order=4,
                estimated_time=45,
                blocked_until="c_3",
                crm_stage_id=53729385,
            ),
            WorkflowStep(
                id="c_5",
                name="Follow-up",
                description="24 soat ichida follow-up qilish",
                role=Role.CLOSER,
                order=5,
                estimated_time=15,
                blocked_until="c_4",
                crm_stage_id=53729386,
            ),
            WorkflowStep(
                id="c_6",
                name="Bitim yopish",
                description="Shartnoma imzolash va avans olish",
                role=Role.CLOSER,
                order=6,
                estimated_time=30,
                blocked_until="c_5",
                crm_stage_id=53729390,
                requires_approval=True,
                approver_role=Role.DIRECTOR,
            ),
        ]

        # PROJECT MANAGER workflow
        self.workflows["pm_daily"] = [
            WorkflowStep(
                id="pm_1",
                name="Kunlik stand-up",
                description="Jamoa bilan qisqa stand-up (15 daqiqa)",
                role=Role.PROJECT_MANAGER,
                order=1,
                estimated_time=15,
            ),
            WorkflowStep(
                id="pm_2",
                name="Tasklarni tekshirish",
                description="Barcha loyiha tasklarini ko'rib chiqish",
                role=Role.PROJECT_MANAGER,
                order=2,
                estimated_time=30,
                blocked_until="pm_1",
            ),
            WorkflowStep(
                id="pm_3",
                name="Mijoz bilan aloqa",
                description="Aktiv loyiha mijozlari bilan status update",
                role=Role.PROJECT_MANAGER,
                order=3,
                estimated_time=45,
                blocked_until="pm_2",
            ),
            WorkflowStep(
                id="pm_4",
                name="Jadval yangilash",
                description="Timeline va deadline'larni yangilash",
                role=Role.PROJECT_MANAGER,
                order=4,
                estimated_time=20,
                blocked_until="pm_3",
            ),
            WorkflowStep(
                id="pm_5",
                name="Hisobot",
                description="Direktorga loyiha statusi hisobot",
                role=Role.PROJECT_MANAGER,
                order=5,
                estimated_time=15,
                blocked_until="pm_4",
            ),
        ]

        # DESIGNER workflow
        self.workflows["designer_task"] = [
            WorkflowStep(
                id="d_1",
                name="Brief olish",
                description="PM'dan dizayn briefini olish va tushunish",
                role=Role.DESIGNER,
                order=1,
                estimated_time=20,
            ),
            WorkflowStep(
                id="d_2",
                name="Research",
                description="Mijoz sohasi va raqobatchilarni tadqiq qilish",
                role=Role.DESIGNER,
                order=2,
                estimated_time=60,
                blocked_until="d_1",
            ),
            WorkflowStep(
                id="d_3",
                name="Moodboard",
                description="3 ta turli konsepsiya uchun moodboard",
                role=Role.DESIGNER,
                order=3,
                estimated_time=90,
                blocked_until="d_2",
            ),
            WorkflowStep(
                id="d_4",
                name="Konsepsiya",
                description="3 ta turli dizayn konsepsiyasi",
                role=Role.DESIGNER,
                order=4,
                estimated_time=240,
                blocked_until="d_3",
            ),
            WorkflowStep(
                id="d_5",
                name="Tasdiqlash",
                description="Mijoz va PM'dan tasdiqlash olish",
                role=Role.DESIGNER,
                order=5,
                estimated_time=30,
                blocked_until="d_4",
                requires_approval=True,
                approver_role=Role.PROJECT_MANAGER,
            ),
            WorkflowStep(
                id="d_6",
                name="Finalization",
                description="Yakuniy dizayn tayyorlash",
                role=Role.DESIGNER,
                order=6,
                estimated_time=180,
                blocked_until="d_5",
            ),
            WorkflowStep(
                id="d_7",
                name="Handoff",
                description="Dasturchiga yoki mijozga topshirish",
                role=Role.DESIGNER,
                order=7,
                estimated_time=30,
                blocked_until="d_6",
            ),
        ]

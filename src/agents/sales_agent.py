import asyncio
import json
import logging
import os
import re
from datetime import timedelta
from typing import Any, Dict, List, Optional

from .core import BaseAgent
from .negotiation_engine import NegotiationEngine
from .negotiation_reengagement import NegotiationReengagementPlanner
from .negotiation_verifier import NegotiationOutcomeVerifier
from .persona_router import PersonaRouter
from src.time_utils import get_local_now

# Escalation safety-net — auto_reply_gate'dagi trigger list bilan bir xil.
# (Gate main.py entry'da filtrlaydi, bu yerda ikkinchi qatlam himoya.)
try:
    from src.services.core.auto_reply_gate import ESCALATION_TRIGGERS
except Exception:  # pragma: no cover — agar modul yo'q bo'lsa (unit test uchun)
    ESCALATION_TRIGGERS = (
        "shikoyat",
        "qaytarish",
        "advokat",
        "sud",
        "vaqtida bermadi",
        "aldadi",
        "firibgar",
        "qaytarib bering",
    )

# Agar assessment.close_probability shu qiymatdan past bo'lsa — admin review.
ESCALATION_CLOSE_PROB_THRESHOLD = 0.30
# Shu risk flag'lardan birortasi bo'lsa — majburiy admin review.
ESCALATION_RISK_FLAGS = {"legal_review", "competitive_pressure", "negative_sentiment"}

logger = logging.getLogger(__name__)


class SalesAgent(BaseAgent):
    """Autonomous negotiation-capable sales agent."""

    def __init__(
        self,
        agent_id: str,
        system_prompt: str,
        api_keys: Dict[str, str],
        executor: Optional[Any] = None,
        db: Optional[Any] = None,
    ):
        super().__init__(agent_id, system_prompt, api_keys, executor, db)
        self.products = self._load_products()
        self.verifier = NegotiationOutcomeVerifier()

    def _load_products(self) -> Dict[str, Any]:
        path = os.path.join("data", "agency_products.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"[SALES AGENT] KB yuklashda xato: {e}")
        return {}

    async def _get_negotiation_mode(self) -> str:
        if self.db and hasattr(self.db, "get_state"):
            try:
                raw = await self.db.get_state("policy:negotiation_mode", "autonomous")
                normalized = str(raw or "autonomous").strip().lower()
                if normalized in {"advisory", "supervised", "autonomous"}:
                    return normalized
            except Exception as e:
                logger.error(f"[SALES AGENT] negotiation mode read error: {e}")
        return "autonomous"

    async def _log_assessment(
        self, user_id: int, payload: Dict[str, Any], success: bool = True
    ) -> None:
        if self.db and hasattr(self.db, "log_agent_action"):
            try:
                await self.db.log_agent_action(
                    user_id, "negotiation_assessment", payload, success=success
                )
            except Exception as e:
                logger.error(f"[SALES AGENT] assessment log error: {e}")

    def _extract_meeting_window(self, text: str) -> Optional[Dict[str, str]]:
        lowered = (text or "").lower()
        if not any(
            word in lowered
            for word in [
                "uchrashuv",
                "qo'ng'iroq",
                "call",
                "zoom",
                "meeting",
                "sessiya",
            ]
        ):
            return None

        match = re.search(r"(\d{1,2})(?::(\d{2}))?", lowered)
        if not match:
            return None

        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        if hour > 23 or minute > 59:
            return None

        target = get_local_now()
        if "ertaga" in lowered:
            target = target + timedelta(days=1)
        elif "indin" in lowered:
            target = target + timedelta(days=2)

        start_dt = target.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if start_dt < get_local_now() and "bugun" in lowered:
            start_dt = start_dt + timedelta(days=1)
        end_dt = start_dt + timedelta(hours=1)
        return {
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
        }

    async def _sync_meeting_state(
        self, user_id: int, meeting_window: Optional[Dict[str, str]]
    ) -> None:
        if not self.db:
            return
        if meeting_window and hasattr(self.db, "upsert_user"):
            try:
                await self.db.upsert_user(
                    user_id,
                    "Unknown",
                    meeting_time=meeting_window["start_time"],
                    meeting_status="scheduled",
                )
            except Exception as e:
                logger.error(f"[SALES AGENT] meeting state sync error: {e}")

    def _fallback_reply(self, assessment, task_description: str) -> str:
        if assessment.intent == "meeting":
            return (
                "Zo'r, strategik sessiyani belgilab olaylik. "
                "Uchrashuvda maqsad, scope va sizga eng to'g'ri yechimni birga aniqlab chiqamiz. "
                "Agar qulay bo'lsa, shu vaqtni final tasdiqlab ketamiz."
            )
        if assessment.objection == "price":
            return (
                "Narx masalasi tabiiy savol. Biz faqat deliverable emas, biznesga ta'sir qiladigan natija va pozitsiyalash ustida ishlaymiz. "
                "Agar xohlasangiz, sizga aynan ehtiyojingizga mos scope va qiymatni qisqa qilib ajratib beraman."
            )
        if assessment.objection == "trust":
            return (
                "To'g'ri, qaror uchun ishonch muhim. "
                "Biz sizga process qanday ketishi, qaysi bosqichlarda natija berishimiz va sizga mos кейslar bilan tushuntirib beramiz. "
                "Xohlasangiz, keyingi xabarda aynan sizning yo'nalishingizga mos misollarni yuboraman."
            )
        if assessment.intent == "closing":
            return (
                "Ajoyib. Keyingi qadam sifatida scope, muddat va start nuqtani aniq qilib yopamiz. "
                "Shundan keyin ishni tez boshlashimiz mumkin."
            )
        return (
            "Tushundim. Sizga eng to'g'ri yechimni tavsiya qilish uchun ehtiyoj, ustuvor natija va muddatni aniq qilib olaylik. "
            "Shunda sizga mos eng samarali next stepni belgilab beraman."
        )

    def _build_lead_note(
        self,
        user_id: int,
        task_description: str,
        context: Dict[str, Any],
        assessment,
        next_step: str,
    ) -> str:
        service_type = (
            context.get("service_type")
            or context.get("user_profile", {}).get("service_type")
            or "Aniqlanmagan"
        )
        crm_status = context.get("crm_status") or "Yangi mijoz"
        excerpt = (task_description or "").strip().replace("\n", " ")
        excerpt = excerpt[:220]
        return (
            "AI negotiation update.\n"
            f"- user_id: {user_id}\n"
            f"- crm_status: {crm_status}\n"
            f"- service_type: {service_type}\n"
            f"- stage: {assessment.stage}\n"
            f"- intent: {assessment.intent}\n"
            f"- objection: {assessment.objection}\n"
            f"- close_probability: {assessment.close_probability}\n"
            f"- last_message: {excerpt}\n"
            f"- next_step: {next_step}"
        )

    def _build_followup_payload(
        self,
        user_id: int,
        user_name: str,
        assessment,
        crm_status: str,
    ) -> Optional[Dict[str, Any]]:
        crm_lower = (crm_status or "").lower()

        if assessment.next_action == "create_followup_commitment":
            due_in_hours = 48 if assessment.urgency == "low" else 24
            return {
                "user_id": user_id,
                "title": f"Follow-up: {user_name} bilan qaror sanasini mahkamlash",
                "details": "Mijoz nurture holatida. Qaror sanasi yoki mini-callni aniq qilib yoping.",
                "due_in_hours": due_in_hours,
            }

        if assessment.intent == "closing":
            return {
                "user_id": user_id,
                "title": f"Closer: {user_name} bilan startni yopish",
                "details": "Scope, start sanasi yoki to'lov bo'yicha yakuniy next stepni mahkamlang.",
                "due_in_hours": 6 if assessment.urgency == "high" else 12,
            }

        if assessment.objection in {"price", "trust", "competition"}:
            objection_map = {
                "price": "Qiymatni qayta asoslab, scope yoki meeting variantini taklif qiling.",
                "trust": "Case, process yoki social proof bilan ishonchni mustahkamlang.",
                "competition": "Raqobatchidan farqni aniq aytib, keyingi qadamni yopishga harakat qiling.",
            }
            return {
                "user_id": user_id,
                "title": f"Objection follow-up: {user_name}",
                "details": objection_map[assessment.objection],
                "due_in_hours": 12 if assessment.urgency == "high" else 24,
            }

        if "meeting" in crm_lower and assessment.close_probability >= 0.6:
            return {
                "user_id": user_id,
                "title": f"Closer follow-up: {user_name}",
                "details": "Meetingdan keyingi commercial next stepni yoki to'lov/start signalini yoping.",
                "due_in_hours": 8,
            }

        return None

    async def _build_action_plan(
        self,
        user_id: int,
        task_description: str,
        context: Dict[str, Any],
        assessment,
    ) -> List[Dict[str, Any]]:
        if (
            not self.executor
            or assessment.approval_needed
            or assessment.autonomy_mode == "advisory"
        ):
            return []

        actions: List[Dict[str, Any]] = []
        meeting_window = self._extract_meeting_window(task_description)
        recommended_status = assessment.recommended_status
        user_name = context.get("user_name") or f"User {user_id}"
        service_type = context.get("service_type") or context.get(
            "user_profile", {}
        ).get("service_type")
        crm_status = str(context.get("crm_status") or "")
        crm_lower = crm_status.lower()
        note_next_step = "Negotiation keyingi bosqichga olib chiqilmoqda."

        if meeting_window:
            summary = f"Strategik sessiya - {user_name}"
            description = (
                "AI negotiation agent tomonidan meeting scheduling trigger qilindi."
            )
            if service_type:
                description += f" Xizmat: {service_type}."
            actions.append(
                {
                    "name": "create_calendar_event",
                    "args": {
                        "summary": summary,
                        "start_time": meeting_window["start_time"],
                        "end_time": meeting_window["end_time"],
                        "description": description,
                    },
                }
            )
            actions.append(
                {
                    "name": "update_lead_status",
                    "args": {"user_id": user_id, "status_name": "Meeting Scheduled"},
                }
            )
            note_next_step = (
                f"Strategik sessiya {meeting_window['start_time']} ga belgilandi."
            )
            actions.append(
                {
                    "name": "create_followup_task",
                    "args": {
                        "user_id": user_id,
                        "title": f"Closer prep: {user_name}",
                        "details": "Strategik sessiyadan oldin brief, scope va keyingi taklifni tayyorlang.",
                        "due_at": meeting_window["start_time"],
                    },
                }
            )
        elif recommended_status in {"Interested", "Qualified"}:
            actions.append(
                {
                    "name": "update_lead_status",
                    "args": {"user_id": user_id, "status_name": recommended_status},
                }
            )
            note_next_step = f"CRM status {recommended_status} ga ko'tarildi."

        if not meeting_window:
            followup_payload = self._build_followup_payload(
                user_id, user_name, assessment, crm_status
            )
            if followup_payload:
                note_next_step = followup_payload["details"]
                actions.append(
                    {"name": "create_followup_task", "args": followup_payload}
                )

        if assessment.intent == "closing" and any(
            token in crm_lower
            for token in ["meeting", "sessiya", "strategik", "consult"]
        ):
            actions.append(
                {
                    "name": "update_lead_status",
                    "args": {"user_id": user_id, "status_name": "Conversation Over"},
                }
            )
            note_next_step = "Closer pipeline ga o'tkazildi va yakuniy commercial follow-up belgilandi."

        if assessment.close_probability >= 0.65 and service_type:
            actions.append(
                {
                    "name": "qualify_lead",
                    "args": {
                        "user_id": user_id,
                        "service": (
                            service_type
                            if service_type
                            in {"Naming", "Logo", "Brandbook", "Web", "SMM"}
                            else None
                        ),
                        "temperature": "Issiq",
                        "need": task_description[:240],
                        "tag": "Negotiation-Active",
                    },
                }
            )

        should_write_note = (
            bool(actions)
            or assessment.close_probability >= 0.45
            or assessment.intent in {"pricing", "proof", "nurture", "closing"}
        )
        if should_write_note:
            actions.append(
                {
                    "name": "add_lead_note",
                    "args": {
                        "user_id": user_id,
                        "note": self._build_lead_note(
                            user_id,
                            task_description,
                            context,
                            assessment,
                            note_next_step,
                        ),
                    },
                }
            )

        filtered_actions: List[Dict[str, Any]] = []
        seen_signatures = set()
        for action in actions:
            args = action["args"]
            if not all(v is not None for v in args.values()):
                continue
            signature = (action["name"], tuple(sorted(args.items())))
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            filtered_actions.append(action)
        return filtered_actions

    async def _execute_actions(
        self, user_id: Optional[int], actions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        if not self.executor:
            return results

        for action in actions:
            result = await self.executor.execute(
                action["name"], action["args"], context_user_id=user_id
            )
            results.append(
                {
                    "action": action["name"],
                    "args": action["args"],
                    **result,
                }
            )
        return results

    async def plan_reengagement_targets(self, limit: int = 20) -> List[Dict[str, Any]]:
        if not self.executor or not getattr(self.executor, "amocrm", None):
            return []

        raw_leads = await asyncio.to_thread(
            self.executor.amocrm.get_all_leads, max(limit * 4, 100)
        )
        candidates = NegotiationReengagementPlanner.plan(raw_leads, limit=limit)
        return [candidate.to_payload() for candidate in candidates]

    async def run_reengagement_cycle(self, limit: int = 10) -> List[Dict[str, Any]]:
        if not self.executor or not getattr(self.executor, "amocrm", None):
            return []

        raw_leads = await asyncio.to_thread(
            self.executor.amocrm.get_all_leads, max(limit * 4, 100)
        )
        candidates = NegotiationReengagementPlanner.plan(raw_leads, limit=limit)
        cycle_results: List[Dict[str, Any]] = []

        for candidate in candidates:
            action_plan = [
                {
                    "name": "create_followup_task",
                    "args": {
                        "lead_id": candidate.lead_id,
                        "title": candidate.task_title,
                        "details": candidate.task_details,
                        "due_in_hours": candidate.due_in_hours,
                    },
                },
                {
                    "name": "add_lead_note",
                    "args": {
                        "lead_id": candidate.lead_id,
                        "note": candidate.note,
                    },
                },
            ]
            action_results = await self._execute_actions(None, action_plan)
            verification = self.verifier.verify(
                action_results, planned_actions=action_plan
            )
            payload = {
                "candidate": candidate.to_payload(),
                "action_plan": action_plan,
                "action_results": action_results,
                "verification": verification.to_payload(),
            }
            cycle_results.append(payload)

            if self.db and hasattr(self.db, "log_agent_action"):
                try:
                    await self.db.log_agent_action(
                        None,
                        "negotiation_reengagement_cycle",
                        payload,
                        success=verification.success,
                    )
                except Exception as e:
                    logger.error(f"[SALES AGENT] re-engagement log error: {e}")

        return cycle_results

    async def review_conversation(
        self,
        user_id: int,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
        *,
        execute_actions: bool = True,
    ) -> Dict[str, Any]:
        """
        Deterministic lead review path for 24/7 pipeline control.
        It does not depend on an LLM reply to classify stage or trigger CRM actions.
        """
        context = context or {}
        await self.load_session_history(user_id)

        history = self.get_session_history(user_id)
        crm_status = str(context.get("crm_status") or "Yangi mijoz")
        autonomy_mode = await self._get_negotiation_mode()
        assessment = NegotiationEngine.assess(
            task_description,
            crm_status,
            autonomy_mode=autonomy_mode,
            history=history,
            context=context,
        )

        action_plan = await self._build_action_plan(
            user_id, task_description, context, assessment
        )
        action_results: List[Dict[str, Any]] = []
        if execute_actions and action_plan:
            action_results = await self._execute_actions(user_id, action_plan)

        verification = self.verifier.verify(action_results, planned_actions=action_plan)
        recommended_reply = self._fallback_reply(assessment, task_description)

        payload = {
            "user_id": user_id,
            "crm_status": crm_status,
            "assessment": assessment.to_payload(),
            "action_plan": action_plan,
            "action_results": action_results,
            "verification": verification.to_payload(),
            "recommended_reply": recommended_reply,
        }
        await self._log_assessment(
            user_id, payload, success=verification.success or not action_plan
        )
        return payload

    def _detect_escalation(
        self, task_description: str, assessment: Any
    ) -> Optional[str]:
        """Xavfli vaziyatlarni aniqlash — admin review'ga belgilash uchun.

        Return: sabab (str) yoki None. Bu metod reply generatsiyasini to'xtatmaydi;
        u faqat log + flag qo'yadi. Yakuniy yuborish qarori main.py'dagi gate'da.
        """
        text = (task_description or "").lower()
        for trigger in ESCALATION_TRIGGERS:
            if trigger in text:
                return f"trigger_word:{trigger}"
        try:
            prob = float(getattr(assessment, "close_probability", 1.0))
        except (TypeError, ValueError):
            prob = 1.0
        if prob < ESCALATION_CLOSE_PROB_THRESHOLD:
            return f"low_close_prob:{prob:.2f}"
        risk_flags = set(getattr(assessment, "risk_flags", []) or [])
        matched = risk_flags & ESCALATION_RISK_FLAGS
        if matched:
            return f"risk_flag:{','.join(sorted(matched))}"
        return None

    async def process_task(
        self,
        user_id: int,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        context = context or {}
        await self.load_session_history(user_id)
        self.update_history(user_id, "user", task_description)

        history = self.get_session_history(user_id)
        crm_status = str(context.get("crm_status") or "Yangi mijoz")
        autonomy_mode = await self._get_negotiation_mode()
        assessment = NegotiationEngine.assess(
            task_description,
            crm_status,
            autonomy_mode=autonomy_mode,
            history=history,
            context=context,
        )
        await self._log_assessment(
            user_id,
            {
                "user_id": user_id,
                "crm_status": crm_status,
                "message": task_description,
                "assessment": assessment.to_payload(),
            },
        )

        # Escalation check — log + flag, pipeline davom etadi (reply hali ham generatsiya bo'ladi,
        # lekin main.py'dagi gate va admin review shadow mode'da uni bloklashi mumkin).
        escalation_reason = self._detect_escalation(task_description, assessment)
        if escalation_reason and self.db and hasattr(self.db, "log_agent_action"):
            try:
                await self.db.log_agent_action(
                    user_id,
                    "escalation_flagged",
                    {
                        "user_id": user_id,
                        "reason": escalation_reason,
                        "message": task_description[:500],
                        "close_probability": getattr(
                            assessment, "close_probability", None
                        ),
                        "risk_flags": list(getattr(assessment, "risk_flags", []) or []),
                    },
                    success=False,  # False = diqqat kerakligini bildiradi
                )
                logger.warning(
                    f"[SALES AGENT] Escalation flagged user={user_id} reason={escalation_reason}"
                )
            except Exception as e:
                logger.error(f"[SALES AGENT] escalation log error: {e}")

        products_context = json.dumps(self.products, indent=2, ensure_ascii=False)
        history_text = "\n".join(
            f"{item['role']}: {item['content']}" for item in history[-8:]
        )
        context_json = json.dumps(context, ensure_ascii=False)

        approval_instruction = ""
        if assessment.approval_needed:
            approval_instruction = (
                "\n[SAFETY GATE]\n"
                "Bu vaziyat yuqori riskli. Chegirma, yuridik majburiyat, agressiv va'da yoki raqobatchi bilan qattiq taqqoslashga KIRMANG. "
                "Mijozga xavfsiz, professionallik bilan bridge-reply bering va keyingi aniq qadamni taklif qiling."
            )

        mode_instruction = {
            "advisory": "Javobingizni menejer uchun ichki tavsiya shaklida yozing. Lekin mijozga yuborilsa ham uyat bo'lmaydigan muloyim uslubdan chiqmang.",
            "supervised": "Client-safe reply yozing, lekin agressiv close qilmang. Bitta aniq next step bering va kerak bo'lsa strategik sessiyani taklif qiling.",
            "autonomous": "Mijozga to'g'ridan-to'g'ri client-ready reply yozing. Savdoni konsultativ tarzda oldinga suring va bitta aniq next stepga olib boring.",
        }.get(autonomy_mode, "Client-safe reply yozing.")

        sales_instruction = f"""
Siz Jon.Branding uchun autonomous negotiation sales agentisiz.

Maqsad:
- mijozni tushunish
- ehtiyojni aniqlashtirish
- e'tirozni yumshatish
- suhbatni keyingi bosqichga olib o'tish
- imkon qadar strategik sessiya yoki aniq commercial next stepga olib borish

Negotation plan:
- stage: {assessment.stage}
- intent: {assessment.intent}
- objection: {assessment.objection}
- urgency: {assessment.urgency}
- sentiment: {assessment.sentiment}
- close_probability: {assessment.close_probability}
- recommended_status: {assessment.recommended_status}
- next_action: {assessment.next_action}
- autonomy_mode: {assessment.autonomy_mode}
- risk_flags: {", ".join(assessment.risk_flags) if assessment.risk_flags else "none"}

Qoidalar:
- O'zbek tilida yozing.
- Reply client-ready bo'lsin.
- Ortiqcha uzun yozmang.
- Narx yoki scope bo'yicha aniq ma'lumot products_contextda bo'lmasa, to'qib chiqarmang.
- 1 ta aniq keyingi qadam bilan yakunlang.
- Agar mijoz narxdan shubhalansa, faqat narxni emas, qiymat va natijani frame qiling.
- Agar mijoz ishonch qidirmoqda bo'lsa, relevant case yoki processga tayaning.
- Agar mijoz meetingga yaqin bo'lsa, vaqt variantini taklif qiling.
- Agar approval_needed bo'lsa, xavfli commitment bermang.

{mode_instruction}
{approval_instruction}

Products knowledge:
{products_context}

Context:
{context_json}
{PersonaRouter.route(task_description, assessment.intent, "sales")}

Bot-to-Bot & Guest Rules:
- Agar is_bot: True bo'lsa, suhbatdosh - boshqa bir AI agenti. Juda aniq, texnik, strukturaviy va professional gaplashing. Ortiqcha emotsiyaga berilmang, lekin hamkorlikka ochiqlikni ko'rsating.
- Agar is_guest: True bo'lsa, bu yangi foydalanuvchi. Uni samimiy qarshilang, JonBranding imkoniyatlarini qisqa va londa tushuntiring.
"""

        contents = [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            f"CRM status: {crm_status}\n"
                            f"Suhbat tarixi:\n{history_text}\n\n"
                            f"Yangi xabar: {task_description}\n\n"
                            "Negotiation plan asosida eng yaxshi keyingi javobni yozing."
                        )
                    }
                ],
            }
        ]

        original_prompt = self.system_prompt
        self.system_prompt = f"{original_prompt}\n\n{sales_instruction}"
        try:
            reply = await self.call_ai_with_fallback(
                contents, user_id, enable_tools=False
            )
        finally:
            self.system_prompt = original_prompt

        if not reply or reply in {
            "Javob bo'sh qaytdi.",
            "Kechirasiz, texnik tanaffus.",
        }:
            reply = self._fallback_reply(assessment, task_description)

        action_plan = await self._build_action_plan(
            user_id, task_description, context, assessment
        )
        action_results = await self._execute_actions(user_id, action_plan)
        meeting_window = self._extract_meeting_window(task_description)
        if meeting_window:
            await self._sync_meeting_state(user_id, meeting_window)
        verification = self.verifier.verify(
            action_results,
            resulting_status=assessment.recommended_status,
            planned_actions=action_plan,
        )

        self.update_history(user_id, "assistant", reply)
        if self.db and hasattr(self.db, "log_agent_action"):
            try:
                await self.db.log_agent_action(
                    user_id,
                    "negotiation_reply_generated",
                    {
                        "user_id": user_id,
                        "assessment": assessment.to_payload(),
                        "reply": reply,
                        "autonomy_mode": autonomy_mode,
                        "action_plan": action_plan,
                        "action_results": action_results,
                    },
                    success=not assessment.approval_needed,
                )
                await self.db.log_agent_action(
                    user_id,
                    "negotiation_verification",
                    verification.to_payload(),
                    success=verification.success,
                )
            except Exception as e:
                logger.error(f"[SALES AGENT] reply log error: {e}")

        return reply

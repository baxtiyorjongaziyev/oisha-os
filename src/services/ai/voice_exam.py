"""AI Voice Exam and Sales Simulation Engine.

Enables sales representatives to undergo automated voice or text roleplay examinations
against realistic client personas with standard multi-criteria grading rubric.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class VoiceExamCriterion:
    """Evaluation criterion with weighting for sales exam."""

    criterion_id: str
    name: str
    weight: int  # out of 100
    description: str


@dataclass
class VoiceExamScenario:
    """Preconfigured scenario for sales qualification examination."""

    scenario_id: str
    title: str
    client_name: str
    client_gender: str
    industry: str
    difficulty: str  # "easy", "medium", "hard"
    primary_objection: str
    client_prompt: str


@dataclass
class ExamTurn:
    """Single dialogue turn during voice examination."""

    speaker: str  # "manager" or "client"
    text: str
    timestamp: str


@dataclass
class VoiceExamSession:
    """Stateful record of an ongoing or completed voice exam session."""

    session_id: str
    manager_id: str
    scenario_id: str
    status: str = "pending"  # "pending", "active", "completed"
    turns: List[ExamTurn] = field(default_factory=list)
    criterion_scores: Dict[str, int] = field(default_factory=dict)
    overall_score: int = 0
    passed: bool = False
    feedback: str = ""
    certificate_id: Optional[str] = None


class VoiceExamEngine:
    """Core evaluation engine for sales voice roleplay examination."""

    RUBRIC: List[VoiceExamCriterion] = [
        VoiceExamCriterion("greeting", "Salomlashish va kontakt", 15, "Ism bilan murojaat, professional salomlashish"),
        VoiceExamCriterion("discovery", "Ehtiyojni aniqlash — SOPRANO", 25, "Ochiq savollar berish va asosiy ogʻriqni topish"),
        VoiceExamCriterion("presentation", "Taqdimot va foyda", 20, "Mijoz ehtiyojiga mos aniq qiymat koʻrsatish"),
        VoiceExamCriterion("objections", "Eʼtirozlarni yopish", 25, "Narx va vaqt eʼtirozlariga argumentli javob"),
        VoiceExamCriterion("closing", "Yakunlash va keyingi qadam", 15, "Aniq toʻlov yoki uchrashuv sanasini kelishish"),
    ]

    SCENARIOS: Dict[str, VoiceExamScenario] = {
        "pre_sale_1": VoiceExamScenario(
            scenario_id="pre_sale_1",
            title="Pre Sale (1-qoʻngʻiroq) B2B Imtihon",
            client_name="Bobur Alimov",
            client_gender="male",
            industry="Distribyutsiya",
            difficulty="medium",
            primary_objection="Qimmat, hozir byudjet yoʻq",
            client_prompt="Siz band tadbirkorsiz, vaqtingiz kam va taklifga shubha bilan qaraysiz.",
        ),
        "closing_meeting": VoiceExamScenario(
            scenario_id="closing_meeting",
            title="Bitimni yopish va toʻlov sanasi",
            client_name="Dilnoza Ergasheva",
            client_gender="female",
            industry="Chakana savdo",
            difficulty="hard",
            primary_objection="Boshqa kompaniya arzonroq taklif qildi",
            client_prompt="Siz raqobatchi bilan solishtiryapsiz va chegirma talab qilasiz.",
        ),
    }

    def get_scenarios(self) -> List[VoiceExamScenario]:
        """Return all available exam scenarios."""
        return list(self.SCENARIOS.values())

    def start_exam(self, manager_id: str, scenario_id: str) -> VoiceExamSession:
        """Start a new interactive exam session."""
        scenario = self.SCENARIOS.get(scenario_id)
        if not scenario:
            scenario = list(self.SCENARIOS.values())[0]

        now_str = datetime.now(timezone.utc).isoformat()
        first_turn = ExamTurn(
            speaker="client",
            text=f"Assalomu alaykum. Men {scenario.client_name}man. Qulogʻim sizda, nima masala boʻyicha telefon qildingiz?",
            timestamp=now_str,
        )

        return VoiceExamSession(
            session_id=f"exam_{manager_id}_{int(datetime.now(timezone.utc).timestamp())}",
            manager_id=manager_id,
            scenario_id=scenario.scenario_id,
            status="active",
            turns=[first_turn],
        )

    def process_turn(self, session: VoiceExamSession, manager_text: str) -> Dict[str, Any]:
        """Process manager verbal/text input and return realistic client response."""
        now_str = datetime.now(timezone.utc).isoformat()
        session.turns.append(ExamTurn(speaker="manager", text=manager_text, timestamp=now_str))

        scenario = self.SCENARIOS.get(session.scenario_id, list(self.SCENARIOS.values())[0])
        msg_lower = manager_text.lower()

        # Dynamic customer reaction logic
        if any(kw in msg_lower for kw in ["qimmat", "narx", "chegirma", "budjet", "byudjet"]):
            client_reply = (
                f"Toʻgʻrisini aytsam, narxingiz ancha baland. {scenario.primary_objection}. "
                "Qanday qilib bu xarajat oʻzini oqlashini kafolatlaysiz?"
            )
        elif any(kw in msg_lower for kw in ["savol", "qanday", "nega", "jarayon", "muammo", "maqsad"]):
            client_reply = (
                "Bizda asosiy muammo — xodimlar sotuvni yaxshi yopolmayapti va hisobotlar kechikmoqda. "
                "Sizning tizim buni qanday hal qiladi?"
            )
        elif any(kw in msg_lower for kw in ["uchrashuv", "shartnoma", "toʻlov", "ertaga", "soat", "kelishamiz"]):
            client_reply = (
                "Taklifingiz qiziq. Ertaga soat 15:00 da Zoom orqali batafsil koʻrsatsangiz, maʼqul keladi."
            )
        else:
            client_reply = "Tushunarli. Aniqroq tushuntirib bera olasizmi, bu bizga qanday foyda keltiradi?"

        client_turn = ExamTurn(speaker="client", text=client_reply, timestamp=now_str)
        session.turns.append(client_turn)

        return {
            "session_id": session.session_id,
            "client_response": client_reply,
            "turns_count": len(session.turns),
        }

    def finalize_exam(self, session: VoiceExamSession) -> VoiceExamSession:
        """Grade session across the 5 evaluation criteria and issue certificate if passed."""
        manager_texts = " ".join(t.text.lower() for t in session.turns if t.speaker == "manager")

        # Rubric grading heuristics
        scores: Dict[str, int] = {}

        # 1. Greeting
        has_greeting = any(kw in manager_texts for kw in ["assalomu", "salom", "xayrli", "tanishganimdan"])
        scores["greeting"] = 15 if has_greeting else 7

        # 2. Need Discovery (SOPRANO)
        discovery_count = sum(1 for kw in ["qanday", "nega", "qaysi", "maqsad", "ehtiyoj", "muammo"] if kw in manager_texts)
        scores["discovery"] = min(25, 10 + (discovery_count * 3))

        # 3. Presentation & Value
        presentation_count = sum(1 for kw in ["natija", "foyda", "yechim", "avtomat", "oshirish", "yordam"] if kw in manager_texts)
        scores["presentation"] = min(20, 8 + (presentation_count * 3))

        # 4. Objection Handling
        has_obj = any(kw in manager_texts for kw in ["narx", "qiymat", "kafolat", "investitsiya", "qaytadi", "qulay"])
        scores["objections"] = 23 if has_obj else 12

        # 5. Closing
        has_closing = any(kw in manager_texts for kw in ["ertaga", "uchrashuv", "shartnoma", "toʻlov", "soat", "kelish"])
        scores["closing"] = 15 if has_closing else 5

        overall = sum(scores.values())
        passed = overall >= 70

        feedback = (
            f"Umumiy imtihon natijasi: {overall}/100 ball. "
            + ("Imtihondan muvaffaqiyatli oʻtdi!" if passed else "Imtihon topshirilmadi. Eʼtirozlar va yakunlash qismini qayta mashq qiling.")
        )

        session.status = "completed"
        session.criterion_scores = scores
        session.overall_score = overall
        session.passed = passed
        session.feedback = feedback
        if passed:
            session.certificate_id = f"CERT-GS-{session.manager_id[-4:]}-{overall}"

        return session

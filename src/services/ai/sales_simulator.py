"""AI Sales Practice Simulator Engine.

Allows sales representatives to conduct simulated sales roleplay sessions
with AI buyer personas, handles hidden facts revelation, and grades performance.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class SimulationScenario:
    """Predefined or custom sales coaching roleplay scenario."""

    scenario_id: str
    title: str
    goal: str
    situation: str
    client_name: str
    client_gender: str
    mood: str
    what_convinces: str
    hidden_facts: List[str] = field(default_factory=list)


@dataclass
class SimulationTurn:
    """A single turn in the simulation dialogue."""

    role: str
    content: str
    timestamp: Optional[datetime] = None


@dataclass
class TurnResult:
    """Result of processing a manager message in simulation."""

    client_response: str
    revealed_facts: List[str] = field(default_factory=list)
    coaching_tip: Optional[str] = None


@dataclass
class PracticeSessionEvaluation:
    """Comprehensive post-practice performance grading and feedback."""

    scenario_id: str
    overall_score: int
    active_listening: int
    need_discovery: int
    objection_handling: int
    next_step_agreement: bool
    strengths: List[str] = field(default_factory=list)
    weak_areas: List[str] = field(default_factory=list)
    coaching_feedback: str = ""


class SalesSimulatorEngine:
    """Core engine for AI buyer simulation and sales dialogue evaluation."""

    def __init__(self) -> None:
        """Initialize built-in scenarios tailored for Uzbek B2B and B2C sales."""
        self._built_in_scenarios: Dict[str, SimulationScenario] = self._init_scenarios()

    def get_scenarios(self) -> List[SimulationScenario]:
        """Return list of all available simulation training scenarios."""
        return list(self._built_in_scenarios.values())

    def get_scenario(self, scenario_id: str) -> Optional[SimulationScenario]:
        """Fetch a specific scenario by its identifier."""
        return self._built_in_scenarios.get(scenario_id)

    def process_manager_message(
        self,
        scenario: SimulationScenario,
        history: List[SimulationTurn],
        manager_message: str,
    ) -> TurnResult:
        """Process manager dialogue turn and generate contextual buyer response."""
        msg_lower = manager_message.lower()
        revealed: List[str] = []

        # Discovery trigger keywords indicating good qualification
        discovery_triggers = [
            "nega", "qanday", "oldin", "tajriba", "natija", "maqsad",
            "fikringiz", "qaysi", "qulay", "xohlaysiz", "ehtiyoj"
        ]
        is_discovery = any(kw in msg_lower for kw in discovery_triggers)

        if is_discovery and scenario.hidden_facts:
            revealed.append(scenario.hidden_facts[0])
            client_reply = (
                f"Toʻgʻrisini aytsam, {scenario.hidden_facts[0].lower()}. "
                f"Lekin baribir narx va natija menga juda muhim."
            )
            tip = "Ajoyib savol! Mijoz yashirin ehtiyojini ochiqladi."
        elif "narx" in msg_lower or "soʻm" in msg_lower or "dollar" in msg_lower:
            client_reply = (
                "Hali narxga kelishishdan oldin bu menga qanchalik mos kelishini bilmoqchiman. "
                "Nega aynan sizning taklifingizni tanlashim kerak?"
            )
            tip = "Narxni aytishdan oldin mijoz ehtiyojini chuqurroq aniqlang."
        else:
            client_reply = (
                "Tushundim, lekin hozir aniq bir qarorga kelishim qiyin. "
                "Menga batafsilroq maʼlumot bera olasizmi?"
            )
            tip = "Ochiq savollar berib, mijozning asosiy ogʻriqli nuqtasini toping."

        return TurnResult(
            client_response=client_reply,
            revealed_facts=revealed,
            coaching_tip=tip,
        )

    def evaluate_session(
        self, scenario_id: str, history: List[SimulationTurn]
    ) -> PracticeSessionEvaluation:
        """Evaluate completed simulation session and compute scores."""
        manager_turns = [t.content.lower() for t in history if t.role == "manager"]
        combined_text = " ".join(manager_turns)

        # 1. Active Listening Score
        active_score = 70
        if any(w in combined_text for w in ["tushunaman", "toʻgʻri", "haqiqatan", "albatta"]):
            active_score = 85

        # 2. Need Discovery Score
        discovery_score = 65
        if any(w in combined_text for w in ["qanday", "nega", "maqsad", "natija", "qachon"]):
            discovery_score = 80

        # 3. Objection Handling Score
        objection_score = 70
        if any(w in combined_text for w in ["afzallik", "kafolat", "farq", "imkoniyat"]):
            objection_score = 85

        # 4. Next Step Agreement
        next_step = any(
            w in combined_text for w in ["ertaga", "soat", "belgiladim", "uchrashuv", "kelishdik"]
        )

        overall = int((active_score + discovery_score + objection_score + (90 if next_step else 50)) / 4)

        strengths = ["Xushmuomala muloqot va professional ohang"]
        if next_step:
            strengths.append("Keyingi qadam va aniq vaqt boʻyicha kelishuvga erishildi")
        if active_score >= 80:
            strengths.append("Mijoz fikrini tinglash va tasdiqlash mahorati yuqori")

        weak_areas = []
        if discovery_score < 75:
            weak_areas.append("Ehtiyojni aniqlovchi ochiq savollar soni yetarli emas")
        if not next_step:
            weak_areas.append("Suhbat yakunida keyingi qadam aniq belgilanmadi")

        feedback = (
            f"Umumiy baho: {overall}/100. "
            f"Muloqot yaxshi oʻtdi. Keyingi mashqlarda narxga oʻtishdan oldin "
            f"mijozning yashirin shubhalarini koʻproq ochiqlashga eʼtibor qarating."
        )

        return PracticeSessionEvaluation(
            scenario_id=scenario_id,
            overall_score=overall,
            active_listening=active_score,
            need_discovery=discovery_score,
            objection_handling=objection_score,
            next_step_agreement=next_step,
            strengths=strengths,
            weak_areas=weak_areas,
            coaching_feedback=feedback,
        )

    def _init_scenarios(self) -> Dict[str, SimulationScenario]:
        """Build dictionary of standard simulation roleplay scenarios."""
        scenarios = [
            SimulationScenario(
                scenario_id="first_30_seconds",
                title="Gaplashishga rozilik oling",
                goal="Arizani eslatish va suhbatga rozilik olish",
                situation="Mijoz ikki kun oldin saytda ariza qoldirgan va hozir ishda band.",
                client_name="Kamola",
                client_gender="female",
                mood="band va shoshayotgan",
                what_convinces="Qisqa 1 daqiqalik aniq savol va vaqtni hurmat qilish",
                hidden_facts=["Aslida xizmatga qiziqishi bor, faqat hozir noqulay payt"],
            ),
            SimulationScenario(
                scenario_id="ask_before_selling",
                title="Narxdan oldin ehtiyojni bilib oling",
                goal="Narx aytishdan oldin mijozga nima kerakligini bilish",
                situation="Aziz darhol «Qancha turadi?» deb soʻraydi va qisqa javob kutadi.",
                client_name="Aziz",
                client_gender="male",
                mood="talabchan va tezkor",
                what_convinces="Kompaniyaning aniq unga mos yechim taklif qila olishi",
                hidden_facts=["Oldingi kompaniya qimmatga sotib, foydasiz boʻlib chiqqan"],
            ),
            SimulationScenario(
                scenario_id="too_expensive",
                title="Narxga arzishini koʻrsating",
                goal="Taklifingiz u uchun nega qimmatliroq ekanini koʻrsatish",
                situation="Dilnoza uyi yaqinida arzonroq taklif topgan.",
                client_name="Dilnoza",
                client_gender="female",
                mood="shubhada",
                what_convinces="Yuqori natija, amaliy tajriba va xizmat sifati kafolati",
                hidden_facts=["Uyi yaqinidagi joyda darslar sifatsizligini oʻzi ham eshitgan"],
            ),
            SimulationScenario(
                scenario_id="think_about_it",
                title="«Oʻylab koʻraman» ortidagi shubhani toping",
                goal="Asl shubhani bilish va keyingi qadamni kelishish",
                situation="Sardorga taklif yoqadi, lekin u avval maslahatlashmoqchi.",
                client_name="Sardor",
                client_gender="male",
                mood="ikkilanayotgan",
                what_convinces="Shubhalarga aniq dalillar va risk yoʻqligi",
                hidden_facts=["Byudjeti biroz yetmayapti, boʻlib toʻlash imkoni bormi deb soʻramoqchi"],
            ),
            SimulationScenario(
                scenario_id="book_next_step",
                title="Kun va vaqtni belgilang",
                goal="Ikki tomon uchun qulay aniq kun va soatni kelishish",
                situation="Mijoz hamma narsaga rozi, lekin kun tanlashdan qochadi.",
                client_name="Bekzod",
                client_gender="male",
                mood="xotirjam",
                what_convinces="Cheklangan joylar yoki maxsus tayyorlangan strategik sessiya",
                hidden_facts=["Kalendarida payshanba kuni boʻsh vaqt bor"],
            ),
        ]
        return {s.scenario_id: s for s in scenarios}

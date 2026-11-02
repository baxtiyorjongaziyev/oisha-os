"""Knowledge Base & AI Quiz Engine.

Generates testing quizzes from sales playbooks and evaluates sales rep knowledge
on objections handling, qualification rules, and company service catalogs.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class QuizQuestion:
    """Individual multiple-choice quiz question derived from knowledge playbook."""

    question_id: str
    question_text: str
    options: Dict[str, str]
    correct_option: str
    explanation: str
    category: str


@dataclass
class QuizSubmission:
    """User answers submitted for an interactive knowledge quiz."""

    user_id: str
    answers: Dict[str, str]


@dataclass
class QuizGradingResult:
    """Grading score, pass/fail state, and tailored feedback."""

    user_id: str
    score_pct: float
    passed: bool
    correct_count: int
    total_count: int
    category_scores: Dict[str, Dict[str, int]] = field(default_factory=dict)
    feedback: str = ""


class KnowledgeQuizEngine:
    """Manages question banks, administers quizzes, and grades sales rep submissions."""

    PASSING_THRESHOLD_PCT: float = 80.0

    def __init__(self) -> None:
        """Initialize quiz engine with built-in sales playbook questions."""
        self._questions: Dict[str, QuizQuestion] = self._init_question_bank()

    def get_questions(self, category: Optional[str] = None) -> List[QuizQuestion]:
        """Return all questions or filter by specific playbook category."""
        all_q = list(self._questions.values())
        if category:
            return [q for q in all_q if q.category == category]
        return all_q

    def grade_quiz(self, submission: QuizSubmission) -> QuizGradingResult:
        """Grade a quiz submission against the current question bank."""
        total_questions = len(self._questions)
        if total_questions == 0:
            return QuizGradingResult(
                user_id=submission.user_id,
                score_pct=0.0,
                passed=False,
                correct_count=0,
                total_count=0,
                feedback="Savollar banki boʻsh.",
            )

        correct_count = 0
        cat_stats: Dict[str, Dict[str, int]] = {}

        for q_id, question in self._questions.items():
            cat = question.category
            if cat not in cat_stats:
                cat_stats[cat] = {"correct": 0, "total": 0}
            cat_stats[cat]["total"] += 1

            user_ans = submission.answers.get(q_id, "").strip().upper()
            if user_ans == question.correct_option.upper():
                correct_count += 1
                cat_stats[cat]["correct"] += 1

        score_pct = (correct_count / total_questions) * 100.0
        passed = score_pct >= self.PASSING_THRESHOLD_PCT

        feedback = self._build_feedback(score_pct, passed, cat_stats)

        return QuizGradingResult(
            user_id=submission.user_id,
            score_pct=round(score_pct, 1),
            passed=passed,
            correct_count=correct_count,
            total_count=total_questions,
            category_scores=cat_stats,
            feedback=feedback,
        )

    def _build_feedback(
        self, score: float, passed: bool, cat_stats: Dict[str, Dict[str, int]]
    ) -> str:
        """Generate Uzbek feedback message based on score and weak categories."""
        if passed:
            return (
                f"Tabriklaymiz! Siz {score:.0f}% natija bilan testdan muvaffaqiyatli oʻtdingiz. "
                f"Savdo qoidalari va mahsulot bilimlari boʻyicha aʼlo darajada tayyorsiz."
            )

        weak_cats = [
            cat for cat, s in cat_stats.items()
            if s["total"] > 0 and (s["correct"] / s["total"] < 0.7)
        ]
        weak_str = ", ".join(weak_cats) if weak_cats else "umumiy savdo qoidalari"
        return (
            f"Natijangiz: {score:.0f}%. Testdan oʻtish uchun kamida "
            f"{self.PASSING_THRESHOLD_PCT:.0f}% toʻplash lozim. "
            f"Iltimos, {weak_str} boʻlimlarini qayta oʻqib chiqish va testni qayta topshirish tavsiya etiladi."
        )

    def _init_question_bank(self) -> Dict[str, QuizQuestion]:
        """Construct standard sales playbook question bank."""
        questions = [
            QuizQuestion(
                question_id="Q1",
                question_text="Mijoz qoʻngʻiroq boshida «Narx qancha?» deb soʻrasa, nima qilish kerak?",
                options={
                    "A": "Darhol eng qimmat tarif narxini aytish",
                    "B": "Ehtiyojni aniqlab, soʻng unga mos yechim va narxni taklif qilish",
                    "C": "Narx sir ekanini aytib, mavzuni burish",
                    "D": "Boshqa kompaniyalardan arzon ekanini maqtash",
                },
                correct_option="B",
                explanation="Narx ehtiyoj va qiymat koʻrsatilgandan keyin taqdim etiladi.",
                category="pricing",
            ),
            QuizQuestion(
                question_id="Q2",
                question_text="Mijoz «Oʻylab koʻraman» desa, eng toʻgʻri keyingi qadam nima?",
                options={
                    "A": "«Xoʻp, oʻylab koʻring» deb qoʻngʻiroqni yakunlash",
                    "B": "Asl ikkilanish sababini ochiqlab, aniq keyingi qadam va vaqtni kelishish",
                    "C": "Shu zahoti 50% chegirma taklif qilish",
                    "D": "Har kuni 5 martadan qoʻngʻiroq qilib turish",
                },
                correct_option="B",
                explanation="«Oʻylab koʻraman» ortida aniq savol yoki byudjet shubhasi yotadi.",
                category="objections",
            ),
            QuizQuestion(
                question_id="Q3",
                question_text="B2B lid bilan suhbatda qaror qabul qiluvchi shaxsni (LPR) qanday aniqlash mumkin?",
                options={
                    "A": "Faqat direktor bilan gaplashishim shart deb talab qilish",
                    "B": "«Loyiha yoki byudjet boʻyicha yakuniy qaror kim bilan birga tasdiqlanadi?» deb soʻrash",
                    "C": "Kompaniya buxgalteridan telefon raqam soʻrash",
                    "D": "Har doim suhbatdoshni oʻzi qaror chiqaradi deb taxmin qilish",
                },
                correct_option="B",
                explanation="Qaror qabul qilish jarayonini ochiq va professional savol orqali aniqlash lozim.",
                category="qualification",
            ),
            QuizQuestion(
                question_id="Q4",
                question_text="Mijoz «Boshqa joyda arzonroq ekan» degan eʼtiroz bildirsa, qanday javob beriladi?",
                options={
                    "A": "Ular qalbaki yoki sifatsiz xizmat koʻrsatadi deb raqibni yomonlash",
                    "B": "Mijozga bizning yechimimiz keltiradigan qoʻshimcha foyda va kafolatni tushuntirish",
                    "C": "Raqib narxidan ham pastroq narxga darhol tushib berish",
                    "D": "Mijoz bilan bahslashish",
                },
                correct_option="B",
                explanation="Raqobatchini yomonlamasdan, oʻz qiymatimiz va ROI ni koʻrsatish kerak.",
                category="objections",
            ),
            QuizQuestion(
                question_id="Q5",
                question_text="Lid bilan muloqot muvaffaqiyatli yakunlanishi uchun nima shart?",
                options={
                    "A": "Mijozga 10 sahifalik prezentatsiya yuborish",
                    "B": "Keyingi qadam: aniq kun, soat va uchrashuv maqsadi kelishilishi",
                    "C": "Mijoz «ha, koʻramiz» deb javob berishi",
                    "D": "Suhbat 30 daqiqadan oshishi",
                },
                correct_option="B",
                explanation="Har bir savdo muloqoti aniq sanaga bogʻlangan keyingi qadam bilan tugashi shart.",
                category="qualification",
            ),
            QuizQuestion(
                question_id="Q6",
                question_text="Oisha-OS tizimida CRM lidlari soni qatʼiy nechta bitim bilan cheklangan?",
                options={
                    "A": "100 ta",
                    "B": "500 ta",
                    "C": "1000 ta",
                    "D": "Cheklov yoʻq",
                },
                correct_option="B",
                explanation="Oisha-OS qoidasi boʻyicha aktiv lidlar doimiy 500 ta limitda saqlanadi.",
                category="pricing",
            ),
        ]
        return {q.question_id: q for q in questions}

from database import Database # type: ignore
from agency_hr import AgencyHR # type: ignore
import config
import logging

logger = logging.getLogger(__name__)
db = Database()

class TeamHub:
    """Jamoa a'zolarini tanib olish va almashtirish tizimi."""
    
    # Jamoa a'zolari va ularning rollari (Kelajakda DB dan olinadi)
    TEAM_ROLES = {
        "closer": "Sotuv menejeri (Closer)",
        "pm": "Project Manager",
        "namer": "Namer",
        "designer": "Dizaynerlar jamoasi",
        "hunter": "Hunter",
        "boss": "Man (CEO)"
    }

    @staticmethod
    def register_member(user_id, role, username=""):
        """Jamoa a'zosini rasman ro'yxatdan o'tkazish."""
        role = role.lower()
        if role not in TeamHub.TEAM_ROLES:
            return f"Xato: '{role}' roli mavjud emas. Tanlang: {', '.join(TeamHub.TEAM_ROLES.keys())}"
        
        db.upsert_user(user_id, username or f"TeamMember_{user_id}", role=role)
        logger.info(f"[TEAM] Member registered: {user_id} as {role}")
        return f"Muvaffaqiyatli! Endi men sizni {TeamHub.TEAM_ROLES[role]} sifatida taniyman. 🤝"

    @staticmethod
    def identify_member(user_id, username="", text_context=""):
        """Foydalanuvchini tanib olish."""
        user_info = db.get_user_info(user_id)
        if user_info and user_info.get('role'):
            return user_info['role']
        
        if str(user_id) in [str(u) for u in getattr(config, 'SUDO_USERS', [])]:
            return "boss"
        
        # Muloqot kontekstidan aniqlash (Zero-shot)
        if text_context:
            low_text = text_context.lower()
            if any(w in low_text for w in ["dizayn", "logo", "figma"]): return "designer"
            if any(w in low_text for w in ["sotuv", "mijoz yopildi", "puls"]): return "closer"
            if any(w in low_text for w in ["proyekt", "deadline", "topshiriq"]): return "pm"
            
        return "unknown"

    @staticmethod
    def assign_task_to_member(member_role, task_description):
        """Ma'lum bir rolga vazifa berish."""
        logger.info(f"[TEAM] Task assigned to {member_role}: {task_description[:50]}")
        return f"Vazifa {TeamHub.TEAM_ROLES.get(member_role, member_role)}ga yuborildi."

    @staticmethod
    def activate_ai_substitute(role):
        """Agar xodim vazifani bajarmasa, AI agentni ishga tushirish."""
        logger.warning(f"[TEAM] {role} is failing. Activating AI Substitute!")
        
        specialties = {
            "namer": "copywriter",
            "closer": "researcher",
            "designer": "designer",
            "pm": "automator"
        }
        
        specialty = specialties.get(role, "researcher")
        status = AgencyHR.hire_ai_agent(specialty)
        return f"DIQQAT: {role} o'rniga AI Agent ({specialty}) ishga tushirildi. Tizim toxtamaydi! 🧿"

    @staticmethod
    def set_position(user_id, position):
        """Foydalanuvchiga rasmiy pozitsiya biriktirish."""
        db.upsert_user(user_id, first_name=f"User_{user_id}", position=position)
        logger.info(f"[TEAM] Position set: {user_id} as {position}")
        return f"Muvaffaqiyatli! Endi men ushbu foydalanuvchini {position} sifatida taniyman. 👸🛡️🎯"

    @staticmethod
    def submit_status_report(user_id, report_type, content):
        """Kunlik hisobotni (reja yoki natija) qabul qilish."""
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        now = datetime.datetime.now().isoformat()
        
        # Bazaga saqlash
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO team_reports (user_id, report_date, report_type, content, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, today, report_type, content, now))
            conn.commit()
            
        logger.info(f"[TEAM] Report submitted: {user_id} | {report_type}")
        return True

    @staticmethod
    def get_daily_discipline_summary():
        """Bugungi intizom holatini tahlil qilish."""
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        summary = {"plans": [], "results": [], "missing": []}
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # Hisobotlarni olish
            cursor.execute("SELECT u.first_name, r.report_type, r.status FROM users u JOIN team_reports r ON u.user_id = r.user_id WHERE r.report_date = ?", (today,))
            rows = cursor.fetchall()
            for name, r_type, status in rows:
                if r_type == 'morning_plan': summary["plans"].append(name)
                elif r_type == 'evening_result': summary["results"].append(name)
                
        return summary

class StrategicAdvice:
    """N1 Agentlik bo'lish uchun qo'shimcha rollar bo'yicha tavsiyalar."""
    
    @staticmethod
    def get_missing_roles():
        """№1 daraja uchun kerakli rollar ro'yxati."""
        return [
            {"role": "AI Brand Copywriter", "desc": "Brend hikoyasini dunyo darajasida yozish uchun."},
            {"role": "UX/UI Strategist", "desc": "Brendni raqamli dunyoda yashashi uchun."},
            {"role": "Data Scientist / Market Analyst", "desc": "Trendlarni oldindan bashorat qilish uchun."},
            {"role": "Customer Success Manager", "desc": "Mijozni 'Ambassador' qilish jarayonini boshqarish uchun."},
            {"role": "QA (Quality Assurance)", "desc": "Har bir dizayn va har bir harf BENUQSONligini tekshirish uchun."}
        ]

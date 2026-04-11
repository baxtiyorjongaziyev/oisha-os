"""
MetaSell-style Call & Conversation Analysis Engine.
Transcribes voice messages, scores conversations, generates AI coaching.
"""

import logging
import os
import json
import datetime
from typing import Optional, Dict, Any, List

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class CallAnalyzer:
    """AI-powered call/conversation analysis with scoring and coaching."""

    SCORING_PROMPT = """Sen professional savdo tahlilchisissan (MetaSell AI). Quyidagi savdo suhbatini tahlil qil.

IKKI QISMLI TAHLIL QILISHING KERAK:

═══ 1-QISM: SIFAT BAHOSI (Savdo playbook bo'yicha) ═══
Har biri 0-20 ball:
1. SALOMLASHISH — Professional salomlashdi mi? O'zini va kompaniyani tanishtirib aytdimi?
2. EHTIYOJ ANIQLASH — Mijozning ehtiyojini so'rab-surishtirib chuqur tushundimi?
3. TAKLIF BERISH — Xizmat/mahsulotni ehtiyojga moslab taklif qildimi? Foyda/qiymatni ko'rsatdimi?
4. E'TIROZLARNI HAL QILISH — Mijoz e'tirozlarini professional tarzda javob berdimi?
5. YAKUNLASH — Keyingi qadamni aniqladimi? Uchrashuv/qo'ng'iroq belgiladimi?

═══ 2-QISM: MIJOZ MA'LUMOTLARI (Suhbatdan avtomatik ajratib olish) ═══
Suhbatda aytilgan barcha mijoz haqidagi ma'lumotlarni chiqar.

JAVOB FORMATI (faqat JSON):
{
    "total_score": 0-100,
    "lead_score": 0-100,
    "greeting_score": 0-20,
    "needs_discovery_score": 0-20,
    "pitch_score": 0-20,
    "objection_handling_score": 0-20,
    "closing_score": 0-20,
    "conversation_category": "Birinchi aloqa / Ehtiyoj aniqlash / Yechim taqdimoti / E'tirozlar / Yakuniy muzokara",
    "conversation_domain": "Savdo / Xizmat ko'rsatish / Konsultatsiya",
    "business_fit": "Biznesga mos / Qisman mos / Mos emas",
    "service_direction": "Branding / Marketing / Biznes transformatsiya / Web sayt / SMM / boshqa",
    "client_info": {
        "position": "Lavozimi (Director, Biznes egasi, Menejer, ...)",
        "company": "Kompaniya nomi va sohasi",
        "decision_maker": true,
        "location": "Shahar/viloyat",
        "details": ["muhim faktlar ro'yxati - kompaniya haqida, muammolari, ehtiyojlari"]
    },
    "strengths": ["kuchli tomonlar ro'yxati"],
    "weaknesses": ["zaif tomonlar ro'yxati"],
    "next_steps": ["tavsiya qilingan keyingi qadamlar"],
    "coaching_tip": "Asosiy maslahat - 1-2 gap",
    "summary": "Suhbat mazmuni - 2-3 gap"
}

MUHIM: Agar ma'lumot suhbatda aytilmagan bo'lsa, null yoki bo'sh qoldiring. O'ylab chiqarmang."""

    COACHING_PROMPT = """Sen tajribali savdo mentorsisan. Quyidagi savdogar haqida ma'lumotlar berilgan.

Savdogarning so'nggi {period} natijasi:
- O'rtacha ball: {avg_score}/100
- Eng past soha: {weakest_area}
- Eng kuchli soha: {strongest_area}
- Jami suhbatlar: {total_calls}
- Konversiya: {conversion_rate}%

So'nggi zaif tomonlar: {recent_weaknesses}

VAZIFA: Professional, motivatsion va aniq coaching yoz.
- Birinchi kuchli tomonlarini ta'kidla
- Keyin aniq, amaliy maslahatlar ber
- Mashq qilish uchun 1-2 ta senariy taklif qil
- Oisha uslubida samimiy yoz (professional lekin do'stona)

Javob 300 so'zdan oshmasin."""

    def __init__(self, api_key: str, db=None):
        self.client = genai.Client(api_key=api_key) if api_key else None
        self.model = "gemini-2.0-flash"
        self.db = db

    async def analyze_conversation(self, text: str, salesperson_id: int = None, salesperson_name: str = None) -> Dict[str, Any]:
        """Analyze a sales conversation and return scoring + coaching."""
        if not self.client or not text or len(text.strip()) < 20:
            return {"error": "Tahlil qilish uchun yetarli matn yo'q"}

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=[f"Suhbat matni:\n\n{text}"],
                config=types.GenerateContentConfig(
                    system_instruction=self.SCORING_PROMPT,
                    response_mime_type="application/json"
                )
            )

            result = json.loads(response.text)
            result["salesperson_id"] = salesperson_id
            result["salesperson_name"] = salesperson_name
            result["analyzed_at"] = datetime.datetime.now().isoformat()

            # Save to DB
            if self.db:
                self._save_analysis(result, text, salesperson_id)

            return result

        except Exception as e:
            logger.error(f"[CALL_ANALYZER] Analysis error: {e}")
            return {"error": str(e)}

    async def analyze_voice_message(self, file_path: str, salesperson_id: int = None, salesperson_name: str = None) -> Dict[str, Any]:
        """Analyze a voice message file — transcribe then score."""
        if not self.client:
            return {"error": "AI client not initialized"}

        try:
            with open(file_path, "rb") as f:
                audio_data = f.read()

            # Gemini can handle audio directly
            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    types.Content(parts=[
                        types.Part.from_bytes(data=audio_data, mime_type="audio/ogg"),
                        types.Part.from_text("Bu savdo suhbatining ovozli xabarini transkripsiya qil va to'liq matnini yoz. Faqat transkripsiya — boshqa hech narsa qo'shma.")
                    ])
                ]
            )

            transcript = response.text
            if not transcript or len(transcript.strip()) < 10:
                return {"error": "Transkripsiya bo'sh qaytdi"}

            # Now score the transcript
            result = await self.analyze_conversation(transcript, salesperson_id, salesperson_name)
            result["transcript"] = transcript
            result["source"] = "voice"
            return result

        except Exception as e:
            logger.error(f"[CALL_ANALYZER] Voice analysis error: {e}")
            return {"error": str(e)}

    async def generate_coaching(self, salesperson_id: int, salesperson_name: str = "", period: str = "hafta") -> str:
        """Generate personalized AI coaching for a salesperson."""
        if not self.client or not self.db:
            return "Coaching uchun ma'lumot yetarli emas."

        stats = self._get_salesperson_stats(salesperson_id, period)
        if not stats or stats.get("total_calls", 0) == 0:
            return f"{salesperson_name or 'Savdogar'} uchun hali tahlil qilingan suhbatlar yo'q."

        prompt = self.COACHING_PROMPT.format(
            period=period,
            avg_score=stats["avg_score"],
            weakest_area=stats["weakest_area"],
            strongest_area=stats["strongest_area"],
            total_calls=stats["total_calls"],
            conversion_rate=stats.get("conversion_rate", 0),
            recent_weaknesses=", ".join(stats.get("recent_weaknesses", []))
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=[prompt]
            )
            return response.text
        except Exception as e:
            logger.error(f"[COACHING] Error: {e}")
            return "Coaching generatsiya qilishda xatolik."

    async def get_team_report(self, period_days: int = 7) -> Dict[str, Any]:
        """Generate a full team performance report."""
        if not self.db:
            return {"error": "DB not available"}

        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            since = (datetime.datetime.now() - datetime.timedelta(days=period_days)).isoformat()
            cursor.execute("""
                SELECT salesperson_id, salesperson_name,
                       AVG(total_score) as avg_score,
                       COUNT(*) as call_count,
                       MIN(total_score) as min_score,
                       MAX(total_score) as max_score,
                       AVG(greeting_score) as avg_greeting,
                       AVG(needs_discovery_score) as avg_needs,
                       AVG(pitch_score) as avg_pitch,
                       AVG(objection_score) as avg_objection,
                       AVG(closing_score) as avg_closing
                FROM call_analyses
                WHERE analyzed_at > ?
                GROUP BY salesperson_id
                ORDER BY avg_score DESC
            """, (since,))

            rows = cursor.fetchall()
            if not rows:
                return {"period_days": period_days, "team": [], "summary": "Hali tahlillar yo'q"}

            team = []
            for row in rows:
                team.append({
                    "id": row[0],
                    "name": row[1] or f"ID:{row[0]}",
                    "avg_score": round(row[2], 1),
                    "call_count": row[3],
                    "min_score": row[4],
                    "max_score": row[5],
                    "breakdown": {
                        "greeting": round(row[6], 1),
                        "needs_discovery": round(row[7], 1),
                        "pitch": round(row[8], 1),
                        "objection_handling": round(row[9], 1),
                        "closing": round(row[10], 1)
                    }
                })

            team_avg = round(sum(m["avg_score"] for m in team) / len(team), 1) if team else 0
            return {
                "period_days": period_days,
                "team_avg_score": team_avg,
                "total_analyses": sum(m["call_count"] for m in team),
                "team": team
            }
        except Exception as e:
            logger.error(f"[TEAM_REPORT] Error: {e}")
            return {"error": str(e)}
        finally:
            conn.close()

    async def get_kpi_summary(self) -> Dict[str, Any]:
        """Get KPI summary for dashboard."""
        if not self.db:
            return {}

        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            today = datetime.date.today().isoformat()
            week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
            month_ago = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()

            # Today's stats
            cursor.execute("SELECT COUNT(*), AVG(total_score) FROM call_analyses WHERE DATE(analyzed_at) = ?", (today,))
            today_row = cursor.fetchone()

            # This week
            cursor.execute("SELECT COUNT(*), AVG(total_score) FROM call_analyses WHERE analyzed_at > ?", (week_ago,))
            week_row = cursor.fetchone()

            # This month
            cursor.execute("SELECT COUNT(*), AVG(total_score) FROM call_analyses WHERE analyzed_at > ?", (month_ago,))
            month_row = cursor.fetchone()

            # Trend (this week vs last week)
            two_weeks_ago = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
            cursor.execute("SELECT AVG(total_score) FROM call_analyses WHERE analyzed_at BETWEEN ? AND ?", (two_weeks_ago, week_ago))
            last_week_avg = cursor.fetchone()[0] or 0

            current_week_avg = week_row[1] or 0
            trend = round(current_week_avg - last_week_avg, 1)

            return {
                "today": {"calls": today_row[0] or 0, "avg_score": round(today_row[1] or 0, 1)},
                "week": {"calls": week_row[0] or 0, "avg_score": round(week_row[1] or 0, 1)},
                "month": {"calls": month_row[0] or 0, "avg_score": round(month_row[1] or 0, 1)},
                "trend": trend,
                "trend_label": "📈 Yaxshilanmoqda" if trend > 0 else ("📉 Pasaymoqda" if trend < 0 else "➡️ O'zgarishsiz")
            }
        except Exception as e:
            logger.error(f"[KPI] Error: {e}")
            return {}
        finally:
            conn.close()

    def _save_analysis(self, result: Dict, text: str, salesperson_id: int):
        """Save analysis result to database."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO call_analyses
                (salesperson_id, salesperson_name, conversation_text, total_score,
                 greeting_score, needs_discovery_score, pitch_score, objection_score, closing_score,
                 strengths, weaknesses, next_steps, coaching_tip, summary, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                salesperson_id,
                result.get("salesperson_name"),
                text[:2000],
                result.get("total_score", 0),
                result.get("greeting_score", 0),
                result.get("needs_discovery_score", 0),
                result.get("pitch_score", 0),
                result.get("objection_handling_score", 0),
                result.get("closing_score", 0),
                json.dumps(result.get("strengths", []), ensure_ascii=False),
                json.dumps(result.get("weaknesses", []), ensure_ascii=False),
                json.dumps(result.get("next_steps", []), ensure_ascii=False),
                result.get("coaching_tip", ""),
                result.get("summary", ""),
                result.get("analyzed_at", datetime.datetime.now().isoformat())
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"[SAVE_ANALYSIS] Error: {e}")
        finally:
            conn.close()

    def format_amocrm_note(self, result: Dict) -> str:
        """Format analysis result as AmoCRM note text (MetaSell-style)."""
        score = result.get("total_score", 0)
        lead_score = result.get("lead_score", 0)
        category = result.get("conversation_category", "")
        domain = result.get("conversation_domain", "")
        biz_fit = result.get("business_fit", "")
        service = result.get("service_direction", "")

        note = f"Oisha AI tahlil natijasi\n\n"
        note += result.get("summary", "") + "\n\n"
        note += f"Sifat bahosi: {score}/100\n"
        note += f"Lead bahosi: {lead_score}/100\n"
        note += f"Suhbat oilasi: {category}\n"
        note += f"Suhbat domeni: {domain}\n"
        note += f"Baholash rejimi: Savdo playbook bo'yicha baholanadi\n"
        note += f"Biznes mosligi: {biz_fit}\n"
        note += f"Servis yo'nalishi: {service}\n"

        # Client info
        client = result.get("client_info", {})
        if client and any(client.values()):
            note += f"\nOisha AI: Mijoz haqida ma'lumot\n\n"
            if client.get("position"):
                note += f"Lavozimi: {client['position']}\n"
            if client.get("company"):
                note += f"Kompaniya: {client['company']}\n"
            if client.get("decision_maker") is not None:
                dm = "Ha" if client["decision_maker"] else "Yo'q"
                note += f"Qaror qabul qiluvchi: {dm}\n"
            if client.get("location"):
                note += f"Joylashuv: {client['location']}\n"
            details = client.get("details", [])
            if details:
                note += f"\nMa'lumotlar:\n"
                for d in details:
                    note += f"• {d}\n"

        return note

    async def post_to_amocrm(self, result: Dict, lead_id: int = None, amocrm=None):
        """Post analysis result as AmoCRM note (like MetaSell does)."""
        if not amocrm or not lead_id:
            return False

        try:
            note_text = self.format_amocrm_note(result)
            amocrm.add_note_to_lead(lead_id, note_text)
            logger.info(f"[CALL_ANALYZER] Posted analysis to AmoCRM lead {lead_id}")
            return True
        except Exception as e:
            logger.error(f"[CALL_ANALYZER] AmoCRM note error: {e}")
            return False

    def _get_salesperson_stats(self, salesperson_id: int, period: str = "hafta") -> Optional[Dict]:
        """Get salesperson stats for coaching generation."""
        days = {"kun": 1, "hafta": 7, "oy": 30}.get(period, 7)
        since = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()

        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT AVG(total_score), COUNT(*),
                       AVG(greeting_score), AVG(needs_discovery_score),
                       AVG(pitch_score), AVG(objection_score), AVG(closing_score),
                       GROUP_CONCAT(weaknesses)
                FROM call_analyses
                WHERE salesperson_id = ? AND analyzed_at > ?
            """, (salesperson_id, since))

            row = cursor.fetchone()
            if not row or not row[1]:
                return None

            areas = {
                "Salomlashish": row[2] or 0,
                "Ehtiyoj aniqlash": row[3] or 0,
                "Taklif berish": row[4] or 0,
                "E'tirozlarni hal qilish": row[5] or 0,
                "Yakunlash": row[6] or 0
            }
            weakest = min(areas, key=areas.get)
            strongest = max(areas, key=areas.get)

            # Parse recent weaknesses
            all_weaknesses = []
            if row[7]:
                for w_json in row[7].split(","):
                    try:
                        all_weaknesses.extend(json.loads(w_json.strip()))
                    except Exception:
                        pass

            return {
                "avg_score": round(row[0], 1),
                "total_calls": row[1],
                "weakest_area": weakest,
                "strongest_area": strongest,
                "conversion_rate": 0,  # TODO: CRM integration
                "recent_weaknesses": list(set(all_weaknesses))[:5]
            }
        except Exception as e:
            logger.error(f"[STATS] Error: {e}")
            return None
        finally:
            conn.close()

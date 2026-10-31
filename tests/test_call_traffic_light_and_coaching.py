import pytest
from src.services.call_analytics.normalizer import (
    _derive_traffic_light,
    _derive_coaching_message,
    _derive_client_script,
    CallNormalizerMixin,
)
from src.services.call_analytics.crm_notes import CallCrmNotesMixin
from src.services.call_analytics.crm_tasks import CallCrmTasksMixin
from src.services.core.calls.call_notifier import build_call_alert_message, build_urgent_problem_alert


class TestTrafficLightDerivation:
    def test_green_traffic_light_high_score(self):
        assert _derive_traffic_light(85) == "YASHIL"
        assert _derive_traffic_light(80) == "YASHIL"
        assert _derive_traffic_light(100) == "YASHIL"

    def test_yellow_traffic_light_medium_score(self):
        assert _derive_traffic_light(75) == "SARIQ"
        assert _derive_traffic_light(60) == "SARIQ"
        assert _derive_traffic_light(79) == "SARIQ"

    def test_red_traffic_light_low_score(self):
        assert _derive_traffic_light(59) == "QIZIL"
        assert _derive_traffic_light(40) == "QIZIL"
        assert _derive_traffic_light(0) == "QIZIL"

    def test_explicit_string_override(self):
        assert _derive_traffic_light(50, "YASHIL") == "YASHIL"
        assert _derive_traffic_light(90, "QIZIL") == "QIZIL"
        assert _derive_traffic_light(85, "SARIQ") == "SARIQ"


class TestCoachingMessageDerivation:
    def test_green_motivation(self):
        msg = _derive_coaching_message("YASHIL", 85, None, kuchli=["Ehtiyoj aniqlandi"], zaif=[])
        assert "Ajoyib" in msg
        assert "Ehtiyoj aniqlandi" in msg

    def test_yellow_coaching(self):
        msg = _derive_coaching_message("SARIQ", 65, None, kuchli=[], zaif=["Narx oldidan qiymat berilmadi"])
        assert "o'rtacha" in msg.lower() or "tavsiya" in msg.lower()
        assert "Narx oldidan qiymat berilmadi" in msg

    def test_red_rescue(self):
        msg = _derive_coaching_message("QIZIL", 45, None, kuchli=[], zaif=["Mijoz yo'qotildi"])
        assert "uzilish" in msg.lower() or "qutqarish" in msg.lower()


class TestClientScriptDerivation:
    def test_from_coaching_better_phrase(self):
        coaching = [{"better_phrase": "Akmal aka, loyihamizni qachon boshlaymiz?"}]
        script = _derive_client_script(coaching=coaching)
        assert script == "Akmal aka, loyihamizni qachon boshlaymiz?"

    def test_from_next_steps(self):
        script = _derive_client_script(next_steps="KP yuborish va qayta qo'ng'iroq")
        assert "KP yuborish" in script or "Assalomu alaykum" in script


class TestIntegrationPresenters:
    def test_telegram_alert_rendering(self):
        analysis = {
            "sifat_bahosi": 85,
            "svetofor": "YASHIL",
            "motivatsiya_va_coaching": "Zo'r natija! Shunday davom eting.",
            "mijozga_aytiladigan_gap": "Akmal aka, 2-paket KP tayyor, qachon ko'rib chiqasiz?",
            "keyingi_qadam_aniq": "Ertaga 11:00 da qo'ng'iroq",
        }
        msg = build_call_alert_message(
            lead_id=123,
            call_id="call-456",
            category="Mijoz",
            summary="Mijoz brendingga qiziqdi",
            client_mood="Ijobiy",
            next_steps="Ertaga 11:00 da qo'ng'iroq",
            duration_seconds=120,
            manager_name="Ravshan",
            caller_phone="+998901234567",
            analysis=analysis,
        )
        assert "🟢" in msg
        assert "A'lo daraja" in msg
        assert "Akmal aka, 2-paket KP tayyor" in msg
        assert "Zo'r natija!" in msg

    def test_task_builder_includes_script_and_coaching(self):
        mixin = CallCrmTasksMixin()
        task_text = mixin._build_task_text(
            category="Mijoz",
            summary="Mijoz bilan muzokara",
            client_mood="Neytral",
            next_steps="Smeta yuborish",
            client_script="Salom, smetani ko'rib chiqa oldingizmi?",
            coaching_note="E'tirozga xushmuomala javob bering.",
        )
        assert "🎯 VAZIFA: Smeta yuborish" in task_text
        assert "💬 MIJOZGA AYTISH KERAK: «Salom, smetani ko'rib chiqa oldingizmi?»" in task_text
        assert "🏆 MURABBIYLIK / MOTIVATSIYA: E'tirozga xushmuomala javob bering." in task_text

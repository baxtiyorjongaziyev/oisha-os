from src.services.call_analytics.helpers import _looks_like_stt_hallucination
from src.services.core.calls.call_notifier import build_call_alert_message

# Real production output (lead 53082767): untuned Whisper "translated" an
# Uzbek call into looping English nonsense.
ENGLISH_DRIFT = (
    "Allo Qamara, Dnake, Susus, how are you? Aramat, how are you? I'm going to "
    "tell you, Gablish, can you see? Yes, I am. What happened to you about your "
    "story? Yes, I am. I got a new car, I got a new car, I got a new car, I got a "
    "new car, I got a new car, I got a new car. Iham. Ihah. Ihah."
)

UZBEK_CALL = (
    "[00:01] Menejer: Assalomu alaykum, Jon Branding agentligidan qo'ng'iroq "
    "qilyapman. [00:05] Mijoz: Vaalaykum assalom, ha eshitaman. [00:08] Menejer: "
    "Siz logotip bo'yicha ariza qoldirgan ekansiz, narxlarni aytib bersam "
    "bo'ladimi? [00:14] Mijoz: Ha, albatta, ertaga ofisga kelsam ham bo'ladi."
)


def test_english_drift_with_phrase_loop_is_rejected():
    assert _looks_like_stt_hallucination(ENGLISH_DRIFT)


def test_phrase_loop_alone_is_rejected():
    text = ", ".join(["narxi qancha bo'ladi"] * 5)
    assert _looks_like_stt_hallucination(text)


def test_mostly_english_transcript_is_rejected():
    text = (
        "yes I can tell you what is going on with the car and how are you "
        "doing today we have it for you"
    )
    assert _looks_like_stt_hallucination(text)


def test_normal_uzbek_call_is_accepted():
    assert not _looks_like_stt_hallucination(UZBEK_CALL)


def test_alert_shows_stt_model():
    msg = build_call_alert_message(
        lead_id=1,
        call_id="c1",
        category="Oila",
        summary="s",
        client_mood="Ijobiy",
        next_steps="n",
        duration_seconds=60,
        manager_name="M",
        caller_phone="+998",
        analysis={"stt_model": "groq/whisper-large-v3-turbo"},
    )
    assert "groq/whisper-large-v3-turbo" in msg

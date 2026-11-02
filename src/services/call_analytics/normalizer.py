from typing import Any, Dict, List, Optional
import structlog
from src.services.call_analytics.conversion_coaching import validated_coaching, transcript_quality
from src.services.core.sales_playbook import (
    MAX_ACCEPTABLE_PAUSE_SECONDS,
    OUTCOME_UNKNOWN,
    STAGE_WEIGHTS,
    normalise_outcome,
    outcome_converted,
    OUTCOME_FOLLOW_UP,
    OUTCOME_REFUSED,
)
from src.services.utils.transcript import (
    detect_pauses,
    has_timestamps,
)
from src.services.call_analytics.helpers import *

logger = structlog.get_logger()


def _derive_traffic_light(sifat_bahosi: int, raw_val: Any = None) -> str:
    raw_str = str(raw_val or "").strip().upper()
    if "YASHIL" in raw_str or "GREEN" in raw_str:
        return "YASHIL"
    if "SARIQ" in raw_str or "YELLOW" in raw_str:
        return "SARIQ"
    if "QIZIL" in raw_str or "RED" in raw_str:
        return "QIZIL"
    if sifat_bahosi >= 80:
        return "YASHIL"
    elif sifat_bahosi >= 60:
        return "SARIQ"
    return "QIZIL"


def _derive_coaching_message(
    svetofor: str,
    sifat_bahosi: int,
    raw_val: Any = None,
    kuchli: Optional[List[str]] = None,
    zaif: Optional[List[str]] = None,
) -> str:
    raw_str = str(raw_val or "").strip()
    if raw_str:
        return normalize_name_spellings(raw_str)
    if svetofor == "YASHIL":
        reason = f" ({kuchli[0]})" if kuchli else ""
        return f"Ajoyib muloqot! Mijoz bilan ishonch mustahkamlandi{reason}. Aynan shu tempda bitimni yakunlang!"
    elif svetofor == "SARIQ":
        focus = f" Asosiy e'tibor: {zaif[0]}." if zaif else ""
        return f"Suhbat o'rtacha darajada bo'ldi.{focus} Mahsulot qiymatini ko'proq ochib bering va navbatdagi aniq qadamni mustahkamlang."
    return "Muloqotda uzilish yoki e'tiroz bor. Mijozning ehtiyojiga qayta tayanib, yangi yechim taklif qilish orqali bitimni qutqarish mumkin."


def _derive_client_script(
    raw_val: Any = None,
    coaching: Optional[List[Dict[str, str]]] = None,
    next_steps: str = "",
    keyingi_kelishuv: str = "",
    company: str = "",
) -> str:
    raw_str = str(raw_val or "").strip()
    if raw_str:
        return normalize_name_spellings(raw_str)
    if coaching and coaching[0].get("better_phrase"):
        return normalize_name_spellings(coaching[0]["better_phrase"])
    subj = f" {company}" if company and company not in {"N/A", "na", "-"} else ""
    if keyingi_kelishuv and keyingi_kelishuv.lower() not in {"n/a", "na", "-"}:
        return f"Assalomu alaykum! Kelishganimizdek{subj} bo'yicha {keyingi_kelishuv} masalasini ko'rib chiqishga bog'lanyapman."
    if next_steps and next_steps.lower() not in {"n/a", "na", "-"}:
        return f"Assalomu alaykum!{subj} yuzasidan {next_steps} bo'yicha sizga ma'lumotlarni yubordim, qachon qisqa gaplashib olsak bo'ladi?"
    return f"Assalomu alaykum!{subj} loyihasi bo'yicha suhbatimizni davom ettirib, keyingi qadamni aniqlashtirib olsak bo'ladimi?"

class CallNormalizerMixin:
    def _normalise_analysis(
        self, data: Dict[str, Any], transcript: str, duration_seconds: int = 0
    ) -> Dict[str, Any]:
        summary = normalize_name_spellings(str(data.get("summary") or "").strip())
        next_steps = normalize_name_spellings(str(data.get("next_steps") or "N/A").strip() or "N/A")
        agreed_datetime = _parse_agreed_datetime(data.get("kelishilgan_vaqt"))
        computed_client, computed_agent, attributed = _speaker_split(transcript)
        client_pct = int(data.get("client_talk_pct") or computed_client)
        agent_pct = int(data.get("agent_talk_pct") or computed_agent)

        def _clamp_score(val: Any) -> int:
            try:
                return max(0, min(100, int(val)))
            except (TypeError, ValueError):
                return 0

        mijoz_info = [normalize_name_spellings(str(x)) for x in (data.get("mijoz_malumotlari") or [])]
        if isinstance(data.get("mijoz_malumotlari"), str):
            mijoz_info = [normalize_name_spellings(data.get("mijoz_malumotlari"))]

        def _str_list(value: Any, limit: int = 5) -> List[str]:
            if isinstance(value, str):
                value = [value] if value.strip() else []
            if not isinstance(value, list):
                return []
            items = [normalize_name_spellings(str(item).strip()) for item in value if str(item).strip()]
            return items[:limit]

        # Uzilish lahzasi — "mijoz qaysi soniyada yo'qoldi".
        #
        # MUHIM: transkripsiya bepul STT yo'lidan (Groq/Cloudflare) kelgan
        # bo'lsa, unda vaqt belgisi YO'Q — o'sha router prompt qabul
        # qilmaydi. Bunday matnda LLM lahzani bilolmaydi, faqat TAXMIN
        # qiladi. Noto'g'ri "01:42" rahbarni yozuvning bo'sh joyiga
        # yuboradi va butun funksiyaga ishonchni yo'qotadi — shuning uchun
        # asos bo'lmasa, umuman ko'rsatmaymiz.
        transcript_is_timed = has_timestamps(transcript)
        breakdown_at = (
            _parse_breakdown_time(data.get("uzilish_vaqti"), duration_seconds)
            if transcript_is_timed
            else None
        )
        if not transcript_is_timed and data.get("uzilish_vaqti"):
            logger.info(
                "[CALL] Uzilish lahzasi rad etildi — transkripsiyada vaqt "
                "belgisi yo'q (bepul STT yo'li)."
            )
        breakdown_reason = str(data.get("uzilish_sababi") or "").strip()
        if not breakdown_at:
            # Vaqtsiz sabab rahbarga foydasiz — ikkalasi birga yashaydi.
            breakdown_reason = ""



        # Pauzalar DETERMINISTIK hisoblanadi (LLM'dan so'ralmaydi): vaqt
        # belgilari bor, demak buni o'lchash mumkin va LLM to'qishi shart emas.
        pauses = [
            {
                "vaqt": p.timestamp,
                "davomiyligi": p.gap_seconds,
                "kimdan_keyin": p.after_speaker,
            }
            for p in detect_pauses(transcript, MAX_ACCEPTABLE_PAUSE_SECONDS)
        ]

        kuchli = _str_list(data.get("kuchli_tomonlar"))
        zaif = _str_list(data.get("zaif_tomonlar"))
        etirozlar = _str_list(data.get("etirozlar"))
        tavsiyalar = _str_list(data.get("konversiya_tavsiyalari") or data.get("tavsiyalar") or [])
        coaching = validated_coaching(data, transcript)
        if "coaching_evidence" in data:
            tavsiyalar = []
        if coaching:
            tavsiyalar = [f"Dalil: «{c['quote']}». {c['advice']} "
                         f"Keyingi suhbatda: {c['better_phrase']}" for c in coaching]
        keyingi_kelishuv = normalize_name_spellings(str(data.get("keyingi_kelishuv") or "").strip())
        natija = normalise_outcome(data.get("natija"))

        def _optional_score(*keys: str):
            for key in keys:
                if data.get(key) is not None and data.get(key) != "":
                    return _clamp_score(data.get(key))
            return None

        ovoz_ohangi = _optional_score("ovoz_ohangi", "tone_score")
        nutq_aniqligi = _optional_score("nutq_aniqligi", "clarity_score")
        if outcome_converted(natija):
            holat = "Muvaffaqiyatli yakunlangan"
        elif natija == OUTCOME_FOLLOW_UP:
            holat = "Keyingi aloqa kerak"
        elif natija == OUTCOME_REFUSED:
            holat = "Muvaffaqiyatsiz yakunlangan"
        else:
            holat = "Aniqlanmadi"

        # --- Rubrik baholar ---
        rubrik_raw = data.get("rubrik_baholar") or {}
        if rubrik_raw and isinstance(rubrik_raw, dict):
            def _stage(key: str) -> int:
                s = rubrik_raw.get(key, {})
                return _clamp_score(s.get("ball", 0) if isinstance(s, dict) else s)
            # Og'irliklar rasmiy playbook'dan — bu yerda qayta yozilmaydi.
            rubrik_baholar = {stage: _stage(stage) for stage in STAGE_WEIGHTS}
            total_weight = sum(STAGE_WEIGHTS.values())
            sifat_raw = (
                sum(rubrik_baholar[s] * w for s, w in STAGE_WEIGHTS.items())
                / total_weight
            )
            sifat_bahosi = _clamp_score(round(sifat_raw))
        else:
            sifat_bahosi = _clamp_score(data.get("sifat_bahosi", 0))
            rubrik_baholar = {
                "salomlashish": 0, "ehtiyojlar": 0, "qiymat": 0,
                "etirozlar": 0, "yakunlash": 0, "muloqot_sifati": 0,
            }

        category = _normalise_category(data.get("category"))
        rubrik_amal_qiladi = _rubric_applies(category, transcript)
        if not rubrik_amal_qiladi:
            sifat_bahosi = 0
            rubrik_baholar = dict.fromkeys(rubrik_baholar, 0)
            # Savdo suhbati emas — konversiya statistikasiga kirmasligi kerak,
            # aks holda "Jamoa"/"Oila" qo'ng'iroqlari sotuvchi konversiyasini
            # sun'iy ravishda pasaytiradi.
            natija = OUTCOME_UNKNOWN
            # "Mijoz yo'qolgan lahza" — savdo tushunchasi. Savdo suhbati
            # bo'lmasa mazmunsiz. Pauzalar esa obyektiv o'lchov, qoladi.
            breakdown_at = None
            breakdown_reason = ""

        svetofor = _derive_traffic_light(sifat_bahosi, data.get("svetofor"))
        motivatsiya_coaching = _derive_coaching_message(
            svetofor, sifat_bahosi, data.get("motivatsiya_va_coaching"), kuchli, zaif
        )
        keyingi_qadam_aniq = normalize_name_spellings(
            str(data.get("keyingi_qadam_aniq") or keyingi_kelishuv or next_steps or "Mijoz bilan follow-up").strip()
        )
        mijozga_gap = _derive_client_script(
            data.get("mijozga_aytiladigan_gap"), coaching, next_steps, keyingi_kelishuv, normalize_name_spellings(str(data.get("mijoz_kompaniya") or ""))
        )

        return {
            "svetofor": svetofor,
            "motivatsiya_va_coaching": motivatsiya_coaching,
            "keyingi_qadam_aniq": keyingi_qadam_aniq,
            "mijozga_aytiladigan_gap": mijozga_gap,
            "summary": summary or _clip(transcript, 350),
            "category": category,
            "client_mood": _normalise_mood(data.get("client_mood")),
            "next_steps": next_steps,
            "keyingi_kelishuv": keyingi_kelishuv,
            "kelishilgan_vaqt": agreed_datetime,
            "client_talk_pct": client_pct,
            "agent_talk_pct": agent_pct,
            "talk_ratio_verdict": _talk_ratio_verdict(client_pct, attributed),
            "talk_ratio_attributed": attributed,
            "rubrik_amal_qiladi": rubrik_amal_qiladi,
            # MetaSell-like extended fields
            "sifat_bahosi": sifat_bahosi,
            "lead_bahosi": _clamp_score(data.get("lead_bahosi", 0)),
            "suhbat_oilasi": str(data.get("suhbat_oilasi") or "Boshqa"),
            "suhbat_domeni": str(data.get("suhbat_domeni") or "Boshqa"),
            "baholash_rejimi": str(data.get("baholash_rejimi") or "Savdo playbook boyicha baholanadi"),
            "biznes_mosligi": str(data.get("biznes_mosligi") or "Noaniq"),
            "servis_yonalishi": str(data.get("servis_yonalishi") or "Boshqa"),
            "mijoz_lavozimi": str(data.get("mijoz_lavozimi") or "N/A"),
            "mijoz_kompaniya": normalize_name_spellings(str(data.get("mijoz_kompaniya") or "N/A")),
            "qaror_qabul_qiluvchi": str(data.get("qaror_qabul_qiluvchi") or "Noaniq"),
            "joylashuv": str(data.get("joylashuv") or "N/A"),
            "mijoz_malumotlari": list(mijoz_info),
            "rubrik_baholar": rubrik_baholar,
            # Murabbiylik qatlami (sales_quality_coach, metasell_conversion)
            # aynan shu maydonlarni o'qiydi.
            "natija": natija,
            "holat": holat,
            "natija_ishonch": _normalise_outcome_confidence(data.get("natija_ishonch")),
            "ovoz_ohangi": ovoz_ohangi,
            "nutq_aniqligi": nutq_aniqligi,
            "konversiya": outcome_converted(natija),
            "uzilish_vaqti": breakdown_at,
            "uzilish_sababi": breakdown_reason,
            "pauzalar": pauses,
            "eng_uzun_pauza": max((p["davomiyligi"] for p in pauses), default=0.0),
            "kuchli_tomonlar": kuchli,
            "zaif_tomonlar": zaif,
            "konversiya_tavsiyalari": tavsiyalar,
            "etirozlar": etirozlar,
            "coaching_evidence": coaching,
            "transcript_quality": transcript_quality(transcript),
        }

    def _fallback_analysis(self, transcript: str) -> Dict[str, Any]:
        lowered = (transcript or "").lower()
        client_words = (
            "brend",
            "branding",
            "logo",
            "dizayn",
            "smm",
            "sayt",
            "narx",
            "to'lov",
            "tolov",
            "commercial",
            "tijorat",
            "taklif",
            "mijoz",
            "loyiha",
        )
        family_words = (
            "ona",
            "dada",
            "opa",
            "aka",
            "farzand",
            "bola",
            "uyga",
            "oila",
            "qarindosh",
        )
        team_words = (
            "jamoa",
            "xodim",
            "menejer",
            "dizayner",
            "copywriter",
            "vazifa",
            "deadline",
            "task",
            "brief",
        )

        if any(word in lowered for word in client_words):
            category = "Mijoz"
        elif any(word in lowered for word in team_words):
            category = "Jamoa"
        elif any(word in lowered for word in family_words):
            category = "Oila"
        elif lowered.strip():
            category = "Shaxsiy"
        else:
            category = "Boshqa"

        client_pct, agent_pct, attributed = _speaker_split(transcript)
        fallback_pauses = [
            {
                "vaqt": p.timestamp,
                "davomiyligi": p.gap_seconds,
                "kimdan_keyin": p.after_speaker,
            }
            for p in detect_pauses(transcript, MAX_ACCEPTABLE_PAUSE_SECONDS)
        ]
        return {
            "svetofor": "QIZIL",
            "motivatsiya_va_coaching": "Avtomatik tahlil chegaralangan. Suhbatni tinglab, mijoz bilan qayta bog'lanish tavsiya etiladi.",
            "keyingi_qadam_aniq": "Mijoz bilan qayta bog'lanish",
            "mijozga_aytiladigan_gap": "Assalomu alaykum, kecha gaplashgan edik, sizga yana qanday yordam bera olamiz?",
            "summary": _clip(transcript or "Tahlil uchun transkripsiya topilmadi.", 350),
            "category": category,
            "client_mood": "Noaniq",
            "next_steps": "N/A",
            "kelishilgan_vaqt": None,
            "client_talk_pct": client_pct,
            "agent_talk_pct": agent_pct,
            "talk_ratio_verdict": _talk_ratio_verdict(client_pct, attributed),
            "talk_ratio_attributed": attributed,
            # Fallback = LLM ishlamadi; hech narsa baholanmagan.
            "rubrik_amal_qiladi": False,
            "sifat_bahosi": 0,
            "lead_bahosi": 0,
            "suhbat_oilasi": "Boshqa",
            "suhbat_domeni": "Boshqa",
            "baholash_rejimi": "Savdo playbook boyicha baholanadi",
            "biznes_mosligi": "Noaniq",
            "servis_yonalishi": "Boshqa",
            "mijoz_lavozimi": "N/A",
            "mijoz_kompaniya": "N/A",
            "qaror_qabul_qiluvchi": "Noaniq",
            "joylashuv": "N/A",
            "mijoz_malumotlari": [],
            "rubrik_baholar": {
                "salomlashish": 0, "ehtiyojlar": 0, "qiymat": 0,
                "etirozlar": 0, "yakunlash": 0, "muloqot_sifati": 0,
            },
            # Baholanmagan qo'ng'iroq konversiya statistikasiga kirmaydi.
            "natija": OUTCOME_UNKNOWN,
            "holat": "Aniqlanmadi",
            "natija_ishonch": 0.0,
            "ovoz_ohangi": None,
            "nutq_aniqligi": None,
            "konversiya": False,
            "uzilish_vaqti": None,
            "uzilish_sababi": "",
            # Pauza LLM'ga bog'liq emas — fallback'da ham o'lchanadi.
            "pauzalar": fallback_pauses,
            "eng_uzun_pauza": max(
                (p["davomiyligi"] for p in fallback_pauses), default=0.0
            ),
            "kuchli_tomonlar": [],
            "zaif_tomonlar": [],
            "etirozlar": [],
        }


CallAnalyzerNormalizerMixin = CallNormalizerMixin


def _normalise_outcome_confidence(value: object) -> float:
    """Model 'natija' ga ishonchi, 0.0-1.0 oralig'ida (xato bo'lsa 0.0 — etap surilmaydi)."""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if number != number:  # NaN
        return 0.0
    return max(0.0, min(1.0, number))

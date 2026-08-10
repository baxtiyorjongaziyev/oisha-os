"""Transkripsiyadan so'zlovchilar nisbatini hisoblash — umumiy yordamchi.

`call_analyzer` (AmoCRM qo'ng'iroq notalari) va `quality_analyzer` (menejer
reytinglari) bir xil transkripsiyalarni o'qiydi, shuning uchun mantiq shu
yerda bitta joyda turadi. Ilgari ikkala fayl o'z nusxasini saqlagan va
ikkalasi ham rolsiz yorliqlarda 0% qaytarib, sotuvchini asossiz jazolagan.

VAQT BELGISI (2026-08-10 dan):
    Transkripsiya endi `[01:42] A: ...` ko'rinishida keladi — bu "mijoz
    qaysi lahzada yo'qoldi" va "keraksiz pauza" tahlillari uchun kerak.
    Vaqt belgisining ICHIDA ikki nuqta bor, shuning uchun uni olib
    tashlamasdan yorliqni ajratib bo'lmaydi (`[01` yorliq deb o'qilardi va
    gapirish nisbati 0% ga tushardi). Har bir o'quvchi `strip_timestamps`
    dan o'tkazishi SHART — shu sababli u ham shu yerda turadi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List

_CLIENT_LABELS = re.compile(r"^(mijoz|xaridor|client)\s*:", re.IGNORECASE)
_AGENT_LABELS = re.compile(
    r"^(sotuvchi|menejer|manager|agent|xodim|oisha)\s*:", re.IGNORECASE
)
# Diarizatsiya ko'pincha rolsiz yorliq beradi: "A:", "B:", "Speaker 1:", "1:".
# Bunda kim sotuvchi ekani transkripsiyadan bilinmaydi.
_GENERIC_LABELS = re.compile(r"^(?:speaker\s*)?([ab]|[12])$", re.IGNORECASE)


# `[mm:ss]` yoki `[hh:mm:ss]` — qator boshidagi vaqt belgisi.
_TIMESTAMP_RE = re.compile(r"^\s*\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\]\s*")

# Nutq tezligi — pauzani BAHOLASH uchun. Aniq o'lchov emas: bizda har bir
# gapning boshlanish vaqti bor, tugash vaqti yo'q. `call_analyzer` dagi
# hallucination qo'riqchisi ham shu 2.5 so'z/soniya taxminiga tayanadi —
# ikkalasi bir xil bo'lishi uchun konstanta shu yerda.
WORDS_PER_SECOND = 2.5


def _parse_timestamp(line: str) -> tuple[int | None, str]:
    """Qator boshidagi vaqt belgisini ajratadi -> (soniya, qolgan matn)."""
    match = _TIMESTAMP_RE.match(line or "")
    if not match:
        return None, (line or "").strip()
    hours, minutes, seconds = match.groups()
    total = int(minutes) * 60 + int(seconds)
    if hours:
        total += int(hours) * 3600
    return total, line[match.end():].strip()


def strip_timestamps(transcript: str) -> str:
    """Vaqt belgilarini olib tashlaydi.

    So'z sanaydigan yoki yorliq ajratadigan HAR QANDAY kod avval shundan
    o'tkazishi kerak — aks holda `[01:42]` bitta "so'z" deb sanaladi va
    hallucination qo'riqchisi haqiqiy transkripsiyani rad etadi.
    """
    if not transcript:
        return ""
    return "\n".join(
        _parse_timestamp(line)[1] for line in transcript.splitlines()
    )


def speaker_split(transcript: str) -> tuple[int, int, bool]:
    """Return (client_pct, agent_pct, attributed).

    `attributed` is False when speakers carry role-less labels (A/B, 1/2) —
    the two percentages are then a raw first/second-speaker split, not a
    client/agent split. Callers must not present them as roles, and must not
    score the agent on them.
    """
    client_chars = 0
    agent_chars = 0
    generic_chars: Dict[str, int] = {}
    generic_order: List[str] = []

    for line in (transcript or "").splitlines():
        # Vaqt belgisi ichida ham ':' bor — yorliqni izlashdan OLDIN olib
        # tashlamasak, `[01` yorliq deb o'qiladi va nisbat 0% ga tushadi.
        _, line = _parse_timestamp(line)
        if not line:
            continue
        colon_pos = line.find(":")
        if colon_pos < 1:
            continue
        label = line[:colon_pos].strip()
        text = line[colon_pos + 1:].strip()
        if _CLIENT_LABELS.match(label + ":"):
            client_chars += len(text)
        elif _AGENT_LABELS.match(label + ":"):
            agent_chars += len(text)
        elif _GENERIC_LABELS.match(label):
            key = label.upper()
            if key not in generic_chars:
                generic_chars[key] = 0
                generic_order.append(key)
            generic_chars[key] += len(text)

    total = client_chars + agent_chars
    if total > 0:
        return (
            round(client_chars * 100 / total),
            round(agent_chars * 100 / total),
            True,
        )

    # Rolsiz yorliqlar: aynan 2 ta so'zlovchi bo'lsagina nisbat mazmunli.
    if len(generic_order) == 2:
        first, second = (generic_chars[k] for k in generic_order)
        gen_total = first + second
        if gen_total > 0:
            return (
                round(first * 100 / gen_total),
                round(second * 100 / gen_total),
                False,
            )

    return 0, 0, False


def talk_ratio_verdict(client_pct: int, attributed: bool = True) -> str:
    """Human-readable verdict for the talk ratio.

    Ma'lumot yo'qligi (0%) sotuvchining aybi emas — bunday holatda hukm
    chiqarmaymiz. Rolsiz yorliqlarda ham kim ko'p gapirgani noma'lum.
    """
    if not attributed or client_pct <= 0:
        return "ℹ️ Gapirish nisbati aniqlanmadi — transkripsiyada rollar belgilanmagan"
    if client_pct >= 55:
        return f"✅ Yaxshi — mijoz {client_pct}% gapirdi (ideal: ≥55%)"
    if client_pct >= 40:
        return f"⚠️ O'rtacha — mijoz {client_pct}% gapirdi (ideal: ≥55%)"
    return f"🔴 Zaif — sotuvchi haddan ko'p gapirdi, mijoz faqat {client_pct}% gapirdi"


@dataclass(frozen=True)
class Utterance:
    """Transkripsiyaning bitta gapi (vaqt belgisi bilan)."""

    at_seconds: int
    speaker: str
    text: str

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    @property
    def estimated_duration(self) -> float:
        """Gapni aytishga ketadigan taxminiy vaqt (soniya)."""
        return self.word_count / WORDS_PER_SECOND


@dataclass(frozen=True)
class Pause:
    """Ikki gap orasidagi sukut."""

    at_seconds: int      # pauza boshlangan taxminiy lahza
    gap_seconds: float   # sukut davomiyligi
    after_speaker: str   # kim gapirgandan keyin sukut tushdi

    @property
    def timestamp(self) -> str:
        return format_timestamp(self.at_seconds)


def format_timestamp(seconds: float) -> str:
    """Soniyani `mm:ss` ko'rinishiga keltiradi."""
    total = max(0, int(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def parse_utterances(transcript: str) -> List[Utterance]:
    """Vaqt belgili transkripsiyani gaplarga ajratadi.

    Vaqt belgisi yo'q qatorlar TUSHIRIB QOLDIRILADI — ularsiz pauza
    hisoblab bo'lmaydi, taxmin qilish esa noto'g'ri ayblovga olib keladi.
    """
    utterances: List[Utterance] = []
    for line in (transcript or "").splitlines():
        at_seconds, rest = _parse_timestamp(line)
        if at_seconds is None or not rest:
            continue
        colon_pos = rest.find(":")
        if colon_pos < 1:
            continue
        speaker = rest[:colon_pos].strip()
        text = rest[colon_pos + 1:].strip()
        if not text:
            continue
        utterances.append(Utterance(at_seconds=at_seconds, speaker=speaker, text=text))
    return utterances


def detect_pauses(transcript: str, min_gap_seconds: float) -> List[Pause]:
    """Gaplar orasidagi uzun sukutlarni topadi.

    METOD VA UNING CHEGARASI: bizda har bir gapning BOSHLANISH vaqti bor,
    tugash vaqti yo'q. Shuning uchun gapning davomiyligini so'z sonidan
    baholaymiz (`WORDS_PER_SECOND`) va qolgan bo'shliqni pauza deb olamiz.
    Bu — TAXMIN, sekundomer emas. Shu sababli chegara (`min_gap_seconds`)
    ataylab saxiy qilingan: qisqa, tabiiy tanaffuslarni "xato" deb
    ko'rsatib, sotuvchini asossiz ayblamaslik kerak.
    """
    utterances = parse_utterances(transcript)
    if len(utterances) < 2:
        return []

    pauses: List[Pause] = []
    for current, following in zip(utterances, utterances[1:]):
        speech_end = current.at_seconds + current.estimated_duration
        gap = following.at_seconds - speech_end
        if gap >= min_gap_seconds:
            pauses.append(
                Pause(
                    at_seconds=int(speech_end),
                    gap_seconds=round(gap, 1),
                    after_speaker=current.speaker,
                )
            )
    return pauses

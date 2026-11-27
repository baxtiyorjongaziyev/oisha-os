"""STT proper-noun prompt hints and deterministic spelling normalization.

Prevents STT (Gemini / Whisper) from garbling or translating key company,
founder, and manager names — especially Mumtozmaxal (+998773220098),
Jon Branding Agentligi, and Baxtiyorjon Gaziyev.
"""
from __future__ import annotations

import re

MUMTOZMAXAL_PHONE_DIGITS = "998773220098"
_MUMTOZMAXAL_LOCAL_DIGITS = "773220098"

STT_PROPER_NOUNS_PROMPT = (
    "- ATOQLI OTLAR VA BREND NOMLARI (TARJIMA QILMANG, BUZMANG):\n"
    "  * \"Mumtozmaxal\" (toʻliq ismi: Mumtozmaxal Normurodova) — hech qachon "
    "\"Mumtoz mahal\", \"Mumtozmahal\" yoki boshqa soʻzga buzmang.\n"
    "  * \"Jon Branding Agentligi\" — hech qachon \"John Branding Agency\", "
    "\"Djon Branding\" yoki ingliz/rus tiliga tarjima qilmang.\n"
    "  * \"Baxtiyorjon Gaziyev\" — hech qachon \"Baxtiyor Gaziev\", "
    "\"Bakhtiyor Gaziev\" yoki boshqa shaklda tarjima qilmang."
)


def _digits_only(phone: str) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def is_mumtozmaxal_phone(phone: str) -> bool:
    """Return True if *phone* matches Mumtozmaxal's +998773220098 line."""
    digits = _digits_only(phone)
    if not digits:
        return False
    return digits == MUMTOZMAXAL_PHONE_DIGITS or digits.endswith(_MUMTOZMAXAL_LOCAL_DIGITS)


def build_caller_stt_context(caller_phone: str = "", manager_name: str = "") -> str:
    """Return extra STT prompt guidance when the caller/manager is Mumtozmaxal."""
    is_mumtoz_manager = "mumtoz" in (manager_name or "").lower()
    if not (is_mumtozmaxal_phone(caller_phone) or is_mumtoz_manager):
        return ""
    return (
        "\n- QOʻNGʻIROQ MENEJERI KONTEKSTI: Bu qoʻngʻiroq +998773220098 raqamidan "
        "(menejer: Mumtozmaxal Normurodova) amalga oshirilgan. Menejer oʻzini "
        "tanishtirganda ismini aynan \"Mumtozmaxal\" deb yozing — hech qachon buzmang."
    )


_UZ_SUFFIX = r"(?:'|ʼ|ʻ)?(ning|ga|da|dan|ni|si|miz|man|xon)?"

_NAME_NORMALIZATION_RULES: tuple[tuple[str, str], ...] = (
    # Owner standarti (2026-10-09): 'Rayhonajon' demasin, 'Rayxon' desin.
    (r"(?<!@)\bRayhonajon('?)(ning|ga|da|dan|ni|si|miz)?\b(?!@)", r"Rayxon\1\2"),
    (r"(?<!@)\bRayhonaxon('?)(ning|ga|da|dan|ni|si|miz)?\b(?!@)", r"Rayxon\1\2"),
    (r"(?<!@)\bRayhon('?)(ning|ga|da|dan|ni|si|miz)?\b(?!@)", r"Rayxon\1\2"),
    (r"(?<!@)\bRayhona('?)(ning|ga|da|dan|ni|si|miz)?\b(?!@)", r"Rayxon\1\2"),
    (r"(?<!@)\bRayxona('?)(ning|ga|da|dan|ni|si|miz)?\b(?!@)", r"Rayxon\1\2"),
    # Mumtozmaxal — STT buzilishlari (Mumtozmahal, Mumtoz mahal, kirillcha va h.k.)
    (
        rf"(?<!@)\b(?:Mumtoz[\s\-]+(?:maxal|mahal)|Mumtozmahal|Мумтоз[\s\-]*(?:махал|маҳал)){_UZ_SUFFIX}\b(?!@)",
        r"Mumtozmaxal\1",
    ),
    # Jon Branding Agentligi — inglizcha/ruscha tarjima yoki imlo buzilishlari
    (
        rf"(?<!@)\b(?:(?:John|Jon|Djon)\s+Brand(?:ing)?\s+(?:Agency|Agentligi)|"
        rf"(?:Jon|John|Djon)\s+brending\s+agentligi|"
        rf"(?:Джон|Жон)\s+Брендинг\s+(?:Агентлиги|Агентство)){_UZ_SUFFIX}\b(?!@)",
        r"Jon Branding Agentligi\1",
    ),
    # Baxtiyorjon Gaziyev — tarjima yoki qisqartirilgan/ruscha shakllar
    (
        rf"(?<!@)\b(?:(?:Baxtiyorjon|Baxtiyor|Bakhtiyorjon|Bakhtiyor|Bahtiyorjon|Bahtiyor)\s+"
        rf"(?:Gaziyev|Gaziev|Gʻoziyev|Goziyev|G\x27oziyev)|"
        rf"(?:Бахтиёржон|Бахтиёр)\s+(?:Газиев|Ғозиев)){_UZ_SUFFIX}\b(?!@)",
        r"Baxtiyorjon Gaziyev\1",
    ),
)


def normalize_name_spellings(text: str) -> str:
    """Normalize known team, founder, and agency proper-noun STT distortions."""
    if not text:
        return text
    for pattern, repl in _NAME_NORMALIZATION_RULES:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text

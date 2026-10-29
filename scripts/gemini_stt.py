#!/usr/bin/env python3
"""Gemini-powered Uzbek Speech-to-Text (STT) for Hermes Agent.

Invoked via Hermes Agent:
HERMES_LOCAL_STT_COMMAND=python /home/hermes/.hermes/scripts/gemini_stt.py {input_path} {output_dir}
"""
import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def get_api_key() -> str:
    # 1. Check environment
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        return key

    # 2. Check ~/.hermes/.env
    env_file = Path.home() / ".hermes" / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("GEMINI_API_KEY=") or line.startswith("GOOGLE_API_KEY="):
                _, _, val = line.partition("=")
                return val.strip().strip("'\"")

    return ""


def main():
    if len(sys.argv) < 3:
        print("Usage: gemini_stt.py <input_path> <output_dir>", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "transcript.txt"

    if not input_path.is_file():
        print(f"Error: input file {input_path} not found", file=sys.stderr)
        out_file.write_text("", encoding="utf-8")
        sys.exit(1)

    api_key = get_api_key()
    if not api_key:
        print("Error: GEMINI_API_KEY or GOOGLE_API_KEY not found", file=sys.stderr)
        out_file.write_text("", encoding="utf-8")
        sys.exit(1)

    # Determine MIME type
    ext = input_path.suffix.lower()
    mime_map = {
        ".ogg": "audio/ogg",
        ".oga": "audio/ogg",
        ".mp3": "audio/mp3",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".flac": "audio/flac",
    }
    mime_type = mime_map.get(ext) or mimetypes.guess_type(str(input_path))[0] or "audio/ogg"

    # Encode audio file
    audio_data = input_path.read_bytes()
    b64_data = base64.b64encode(audio_data).decode("ascii")

    # Use gemini-3.5-flash
    model = os.environ.get("HERMES_GEMINI_STT_MODEL", "gemini-3.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    prompt = (
        "Ushbu audio yozuvni o'zbek tilida so'zma-so'z to'liq transkripsiya qilib ber. "
        "Faqat eshitilgan matnni o'zini yoz, hech qanday kirish yoki qo'shimcha izoh qo'shma."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_data
                        }
                    },
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.0
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            text = ""
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts).strip()

            out_file.write_text(text, encoding="utf-8")
            print(f"[OK] Transcribed {len(text)} chars to {out_file}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"Gemini STT API error {e.code}: {err_body}", file=sys.stderr)
        out_file.write_text("", encoding="utf-8")
        sys.exit(1)
    except Exception as e:
        print(f"Gemini STT error: {e}", file=sys.stderr)
        out_file.write_text("", encoding="utf-8")
        sys.exit(1)


if __name__ == "__main__":
    main()

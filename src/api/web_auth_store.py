"""Universal Web Authentication Store for Oisha-OS & MetaCAPI Platform.

Supports:
1. Universal Telegram Deep-Link Login (`t.me/jonairobot?start=weblogin_<state>`)
   for ANY Telegram account without requiring @BotFather domain setup.
2. Email + Password login and self-registration (PBKDF2-HMAC-SHA256).
3. Google Sign-In (ID token verification via Google tokeninfo).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import pathlib
import secrets
import sqlite3
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

_DB_PATH = pathlib.Path("data/web_auth_sessions.db")


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tg_login_states (
            state TEXT PRIMARY KEY,
            next_url TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            user_id INTEGER,
            username TEXT,
            first_name TEXT,
            role TEXT,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS web_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'targetolog',
            created_at REAL NOT NULL
        )
        """
    )
    return conn


def create_tg_login_state(next_url: str = "/api/marketing/capi/console", ttl: int = 600) -> str:
    """Create a pending Telegram deep-link login state token."""
    state = secrets.token_urlsafe(18)
    now = time.time()
    with _conn() as c:
        c.execute("DELETE FROM tg_login_states WHERE expires_at < ?", (now,))
        c.execute(
            "INSERT INTO tg_login_states (state, next_url, status, created_at, expires_at) VALUES (?, ?, 'pending', ?, ?)",
            (state, next_url, now, now + ttl),
        )
        c.commit()
    return state


def approve_tg_login_state(
    state: str,
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    role: str = "targetolog",
) -> Optional[str]:
    """Approve a pending Telegram login state when the user presses Start in @jonairobot."""
    clean_state = str(state or "").strip()
    if not clean_state:
        return None
    now = time.time()
    with _conn() as c:
        row = c.execute(
            "SELECT next_url, expires_at FROM tg_login_states WHERE state = ?",
            (clean_state,),
        ).fetchone()
        if not row or float(row["expires_at"]) < now:
            return None
        c.execute(
            """
            UPDATE tg_login_states
            SET status = 'approved', user_id = ?, username = ?, first_name = ?, role = ?
            WHERE state = ?
            """,
            (int(user_id), str(username or ""), str(first_name or "Foydalanuvchi"), str(role), clean_state),
        )
        c.commit()
        return str(row["next_url"])


def issue_tg_otp_code(
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    role: str = "targetolog",
    next_url: str = "/api/marketing/capi/console",
) -> str:
    """Issue a 10-minute 6-digit OTP code in tg_login_states for browser login."""
    code = f"{secrets.randbelow(900000) + 100000}"
    now = time.time()
    with _conn() as c:
        c.execute("DELETE FROM tg_login_states WHERE expires_at < ?", (now,))
        c.execute(
            """
            INSERT OR REPLACE INTO tg_login_states
            (state, next_url, status, user_id, username, first_name, role, created_at, expires_at)
            VALUES (?, ?, 'approved', ?, ?, ?, ?, ?, ?)
            """,
            (f"otp_{code}", next_url, int(user_id), str(username or ""), str(first_name or "Foydalanuvchi"), str(role), now, now + 600),
        )
        c.commit()
    return code


def poll_tg_login_state(state: str) -> Optional[Dict[str, Any]]:
    """Check if a Telegram deep-link login state has been approved and consume it."""
    clean_state = str(state or "").strip()
    if not clean_state:
        return None
    now = time.time()
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM tg_login_states WHERE state = ?",
            (clean_state,),
        ).fetchone()
        if not row:
            return None
        if float(row["expires_at"]) < now:
            c.execute("DELETE FROM tg_login_states WHERE state = ?", (clean_state,))
            c.commit()
            return {"status": "expired"}
        if row["status"] != "approved":
            return {"status": "pending"}
        data = dict(row)
        c.execute("DELETE FROM tg_login_states WHERE state = ?", (clean_state,))
        c.commit()
        return data


def _hash_password(password: str, salt: Optional[str] = None) -> str:
    s = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), s.encode("utf-8"), 120_000)
    return f"{s}${dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    if "$" not in stored:
        return False
    salt, _ = stored.split("$", 1)
    expected = _hash_password(password, salt=salt)
    return hmac.compare_digest(expected, stored)


def register_or_login_email(
    email: str,
    password: str,
    name: Optional[str] = None,
    is_register: bool = False,
) -> Optional[Dict[str, Any]]:
    """Authenticate or register a user via Email + Password."""
    clean_email = str(email or "").strip().lower()
    if not clean_email or "@" not in clean_email or len(password or "") < 4:
        return None
    owner_email = os.getenv("OWNER_EMAIL", "baxtiyorjon@jonbranding.uz").strip().lower()
    with _conn() as c:
        row = c.execute("SELECT * FROM web_users WHERE email = ?", (clean_email,)).fetchone()
        if is_register:
            if row:
                if _verify_password(password, str(row["password_hash"])):
                    return dict(row)
                return None
            role = "owner" if clean_email == owner_email else "targetolog"
            display = (name or clean_email.split("@")[0]).strip()
            pw_hash = _hash_password(password)
            cur = c.execute(
                "INSERT INTO web_users (email, name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                (clean_email, display, pw_hash, role, time.time()),
            )
            c.commit()
            return {
                "id": int(cur.lastrowid or 1000) + 900_000_000,
                "email": clean_email,
                "name": display,
                "role": role,
            }
        if not row:
            return None
        if not _verify_password(password, str(row["password_hash"])):
            return None
        res = dict(row)
        res["id"] = int(res["id"]) + 900_000_000
        return res


def verify_google_credential(id_token: str) -> Optional[Dict[str, Any]]:
    """Verify Google ID token via Google's official tokeninfo endpoint."""
    tok = str(id_token or "").strip()
    if not tok:
        return None
    url = "https://oauth2.googleapis.com/tokeninfo?" + urllib.parse.urlencode({"id_token": tok})
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as resp:  # nosec B310
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("email_verified") not in ("true", True):
            return None
        email = str(data.get("email") or "").strip().lower()
        if not email:
            return None
        client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
        if client_id and data.get("aud") != client_id:
            return None
        owner_email = os.getenv("OWNER_EMAIL", "baxtiyorjon@jonbranding.uz").strip().lower()
        role = "owner" if email == owner_email else "targetolog"
        display = str(data.get("name") or email.split("@")[0]).strip()
        with _conn() as c:
            row = c.execute("SELECT * FROM web_users WHERE email = ?", (email,)).fetchone()
            if not row:
                cur = c.execute(
                    "INSERT INTO web_users (email, name, password_hash, role, created_at) VALUES (?, ?, '', ?, ?)",
                    (email, display, role, time.time()),
                )
                c.commit()
                uid = int(cur.lastrowid or 1000) + 900_000_000
            else:
                uid = int(row["id"]) + 900_000_000
        return {
            "id": uid,
            "email": email,
            "name": display,
            "role": role,
        }
    except Exception:
        return None


_GOOGLE_FALLBACK_BTN = (
    '<button type="button" class="btn-google" onclick="document.getElementById(\'emailInput\').focus();">'
    '<svg width="18" height="18" viewBox="0 0 24 24"><path fill="#EA4335" d="M12 5c1.6 0 3 .6 4.1 1.7l3.1-3.1C17.3 1.8 14.8 1 12 1 7.4 1 3.5 3.6 1.6 7.4l3.7 2.8C6.2 7.2 8.9 5 12 5z"/><path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.8-2.4 3.6l3.7 2.9c2.2-2 3.7-5 3.7-8.7z"/><path fill="#FBBC05" d="M5.3 14.8c-.2-.8-.4-1.6-.4-2.5s.2-1.7.4-2.5L1.6 7C.6 9 0 11.2 0 13.5s.6 4.5 1.6 6.5l3.7-2.9z"/><path fill="#34A853" d="M12 24c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3.1 0-5.8-2.1-6.7-5l-3.7 2.8C3.5 21.4 7.4 24 12 24z"/></svg>'
    '<span>Google / Gmail orqali davom etish</span></button>'
)


def render_universal_login_html(
    safe_next: str,
    safe_bot_username: str = "",
    auth_url: str = "",
    sent: Optional[str] = None,
    err_msg: Optional[str] = None,
) -> str:
    """Render pure SaaS login page (Google, Email/Password, and Admin Access)."""
    import html
    google_client_id = html.escape(os.getenv("GOOGLE_CLIENT_ID", "").strip(), quote=True)
    banner = ""
    if sent == "1":
        banner = '<div class="banner ok">✅ Maxfiy havola yuborildi!</div>'
    elif err_msg:
        banner = f'<div class="banner err">⚠️ {html.escape(err_msg)}</div>'

    google_block = (
        f'<script src="https://accounts.google.com/gsi/client" async defer></script>'
        f'<div id="g_id_onload" data-client_id="{google_client_id}" data-login_uri="/api/auth/google/callback?next={safe_next}" data-auto_prompt="false"></div>'
        f'<div class="g_id_signin" data-type="standard" data-size="large" data-theme="outline" data-text="signin_with" data-shape="rectangular" data-logo_alignment="left" data-width="360"></div>'
        if google_client_id else _GOOGLE_FALLBACK_BTN
    )
    return _LOGIN_HTML_TEMPLATE.format(
        banner=banner,
        google_block=google_block,
        safe_next=safe_next,
    )


_LOGIN_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8"><title>MetaCAPI Platform — Tizimga kirish</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; background: #0f172a; color: #f8fafc; margin: 0; padding: 16px; box-sizing: border-box; }}
    .card {{ background: #1e293b; padding: 36px 32px; border-radius: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.4); max-width: 420px; width: 100%; border: 1px solid #334155; box-sizing: border-box; }}
    .logo-badge {{ width: 48px; height: 48px; border-radius: 14px; background: linear-gradient(135deg, #3b82f6, #8b5cf6); display: flex; align-items: center; justify-content: center; margin: 0 auto 16px; font-size: 24px; box-shadow: 0 8px 20px rgba(59,130,246,0.3); }}
    h2 {{ color: #f8fafc; margin: 0 0 6px; font-size: 22px; font-weight: 700; text-align: center; letter-spacing: -0.3px; }}
    .sub {{ color: #94a3b8; margin: 0 0 24px; font-size: 13px; text-align: center; line-height: 1.4; }}
    .banner {{ padding: 11px 14px; border-radius: 10px; margin-bottom: 16px; font-size: 13px; font-weight: 500; }}
    .banner.ok {{ background: rgba(16,185,129,0.15); border: 1px solid #10b981; color: #34d399; }}
    .banner.err {{ background: rgba(239,68,68,0.15); border: 1px solid #ef4444; color: #f87171; }}
    .btn-google {{ width: 100%; background: #ffffff; color: #0f172a; border: none; padding: 12px 14px; border-radius: 10px; font-weight: 600; cursor: pointer; font-size: 14px; display: flex; align-items: center; justify-content: center; gap: 10px; margin-bottom: 16px; transition: transform 0.1s, background 0.15s; }}
    .btn-google:hover {{ background: #f1f5f9; transform: translateY(-1px); }}
    .divider {{ display: flex; align-items: center; text-align: center; color: #64748b; font-size: 12px; margin: 18px 0; font-weight: 500; }}
    .divider::before, .divider::after {{ content: ''; flex: 1; border-bottom: 1px solid #334155; }}
    .divider:not(:empty)::before {{ margin-right: 12px; }} .divider:not(:empty)::after {{ margin-left: 12px; }}
    .tabs {{ display: flex; background: #0f172a; border-radius: 10px; padding: 4px; margin-bottom: 16px; border: 1px solid #334155; }}
    .tab {{ flex: 1; text-align: center; padding: 8px; font-size: 13px; font-weight: 600; border-radius: 8px; cursor: pointer; color: #94a3b8; border: none; background: transparent; transition: all 0.2s; }}
    .tab.active {{ background: #3b82f6; color: #ffffff; box-shadow: 0 2px 8px rgba(59,130,246,0.3); }}
    .lbl {{ display: block; font-size: 12px; font-weight: 600; color: #cbd5e1; margin-bottom: 5px; text-align: left; }}
    .inp {{ width: 100%; padding: 11px 14px; background: #0f172a; border: 1px solid #334155; border-radius: 10px; font-size: 14px; color: #f8fafc; box-sizing: border-box; margin-bottom: 14px; outline: none; transition: border 0.15s; }}
    .inp:focus {{ border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.2); }}
    .btn-primary {{ width: 100%; background: linear-gradient(135deg, #3b82f6, #2563eb); color: #fff; border: none; padding: 12px; border-radius: 10px; font-weight: 600; cursor: pointer; font-size: 14px; box-shadow: 0 4px 12px rgba(37,99,235,0.3); transition: filter 0.15s, transform 0.1s; }}
    .btn-primary:hover {{ filter: brightness(1.1); transform: translateY(-1px); }}
    .perks {{ display: flex; justify-content: space-between; margin-top: 22px; padding-top: 18px; border-top: 1px solid #334155; font-size: 11px; color: #64748b; }}
    .admin-toggle {{ margin-top: 16px; text-align: center; font-size: 11px; }}
    .admin-toggle a {{ color: #475569; text-decoration: none; }}
    .admin-toggle a:hover {{ color: #94a3b8; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo-badge">⚡</div>
    <h2>MetaCAPI Platform</h2>
    <p class="sub">Targetologlar va bizneslar uchun CRM & Meta Conversion API attribyutsiyasi</p>
    {banner}
    {google_block}
    <div class="divider">yoki Email orqali</div>
    <div class="tabs">
      <button type="button" class="tab active" id="tabLogin" onclick="setMode('login')">Kirish</button>
      <button type="button" class="tab" id="tabReg" onclick="setMode('register')">Ro'yxatdan o'tish</button>
    </div>
    <form method="POST" action="/api/auth/email/login" id="authForm">
      <input type="hidden" name="next" value="{safe_next}">
      <input type="hidden" name="mode" id="authMode" value="login">
      <div id="nameGroup" style="display:none;">
        <label class="lbl">Ismingiz</label>
        <input type="text" name="name" id="nameInput" class="inp" placeholder="Masalan: Sardor">
      </div>
      <div>
        <label class="lbl">Elektron pochta</label>
        <input type="email" name="email" id="emailInput" class="inp" placeholder="ism@kompaniya.uz yoki gmail" required>
      </div>
      <div>
        <label class="lbl">Maxfiy parol</label>
        <input type="password" name="password" class="inp" placeholder="••••••••" required minlength="4">
      </div>
      <button type="submit" class="btn-primary" id="submitBtn">Tizimga kirish</button>
    </form>
    <div class="perks">
      <span>🔒 Shaxsiy Sandbox</span>
      <span>⚡ 7 kun bepul</span>
      <span>📊 CRM Attribyutsiya</span>
    </div>
    <div class="admin-toggle">
      <a href="#" onclick="document.getElementById('adminBox').style.display=document.getElementById('adminBox').style.display==='none'?'block':'none';return false;">Admin kirish</a>
    </div>
    <div id="adminBox" style="display:none;margin-top:12px;padding:12px;background:#0f172a;border-radius:10px;border:1px solid #334155;">
      <form method="POST" action="/api/auth/token/login" style="display:flex;gap:6px;">
        <input type="hidden" name="next" value="{safe_next}">
        <input type="password" name="token" class="inp" placeholder="Admin Secret / Bearer Token" style="margin:0;font-size:12px;" required>
        <button type="submit" class="btn-primary" style="width:auto;padding:0 12px;font-size:12px;">Kirish</button>
      </form>
    </div>
  </div>
  <script>
    function setMode(m) {{
      document.getElementById('authMode').value = m;
      document.getElementById('tabLogin').className = 'tab' + (m === 'login' ? ' active' : '');
      document.getElementById('tabReg').className = 'tab' + (m === 'register' ? ' active' : '');
      document.getElementById('nameGroup').style.display = m === 'register' ? 'block' : 'none';
      document.getElementById('submitBtn').textContent = m === 'register' ? "Hisob yaratish va kirish" : "Tizimga kirish";
    }}
  </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Email + parol bilan kirish (faqat owner yaratgan hisoblar, ochiq roʼyxatdan
# oʼtish yoʼq). Urinishlar soni cheklanadi.
# ---------------------------------------------------------------------------
MIN_PASSWORD_LENGTH = 10
_EMAIL_FAIL_LIMIT = 5
_IP_FAIL_LIMIT = 20
_FAIL_WINDOW_SECONDS = 900
_failures: Dict[str, list] = {}
_DUMMY_HASH = ""


def _recent_failures(key: str, now: float) -> list:
    hits = [t for t in _failures.get(key, []) if now - t < _FAIL_WINDOW_SECONDS]
    if hits:
        _failures[key] = hits
    else:
        _failures.pop(key, None)
    return hits


def login_throttled(email: str, ip: str) -> bool:
    """True when too many failed email/password attempts were made recently."""
    now = time.time()
    if len(_recent_failures(f"e:{email}", now)) >= _EMAIL_FAIL_LIMIT:
        return True
    return len(_recent_failures(f"i:{ip}", now)) >= _IP_FAIL_LIMIT


def record_login_failure(email: str, ip: str) -> None:
    now = time.time()
    _failures.setdefault(f"e:{email}", []).append(now)
    _failures.setdefault(f"i:{ip}", []).append(now)


def clear_login_failures(email: str) -> None:
    _failures.pop(f"e:{email}", None)


def authenticate_email(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Verify an existing account. Never creates accounts."""
    global _DUMMY_HASH
    clean_email = str(email or "").strip().lower()
    if not clean_email or "@" not in clean_email or not password:
        return None
    with _conn() as c:
        row = c.execute("SELECT * FROM web_users WHERE email = ?", (clean_email,)).fetchone()
    if not row or not str(row["password_hash"] or ""):
        # Parol tekshiruvi vaqti hisob bor-yoʼqligini bildirmasligi uchun.
        if not _DUMMY_HASH:
            _DUMMY_HASH = _hash_password(secrets.token_urlsafe(12))
        _verify_password(password, _DUMMY_HASH)
        return None
    if not _verify_password(password, str(row["password_hash"])):
        return None
    res = dict(row)
    res["id"] = int(res["id"]) + 900_000_000
    return res


def set_user_password(
    email: str,
    password: str,
    role: str = "targetolog",
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create or update an account (owner-run script only)."""
    clean_email = str(email or "").strip().lower()
    if not clean_email or "@" not in clean_email:
        raise ValueError("email notoʼgʼri")
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise ValueError(f"parol kamida {MIN_PASSWORD_LENGTH} belgi boʼlishi kerak")
    pw_hash = _hash_password(password)
    display = (name or clean_email.split("@")[0]).strip()
    with _conn() as c:
        row = c.execute("SELECT id FROM web_users WHERE email = ?", (clean_email,)).fetchone()
        if row:
            c.execute(
                "UPDATE web_users SET password_hash = ?, role = ? WHERE email = ?",
                (pw_hash, role, clean_email),
            )
        else:
            c.execute(
                "INSERT INTO web_users (email, name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                (clean_email, display, pw_hash, role, time.time()),
            )
        c.commit()
    return {"email": clean_email, "role": role, "created": row is None}

"""One-time, owner-authorized Google Drive OAuth onboarding for Oisha-OS.

Tickets and CSRF state are stored as SHA256 hashes in Turso. OAuth credentials
never enter Telegram, source control, or user-visible logs. Only the intended
personal Google account and configured folder can be authorized.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import secrets
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
from google_auth_oauthlib.flow import Flow

from src.database_pool import db_pool

EXPECTED_EMAIL_DEFAULT = "baxtiyorjongaziyev@gmail.com"
REDIRECT_DEFAULT = "https://oisha.jonbranding.uz/api/integrations/gdrive/callback"
SCOPES = (
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/userinfo.email",
)
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_OAUTH_EXCHANGE_ENDPOINT = "https://oauth2.googleapis.com/token"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def expected_email() -> str:
    return _env("GDRIVE_EXPECTED_EMAIL", EXPECTED_EMAIL_DEFAULT).lower()


def token_path() -> Path:
    return Path(_env(
        "GDRIVE_OAUTH_TOKEN_FILE",
        "/home/deploy/oisha-os/data/gdrive_oauth_token.json",
    ))


def root_folder() -> str:
    return _env("GDRIVE_OFFLOAD_FOLDER_ID")


def _flow() -> Flow:
    client_id = _env("GDRIVE_OAUTH_CLIENT_ID") or _env("GOOGLE_CLIENT_ID")
    client_secret = _env("GDRIVE_OAUTH_CLIENT_SECRET") or _env("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("Google OAuth web client has not been configured")
    redirect = _env("GDRIVE_OAUTH_REDIRECT_URI", REDIRECT_DEFAULT)
    if redirect != REDIRECT_DEFAULT:
        raise RuntimeError("Google Drive callback URL differs from trusted origin")
    config = {"web": {
        "client_id": client_id,
        "client_secret": client_secret,
        "auth_uri": GOOGLE_AUTH_URI,
        "token_uri": GOOGLE_OAUTH_EXCHANGE_ENDPOINT,
        "redirect_uris": [redirect],
    }}
    return Flow.from_client_config(config, scopes=list(SCOPES), redirect_uri=redirect)


def oauth_client_ready() -> bool:
    return bool(
        (_env("GDRIVE_OAUTH_CLIENT_ID") or _env("GOOGLE_CLIENT_ID")) and
        (_env("GDRIVE_OAUTH_CLIENT_SECRET") or _env("GOOGLE_CLIENT_SECRET")) and
        root_folder()
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def _schema() -> None:
    await db_pool.execute(
        """CREATE TABLE IF NOT EXISTS crm_drive_oauth_states (
           hash TEXT PRIMARY KEY,
           kind TEXT NOT NULL,
           expires_at TEXT NOT NULL,
           consumed_at TEXT
        )"""
    )
    await db_pool.commit()


async def _issue(kind: str) -> str:
    await _schema()
    secret = secrets.token_urlsafe(32)
    expires = (_utcnow() + timedelta(minutes=10)).isoformat()
    await db_pool.execute(
        "INSERT INTO crm_drive_oauth_states (hash,kind,expires_at) VALUES (?,?,?)",
        [_fingerprint(secret), kind, expires],
    )
    await db_pool.commit()
    return secret


async def _consume(kind: str, secret: str) -> bool:
    if not secret or len(secret) > 256:
        return False
    await _schema()
    result = await db_pool.execute(
        """UPDATE crm_drive_oauth_states SET consumed_at=?
           WHERE hash=? AND kind=? AND consumed_at IS NULL AND expires_at>?
           RETURNING hash""",
        [_utcnow().isoformat(), _fingerprint(secret), kind, _utcnow().isoformat()],
    )
    await db_pool.commit()
    return len(result) == 1


async def issue_owner_link() -> str:
    if not oauth_client_ready():
        raise RuntimeError("OAuth client credentials or Drive destination not configured")
    ticket = await _issue("ticket")
    return f"https://oisha.jonbranding.uz/api/integrations/gdrive/connect?ticket={ticket}"


async def begin_authorization(ticket: str) -> str:
    if not oauth_client_ready():
        raise RuntimeError("OAuth is not configured")
    if not await _consume("ticket", ticket):
        raise PermissionError("OAuth link is expired, invalid, or already used")
    state = await _issue("state")
    flow = _flow()
    url, _ = flow.authorization_url(
        state=state,
        access_type="offline",
        prompt="consent",
        login_hint=expected_email(),
        include_granted_scopes="false",
    )
    return url


def _validate_google_account(credentials) -> dict:
    response = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {credentials.token}"},
        timeout=20,
    )
    response.raise_for_status()
    user = response.json()
    if (user.get("email", "").lower() != expected_email()
            or user.get("email_verified") not in (True, "true")):
        raise PermissionError("Google account is not the approved personal account")
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    about = drive.about().get(
        fields="user(emailAddress),storageQuota(limit,usage)"
    ).execute()
    email = (about.get("user") or {}).get("emailAddress", "").lower()
    if email != expected_email():
        raise PermissionError("Drive owner account does not match Google identity")
    quota = (about.get("storageQuota") or {})
    limit = int(quota.get("limit") or 0)
    if limit < 4_500_000_000_000:
        raise PermissionError("Expected personal 5 TB storage limit not verified")
    folder_id = root_folder()
    if not folder_id:
        raise RuntimeError("GDRIVE_OFFLOAD_FOLDER_ID is not configured")
    folder = drive.files().get(
        fileId=folder_id,
        fields="id,mimeType,trashed,capabilities(canAddChildren)",
        supportsAllDrives=True,
    ).execute()
    if (folder.get("trashed") or
            folder.get("mimeType") != "application/vnd.google-apps.folder" or
            not (folder.get("capabilities") or {}).get("canAddChildren")):
        raise PermissionError("Personal Drive destination is not writable")
    if not credentials.refresh_token:
        raise RuntimeError("Google did not issue an offline refresh token")
    # Verify real create, read-back and cleanup before permitting CRM sync.
    payload = b"Oisha Drive authorized write probe"
    media = MediaIoBaseUpload(io.BytesIO(payload), mimetype="text/plain")
    probe_id = None
    try:
        probe = drive.files().create(
            body={"name": ".oisha-oauth-probe-" + secrets.token_hex(6),
                  "parents": [folder_id]},
            media_body=media, fields="id,size", supportsAllDrives=True,
        ).execute()
        probe_id = probe["id"]
        fetched = drive.files().get(
            fileId=probe_id, fields="id,size", supportsAllDrives=True,
        ).execute()
        if int(fetched.get("size", -1)) != len(payload):
            raise RuntimeError("Google Drive write-probe readback failed")
    finally:
        if probe_id:
            drive.files().delete(fileId=probe_id, supportsAllDrives=True).execute()
    return {"email": email, "quota_limit_bytes": limit, "folder_id": folder_id}


def _persist(credentials) -> None:
    path = token_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=".drive-oauth-", delete=False,
        ) as handle:
            temp_name = handle.name
            os.chmod(temp_name, 0o600)
            handle.write(credentials.to_json())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        os.chmod(path, 0o600)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


async def complete_authorization(state: str, code: str) -> dict:
    if not await _consume("state", state):
        raise PermissionError("Google OAuth state is expired or already consumed")
    if not code:
        raise PermissionError("Google OAuth code missing")

    def exchange():
        flow = _flow()
        flow.fetch_token(code=code)
        verified = _validate_google_account(flow.credentials)
        _persist(flow.credentials)
        return verified

    return await asyncio.to_thread(exchange)

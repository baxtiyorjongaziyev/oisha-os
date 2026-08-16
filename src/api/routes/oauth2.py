import hmac
import os
import secrets
import time
import html as html_lib
from typing import Optional
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(prefix="/oauth2", tags=["oauth2"])

_AUTH_CODE_TTL_SECONDS = 300
_auth_codes: dict[str, tuple[str, float]] = {}  # code -> (client_id, expires_at)

ALLOWED_HOSTS = {"localhost", "127.0.0.1", "jonbranding.uz", "oisha.jonbranding.uz"}


def _allowed_redirect_uris() -> set[str]:
    raw = os.environ.get("OAUTH2_ALLOWED_REDIRECT_URIS", "")
    return {u.strip() for u in raw.split(",") if u.strip()}


def _validate_redirect_uri(redirect_uri: str) -> str:
    parsed = urlparse(redirect_uri)
    if parsed.scheme not in ("https", "http") or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid redirect_uri scheme or host")

    host = parsed.netloc.split(":")[0].lower()
    allowed_uris = _allowed_redirect_uris()

    if allowed_uris:
        if redirect_uri not in allowed_uris:
            raise HTTPException(status_code=400, detail="Redirect URI not in allowed list")
        return redirect_uri

    if host not in ALLOWED_HOSTS and not host.endswith(".jonbranding.uz"):
        raise HTTPException(status_code=400, detail="Untrusted redirect URI host")

    return redirect_uri


# GET /oauth2/authorize - Shows the consent screen
@router.get("/authorize", response_class=HTMLResponse)
async def authorize_get(
    request: Request,
    client_id: str,
    redirect_uri: str,
    state: str,
    response_type: str = "code",
):
    valid_uri = _validate_redirect_uri(redirect_uri)
    safe_client_id = html_lib.escape(client_id)
    safe_redirect_uri = html_lib.escape(valid_uri)
    safe_state = html_lib.escape(state)
    # Simple HTML consent screen
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Oisha-OS Authorization</title>
        <style>
            body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #f0f2f5; margin: 0; }}
            .card {{ background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; max-width: 400px; }}
            .btn {{ background: #007bff; color: white; border: none; padding: 10px 20px; font-size: 16px; border-radius: 4px; cursor: pointer; }}
            .btn:hover {{ background: #0056b3; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Oisha-OS</h2>
            <p><strong>{safe_client_id}</strong> is requesting access to your Oisha-OS MCP Server (Telegram & CRM).</p>
            <form method="POST" action="/oauth2/authorize">
                <input type="hidden" name="client_id" value="{safe_client_id}">
                <input type="hidden" name="redirect_uri" value="{safe_redirect_uri}">
                <input type="hidden" name="state" value="{safe_state}">
                <button type="submit" class="btn">Allow Access</button>
            </form>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

# POST /oauth2/authorize - Processes consent and redirects
@router.post("/authorize")
async def authorize_post(
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    state: str = Form(...),
):
    valid_uri = _validate_redirect_uri(redirect_uri)
    parsed = urlparse(valid_uri)

    auth_code = secrets.token_urlsafe(32)
    _auth_codes[auth_code] = (client_id, time.time() + _AUTH_CODE_TTL_SECONDS)

    # Parse and safely reconstruct query parameters
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs["code"] = [auth_code]
    qs["state"] = [state]
    new_query = urlencode(qs, doseq=True)

    # Rebuild URL strictly from parsed components
    safe_redirect_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment,
    ))

    return RedirectResponse(url=safe_redirect_url, status_code=302)



# POST /oauth2/token - Exchanges auth code for access token
@router.post("/token")
async def token(
    grant_type: str = Form(...),
    code: str = Form(None),
    client_id: str = Form(None),
    client_secret: str = Form(None),
):
    if grant_type != "authorization_code":
        raise HTTPException(status_code=400, detail="Unsupported grant type")

    entry = _auth_codes.pop(code, None) if code else None
    if entry is None or entry[1] < time.time():
        raise HTTPException(status_code=400, detail="Invalid or expired authorization code")

    stored_client_id, _ = entry
    if not client_id or not hmac.compare_digest(client_id, stored_client_id):
        raise HTTPException(status_code=400, detail="client_id mismatch")

    expected_secret = os.environ.get("OAUTH2_CLIENT_SECRET") or os.environ.get("OISHA_API_SECRET")
    if not expected_secret:
        raise HTTPException(status_code=500, detail="OAuth2 not configured")
    if not client_secret or not hmac.compare_digest(client_secret, expected_secret):
        raise HTTPException(status_code=401, detail="Invalid client_secret")

    # The access token is the OISHA_API_SECRET so existing internal auth
    # middleware (which checks it directly) accepts requests made with it.
    access_token = os.environ.get("OISHA_API_SECRET")
    if not access_token:
        raise HTTPException(status_code=500, detail="OAuth2 not configured")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 315360000  # 10 years
    }

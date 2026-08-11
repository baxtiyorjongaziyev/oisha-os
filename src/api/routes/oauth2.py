import os
from typing import Optional
from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(prefix="/oauth2", tags=["oauth2"])

# GET /oauth2/authorize - Shows the consent screen
@router.get("/authorize", response_class=HTMLResponse)
async def authorize_get(
    request: Request,
    client_id: str,
    redirect_uri: str,
    state: str,
    response_type: str = "code",
):
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
            <p><strong>{client_id}</strong> is requesting access to your Oisha-OS MCP Server (Telegram & CRM).</p>
            <form method="POST" action="/oauth2/authorize">
                <input type="hidden" name="client_id" value="{client_id}">
                <input type="hidden" name="redirect_uri" value="{redirect_uri}">
                <input type="hidden" name="state" value="{state}">
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
    # In a real system, we'd generate a temporary auth code and store it.
    # For this simplified stateless version, we just use a static code.
    auth_code = "oisha_auth_code_123"
    
    # Append code and state to redirect_uri
    if "?" in redirect_uri:
        redirect_url = f"{redirect_uri}&code={auth_code}&state={state}"
    else:
        redirect_url = f"{redirect_uri}?code={auth_code}&state={state}"
        
    return RedirectResponse(url=redirect_url, status_code=302)


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
        
    if code != "oisha_auth_code_123":
        raise HTTPException(status_code=400, detail="Invalid authorization code")
        
    # The access token is simply the OISHA_API_SECRET
    # This way the existing internal mechanisms that expect it might work, 
    # but the middleware will explicitly check it anyway.
    access_token = os.environ.get("OISHA_API_SECRET", "default_secret_if_none")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 315360000  # 10 years
    }

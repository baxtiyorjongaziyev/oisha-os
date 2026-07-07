import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
from dotenv import load_dotenv
import httpx
from db import init_db, save_token, get_token, delete_token

load_dotenv()

META_APP_ID = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
REDIRECT_URI = f"{BACKEND_URL}/api/auth/callback"

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Marketing OS API", lifespan=lifespan)

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/auth/login")
async def login():
    """Redirect to Meta OAuth page"""
    if not META_APP_ID:
        return {"error": "META_APP_ID is not configured in .env"}
        
    oauth_url = (
        f"https://www.facebook.com/v19.0/dialog/oauth?"
        f"client_id={META_APP_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"scope=instagram_basic,instagram_manage_insights,pages_show_list,ads_read,business_management"
    )
    return RedirectResponse(url=oauth_url)

@app.get("/api/auth/callback")
async def callback(code: str = None, error: str = None):
    """Handle Meta OAuth callback"""
    if error:
        return RedirectResponse(url=f"{FRONTEND_URL}?error={error}")
    
    if not code:
        return RedirectResponse(url=f"{FRONTEND_URL}?error=missing_code")

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_url = "https://graph.facebook.com/v19.0/oauth/access_token"
        params = {
            "client_id": META_APP_ID,
            "redirect_uri": REDIRECT_URI,
            "client_secret": META_APP_SECRET,
            "code": code
        }
        res = await client.get(token_url, params=params)
        data = res.json()
        
        access_token = data.get("access_token")
        if access_token:
            save_token(access_token)
            return RedirectResponse(url=f"{FRONTEND_URL}?success=true")
        else:
            return RedirectResponse(url=f"{FRONTEND_URL}?error=token_exchange_failed")

@app.get("/api/auth/status")
async def auth_status():
    token = get_token()
    return {"connected": bool(token)}

@app.get("/api/auth/logout")
async def logout():
    delete_token()
    return {"success": True}


@app.get("/api/performance")
async def get_performance_data() -> Dict[str, Any]:
    """
    Mock data matching Adtru AI dashboard.
    """
    return {
        "summary": {
            "amount_spent": 3032.20,
            "revenue": 33382.79,
            "roas": 11.01,
            "cac": 112.30,
            "conversion_rate": 6.3,
            "deal_time": "11.7d",
            "arpl": 97.61,
            "revenue_growth": 253.7
        },
        "ad_sets": [
            {
                "name": "Ad Set AA-...",
                "spend": 39.16,
                "impressions": 14952,
                "frequency": 1.30,
                "clicks": 63,
                "ctr": 0.42,
                "cpm": 2.62,
                "cpc": 0.62,
                "leads": 15,
                "cpl": 2.61,
                "q_leads": 0,
                "ql_percentage": 0.0,
                "cpql": 0.0,
                "purchases": 0,
                "cost_per_purchase": 0.0,
                "revenue": 0.0,
                "roas": 0.0,
                "status": "active"
            },
            {
                "name": "Ad Set Sma...",
                "spend": 53.63,
                "impressions": 42527,
                "frequency": 1.06,
                "clicks": 155,
                "ctr": 0.36,
                "cpm": 1.26,
                "cpc": 0.35,
                "leads": 7,
                "cpl": 7.66,
                "q_leads": 0,
                "ql_percentage": 0.0,
                "cpql": 0.0,
                "purchases": 0,
                "cost_per_purchase": 0.0,
                "revenue": 0.0,
                "roas": 0.0,
                "status": "active"
            },
            {
                "name": "Ad Set AA-...",
                "spend": 443.68,
                "impressions": 226580,
                "frequency": 1.40,
                "clicks": 2570,
                "ctr": 1.13,
                "cpm": 1.96,
                "cpc": 0.17,
                "leads": 47,
                "cpl": 9.44,
                "q_leads": 8,
                "ql_percentage": 17.0,
                "cpql": 55.46,
                "purchases": 4,
                "cost_per_purchase": 110.92,
                "revenue": 4982.98,
                "roas": 11.23,
                "status": "active"
            },
            {
                "name": "Ad Set Pag...",
                "spend": 380.10,
                "impressions": 171998,
                "frequency": 1.45,
                "clicks": 967,
                "ctr": 0.56,
                "cpm": 2.21,
                "cpc": 0.39,
                "leads": 36,
                "cpl": 10.56,
                "q_leads": 6,
                "ql_percentage": 16.7,
                "cpql": 63.35,
                "purchases": 3,
                "cost_per_purchase": 126.70,
                "revenue": 3741.01,
                "roas": 9.84,
                "status": "active"
            },
            {
                "name": "Ad Set AA-...",
                "spend": 394.78,
                "impressions": 151170,
                "frequency": 1.52,
                "clicks": 815,
                "ctr": 0.54,
                "cpm": 2.61,
                "cpc": 0.48,
                "leads": 35,
                "cpl": 11.28,
                "q_leads": 4,
                "ql_percentage": 11.4,
                "cpql": 98.70,
                "purchases": 2,
                "cost_per_purchase": 197.39,
                "revenue": 2427.92,
                "roas": 6.15,
                "status": "active"
            },
            {
                "name": "Ad Set AA-...",
                "spend": 447.03,
                "impressions": 238356,
                "frequency": 1.32,
                "clicks": 2495,
                "ctr": 1.05,
                "cpm": 1.88,
                "cpc": 0.18,
                "leads": 38,
                "cpl": 11.76,
                "q_leads": 3,
                "ql_percentage": 7.9,
                "cpql": 149.01,
                "purchases": 2,
                "cost_per_purchase": 223.52,
                "revenue": 2503.99,
                "roas": 5.60,
                "status": "active"
            },
            {
                "name": "Ad Set AA-...",
                "spend": 440.24,
                "impressions": 195739,
                "frequency": 1.47,
                "clicks": 2589,
                "ctr": 1.32,
                "cpm": 2.25,
                "cpc": 0.17,
                "leads": 36,
                "cpl": 12.23,
                "q_leads": 4,
                "ql_percentage": 11.1,
                "cpql": 110.06,
                "purchases": 1,
                "cost_per_purchase": 440.24,
                "revenue": 1237.89,
                "roas": 2.81,
                "status": "active"
            },
            {
                "name": "Ad Set AA-...",
                "spend": 391.62,
                "impressions": 222336,
                "frequency": 1.51,
                "clicks": 1042,
                "ctr": 0.47,
                "cpm": 1.76,
                "cpc": 0.38,
                "leads": 31,
                "cpl": 12.63,
                "q_leads": 4,
                "ql_percentage": 12.9,
                "cpql": 97.91,
                "purchases": 1,
                "cost_per_purchase": 391.62,
                "revenue": 1251.87,
                "roas": 3.20,
                "status": "active"
            },
            {
                "name": "Ad Set AA-...",
                "spend": 441.06,
                "impressions": 221598,
                "frequency": 1.43,
                "clicks": 1889,
                "ctr": 0.85,
                "cpm": 1.99,
                "cpc": 0.23,
                "leads": 34,
                "cpl": 13.00,
                "q_leads": 1,
                "ql_percentage": 2.9,
                "cpql": 441.96,
                "purchases": 4,
                "cost_per_purchase": 110.49,
                "revenue": 4917.54,
                "roas": 11.13,
                "status": "active"
            }
        ]
    }

"""Airtable OAuth 2.0 Client and API wrapper."""
import base64
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
import httpx
import structlog
from fastapi import HTTPException

from src.settings import settings
from src.db import get_db

logger = structlog.get_logger()

class AirtableClient:
    AUTH_URL = "https://airtable.com/oauth2/v1/authorize"
    TOKEN_URL = "https://airtable.com/oauth2/v1/token"
    API_BASE = "https://api.airtable.com/v0"

    def __init__(self):
        self.client_id = settings.AIRTABLE_CLIENT_ID
        self.client_secret = settings.AIRTABLE_CLIENT_SECRET.get_secret_value() if settings.AIRTABLE_CLIENT_SECRET else ""
        self.redirect_uri = settings.AIRTABLE_REDIRECT_URI

    def get_authorization_url(self, state: str, code_challenge: str) -> str:
        """Generate the URL to redirect the user for OAuth."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "scope": "data.records:read data.records:write schema.bases:read", # Customize based on needs
        }
        return f"{self.AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def exchange_code_for_token(self, code: str, code_verifier: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens."""
        async with httpx.AsyncClient() as client:
            auth_str = f"{self.client_id}:{self.client_secret}"
            auth_b64 = base64.b64encode(auth_str.encode()).decode()
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {auth_b64}",
            }
            
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "code_verifier": code_verifier,
            }
            
            resp = await client.post(self.TOKEN_URL, headers=headers, data=data)
            
            if resp.status_code != 200:
                logger.error("[AIRTABLE] Token exchange failed", resp=resp.text)
                raise HTTPException(status_code=400, detail="Failed to exchange code for token")
            
            token_data = resp.json()
            
            # Save to database
            expires_in = token_data.get("expires_in", 3600)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            
            db = get_db()
            await db.oauth.save_tokens(
                service_name="airtable",
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                expires_at=expires_at,
            )
            return token_data

    async def _refresh_token_if_needed(self) -> str:
        """Check if token is expired, refresh it if so, and return valid access token."""
        db = get_db()
        tokens = await db.oauth.get_tokens("airtable")
        if not tokens:
            raise ValueError("No Airtable tokens found in database. User must authenticate first.")
        
        expires_at = tokens["expires_at"]
        # If token expires in less than 5 minutes, refresh it
        if not expires_at or datetime.now(timezone.utc) >= expires_at - timedelta(minutes=5):
            logger.info("[AIRTABLE] Token expired or expiring soon, refreshing...")
            async with httpx.AsyncClient() as client:
                auth_str = f"{self.client_id}:{self.client_secret}"
                auth_b64 = base64.b64encode(auth_str.encode()).decode()
                
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {auth_b64}",
                }
                
                data = {
                    "grant_type": "refresh_token",
                    "refresh_token": tokens["refresh_token"],
                }
                
                resp = await client.post(self.TOKEN_URL, headers=headers, data=data)
                
                if resp.status_code != 200:
                    logger.error("[AIRTABLE] Token refresh failed", resp=resp.text)
                    raise RuntimeError("Failed to refresh Airtable token")
                
                token_data = resp.json()
                expires_in = token_data.get("expires_in", 3600)
                new_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                
                await db.oauth.save_tokens(
                    service_name="airtable",
                    access_token=token_data["access_token"],
                    refresh_token=token_data["refresh_token"],
                    expires_at=new_expires_at,
                )
                return token_data["access_token"]
        
        return tokens["access_token"]

    async def get_records(self, base_id: str, table_id_or_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fetch records from a table."""
        access_token = await self._refresh_token_if_needed()
        
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        url = f"{self.API_BASE}/{base_id}/{urllib.parse.quote(table_id_or_name)}"
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json()

    async def create_records(self, base_id: str, table_id_or_name: str, records: list) -> Dict[str, Any]:
        """Create records in a table."""
        access_token = await self._refresh_token_if_needed()
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.API_BASE}/{base_id}/{urllib.parse.quote(table_id_or_name)}"
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json={"records": records})
            resp.raise_for_status()
            return resp.json()

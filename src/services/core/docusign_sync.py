"""
DocuSign Bridge
Surgical Negotiator shartnoma generatsiya qilganda → DocuSign orqali imzoga yuboradi.

⚠️ O'zbekistonda email ishlatilmaydi → default `embedded=True`: DocuSign EMAIL
YUBORMAYDI, o'rniga `signingUrl` qaytaradi — uni oisha-os Telegram/SMS orqali
mijozga yuboradi. [[uz-email-not-used]]

⚠️ settings.py YANGILANMAYDI (Coordinator owns) — env varlar getattr bilan o'qiladi.
Coordinator qo'shishi kerak: DOCUSIGN_ENABLED, DOCUSIGN_BASE_URI, DOCUSIGN_ACCOUNT_ID,
DOCUSIGN_ACCESS_TOKEN, DOCUSIGN_TEMPLATE_ID.

Integratsiya (surgical_negotiator deal yopilganda):
    ds = get_docusign()
    res = await ds.send_contract(signer_name=client_name, contract_text=body)
    if res and res.get("signingUrl"):
        await send_telegram(user_id, f"Shartnoma: {res['signingUrl']}")
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Dict, Optional

import httpx

from src.settings import settings

logger = logging.getLogger("DocuSignSync")


def _cfg(name: str, default):
    return getattr(settings, name, default)


class DocuSignSync:
    def __init__(self):
        self.base_uri = str(_cfg("DOCUSIGN_BASE_URI", "https://demo.docusign.net/restapi")).rstrip("/")
        self.account_id = str(_cfg("DOCUSIGN_ACCOUNT_ID", ""))
        self.token = str(_cfg("DOCUSIGN_ACCESS_TOKEN", ""))
        self.template_id = str(_cfg("DOCUSIGN_TEMPLATE_ID", ""))
        self.enabled = bool(_cfg("DOCUSIGN_ENABLED", False)) and bool(self.account_id) and bool(self.token)
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=f"{self.base_uri}/v2.1/accounts/{self.account_id}",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def send_contract(
        self,
        signer_name: str,
        signer_email: str = "",
        contract_text: str = "",
        subject: str = "Shartnoma imzo uchun",
        embedded: bool = True,
        return_url: str = "https://t.me",
    ) -> Optional[Dict[str, Any]]:
        """
        Shartnomani imzoga yuboradi.

        - embedded=True  → clientUserId bilan envelope; EMAIL yuborilmaydi,
          `signingUrl` qaytariladi (Telegram/SMS orqali yuborish uchun).
        - embedded=False → klassik email-based delivery (signer_email kerak).

        Returns: {"envelopeId", "status", "signingUrl"?} yoki None
        """
        if not self.enabled:
            logger.info("[DocuSign] disabled — shartnoma yuborilmadi")
            return None
        if not embedded and not signer_email:
            logger.warning("[DocuSign] email-mode uchun signer_email kerak")
            return None

        client_user_id = "tg-signer" if embedded else ""
        effective_email = signer_email or (
            f"{(signer_name or 'mijoz').strip().replace(' ', '.').lower()}@telegram.local"
            if embedded
            else signer_email
        )

        try:
            if self.template_id:
                envelope = self._build_template_envelope(
                    signer_name, effective_email, subject, client_user_id
                )
            else:
                envelope = self._build_document_envelope(
                    signer_name, effective_email, contract_text, subject, client_user_id
                )

            resp = await self.client.post("/envelopes", json=envelope)
            resp.raise_for_status()
            data = resp.json()
            envelope_id = data.get("envelopeId")
            logger.info(f"[DocuSign] Envelope yaratildi: {envelope_id}")

            result: Dict[str, Any] = {
                "envelopeId": envelope_id,
                "status": data.get("status"),
            }
            if embedded and envelope_id:
                result["signingUrl"] = await self.create_recipient_view(
                    envelope_id, signer_name, effective_email, client_user_id, return_url
                )
            return result
        except Exception as e:
            logger.warning(f"[DocuSign] send_contract failed: {e}")
            return None

    async def create_recipient_view(
        self,
        envelope_id: str,
        signer_name: str,
        signer_email: str,
        client_user_id: str,
        return_url: str = "https://t.me",
    ) -> Optional[str]:
        """Embedded signing URL — Telegram/SMS orqali mijozga yuborish uchun."""
        if not self.enabled:
            return None
        try:
            body = {
                "returnUrl": return_url,
                "authenticationMethod": "none",
                "email": signer_email,
                "userName": signer_name or signer_email,
                "clientUserId": client_user_id,
            }
            resp = await self.client.post(
                f"/envelopes/{envelope_id}/views/recipient", json=body
            )
            resp.raise_for_status()
            return resp.json().get("url")
        except Exception as e:
            logger.warning(f"[DocuSign] create_recipient_view failed: {e}")
            return None

    def _build_template_envelope(
        self, signer_name: str, signer_email: str, subject: str, client_user_id: str = ""
    ) -> Dict[str, Any]:
        role: Dict[str, Any] = {
            "email": signer_email,
            "name": signer_name or signer_email,
            "roleName": "Signer",
        }
        if client_user_id:
            role["clientUserId"] = client_user_id
        return {
            "templateId": self.template_id,
            "emailSubject": subject,
            "status": "sent",
            "templateRoles": [role],
        }

    def _build_document_envelope(
        self,
        signer_name: str,
        signer_email: str,
        contract_text: str,
        subject: str,
        client_user_id: str = "",
    ) -> Dict[str, Any]:
        doc_b64 = base64.b64encode(
            (contract_text or "Shartnoma matni").encode("utf-8")
        ).decode("ascii")
        signer: Dict[str, Any] = {
            "email": signer_email,
            "name": signer_name or signer_email,
            "recipientId": "1",
            "routingOrder": "1",
            "tabs": {
                "signHereTabs": [
                    {
                        "anchorString": "/sn1/",
                        "anchorUnits": "pixels",
                        "anchorXOffset": "20",
                        "anchorYOffset": "10",
                    }
                ]
            },
        }
        if client_user_id:
            signer["clientUserId"] = client_user_id
        return {
            "emailSubject": subject,
            "status": "sent",
            "documents": [
                {
                    "documentBase64": doc_b64,
                    "name": "Shartnoma",
                    "fileExtension": "txt",
                    "documentId": "1",
                }
            ],
            "recipients": {"signers": [signer]},
        }

    async def get_envelope_status(self, envelope_id: str) -> Optional[str]:
        if not self.enabled:
            return None
        try:
            resp = await self.client.get(f"/envelopes/{envelope_id}")
            resp.raise_for_status()
            return resp.json().get("status")
        except Exception as e:
            logger.warning(f"[DocuSign] get_envelope_status failed: {e}")
            return None


_instance: Optional[DocuSignSync] = None


def get_docusign() -> DocuSignSync:
    global _instance
    if _instance is None:
        _instance = DocuSignSync()
    return _instance

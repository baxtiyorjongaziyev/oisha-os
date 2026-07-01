"""Free-first text and speech provider routing for Oisha."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Iterable, Optional

import httpx

from src.settings import settings

logger = logging.getLogger(__name__)


class AllProvidersUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderResult:
    text: str
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0


def _text(value: Any) -> str:
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        value = getter()
    return str(value or "").strip()


class FreeAIProviderRouter:
    def __init__(self, settings_obj: Any = settings, http_client: Any = None):
        self.settings = settings_obj
        self.http_client = http_client
        self.blocked_until: dict[str, float] = {}
        self.timeout = float(
            getattr(settings_obj, "FREE_AI_PROVIDER_TIMEOUT_SECONDS", 45) or 45
        )

    def available(self, provider: str) -> bool:
        if self.blocked_until.get(provider, 0) > time.time():
            return False
        if provider == "groq":
            return bool(_text(getattr(self.settings, "GROQ_API_KEY", None)))
        if provider == "cloudflare":
            return bool(
                _text(getattr(self.settings, "CLOUDFLARE_AI_API_TOKEN", None))
                and _text(getattr(self.settings, "CLOUDFLARE_ACCOUNT_ID", None))
            )
        if provider == "ollama":
            return bool(_text(getattr(self.settings, "OLLAMA_BASE_URL", None)))
        return False

    def _pause(self, provider: str, exc: Exception) -> None:
        value = str(exc).lower()
        self.blocked_until[provider] = time.time() + (
            900 if any(x in value for x in ("429", "quota", "rate")) else 60
        )

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if self.http_client is not None:
            response = await self.http_client.request(method, url, **kwargs)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    async def generate_text(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.3,
        providers: Iterable[str] = ("groq", "cloudflare", "ollama"),
    ) -> ProviderResult:
        errors: list[str] = []
        for provider in providers:
            if not self.available(provider):
                continue
            try:
                if provider == "groq":
                    return await self._groq_text(prompt, system, max_tokens, temperature)
                if provider == "cloudflare":
                    return await self._cloudflare_text(prompt, system)
                if provider == "ollama":
                    return await self._ollama_text(prompt, system, temperature)
            except Exception as exc:
                self._pause(provider, exc)
                errors.append(f"{provider}:{type(exc).__name__}")
                logger.warning("[FREE_AI] provider=%s failed: %s", provider, type(exc).__name__)
        raise AllProvidersUnavailableError(", ".join(errors) or "no provider configured")

    async def transcribe_audio(
        self, audio_bytes: bytes, mime_type: str
    ) -> Optional[ProviderResult]:
        for provider in ("groq", "cloudflare"):
            if not self.available(provider):
                continue
            try:
                if provider == "groq":
                    return await self._groq_whisper(audio_bytes, mime_type)
                return await self._cloudflare_whisper(audio_bytes)
            except Exception as exc:
                self._pause(provider, exc)
                logger.warning("[FREE_AI_STT] provider=%s failed: %s", provider, type(exc).__name__)
        return None

    async def _groq_text(
        self, prompt: str, system: Optional[str], max_tokens: int, temperature: float
    ) -> ProviderResult:
        model = self.settings.GROQ_TEXT_MODEL
        messages = ([{"role": "system", "content": system}] if system else [])
        messages.append({"role": "user", "content": prompt})
        response = await self._request(
            "POST",
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {_text(self.settings.GROQ_API_KEY)}"},
            json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
        )
        data = response.json()
        usage = data.get("usage") or {}
        return ProviderResult(
            str(data["choices"][0]["message"]["content"]).strip(),
            "groq",
            model,
            int(usage.get("prompt_tokens") or 0),
            int(usage.get("completion_tokens") or 0),
        )

    async def _groq_whisper(self, audio_bytes: bytes, mime_type: str) -> ProviderResult:
        model = self.settings.GROQ_WHISPER_MODEL
        response = await self._request(
            "POST",
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {_text(self.settings.GROQ_API_KEY)}"},
            files={"file": ("amocrm-call", audio_bytes, mime_type)},
            data={"model": model, "response_format": "json"},
        )
        return ProviderResult(str(response.json().get("text") or "").strip(), "groq", model)

    def _cf_url(self, model: str) -> str:
        return (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{_text(self.settings.CLOUDFLARE_ACCOUNT_ID)}/ai/run/{model}"
        )

    def _cf_headers(self, content_type: str = "application/json") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {_text(self.settings.CLOUDFLARE_AI_API_TOKEN)}",
            "Content-Type": content_type,
        }

    async def _cloudflare_text(self, prompt: str, system: Optional[str]) -> ProviderResult:
        model = self.settings.CLOUDFLARE_TEXT_MODEL
        response = await self._request(
            "POST",
            self._cf_url(model),
            headers=self._cf_headers(),
            json={"prompt": f"{system}\n\n{prompt}" if system else prompt},
        )
        result = response.json().get("result") or {}
        return ProviderResult(str(result.get("response") or "").strip(), "cloudflare", model)

    async def _cloudflare_whisper(self, audio_bytes: bytes) -> ProviderResult:
        model = self.settings.CLOUDFLARE_WHISPER_MODEL
        response = await self._request(
            "POST",
            self._cf_url(model),
            headers=self._cf_headers("application/octet-stream"),
            content=audio_bytes,
        )
        result = response.json().get("result") or {}
        return ProviderResult(str(result.get("text") or "").strip(), "cloudflare", model)

    async def _ollama_text(
        self, prompt: str, system: Optional[str], temperature: float
    ) -> ProviderResult:
        model = self.settings.OLLAMA_TEXT_MODEL
        response = await self._request(
            "POST",
            f"{_text(self.settings.OLLAMA_BASE_URL).rstrip('/')}/generate",
            json={
                "model": model,
                "prompt": f"{system}\n\n{prompt}" if system else prompt,
                "stream": False,
                "options": {"temperature": temperature},
            },
        )
        return ProviderResult(str(response.json().get("response") or "").strip(), "ollama", model)


_router: Optional[FreeAIProviderRouter] = None


def get_free_ai_router() -> FreeAIProviderRouter:
    global _router
    if _router is None:
        _router = FreeAIProviderRouter()
    return _router


def reset_free_ai_router() -> None:
    global _router
    _router = None

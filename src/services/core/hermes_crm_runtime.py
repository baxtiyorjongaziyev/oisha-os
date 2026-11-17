"""Runtime dependencies kept out of the MCP protocol and its contract tests."""
from __future__ import annotations

import asyncio
from urllib.parse import urlparse, urljoin


class LiveCrmApi:
    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from src.services.core.crm.amocrm_sync import AmoCRMSync
            self._client = AmoCRMSync()
        return self._client

    async def read(self, path, params=None):
        import requests
        client = self.client
        response = await client._request_with_auth(
            requests.get, client.base_url + '/api/v4' + path, params=params, timeout=30)
        if response.status_code == 204:
            return {}
        if response.status_code != 200:
            raise RuntimeError('amocrm_http_' + str(response.status_code))
        return response.json()


def recording_url(url, domain):
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or parsed.hostname != domain or
            parsed.port not in (None, 443) or parsed.username or parsed.password):
        raise ValueError('recording_host_not_allowed')
    return url


def moizvonki_login(session, domain, settings):
    """Login only at the configured host; never expose cookies or credentials."""
    import re
    email = getattr(settings, 'MOIZVONKI_EMAIL', '')
    password = getattr(settings, 'MOIZVONKI_PASSWORD', '')
    if hasattr(password, 'get_secret_value'):
        password = password.get_secret_value()
    if not email or not password:
        return False
    url = 'https://' + domain + '/accounts/login/'
    response = session.get(url, timeout=20, allow_redirects=False)
    match = re.search(r"name=[\x22\x27]csrfmiddlewaretoken[\x22\x27]\s+value=[\x22\x27]([^\x22\x27]+)", response.text)
    csrf = match.group(1) if match else session.cookies.get('csrftoken')
    if not csrf:
        return False
    session.post(url, data={'csrfmiddlewaretoken': csrf, 'username': email,
                           'password': password, 'foreign_pc': 'on'},
                 headers={'Referer': url}, timeout=20, allow_redirects=False)
    return bool(session.cookies.get('sessionid'))


def download_recording(url, settings, max_bytes=20 * 1024 * 1024):
    import requests
    domain = getattr(settings, 'MOIZVONKI_DOMAIN', '') or 'jonbrandingagency.moizvonki.ru'
    domain = domain.replace('https://', '').rstrip('/')
    recording_url(url, domain)
    with requests.Session() as session:
        moizvonki_login(session, domain, settings)
        for _ in range(4):
            with session.get(url, stream=True, timeout=35, allow_redirects=False) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    url = recording_url(urljoin(url, response.headers['Location']), domain)
                    continue
                if response.status_code != 200:
                    raise RuntimeError('recording_http_' + str(response.status_code))
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > max_bytes:
                        raise RuntimeError('recording_too_large')
                    chunks.append(chunk)
                data = b''.join(chunks)
                mime = response.headers.get('Content-Type', '').split(';')[0]
                if (not data or len(data) == 60027 or data.lstrip().startswith((b'<', b'{'))):
                    raise RuntimeError('recording_not_audio')
                if not mime.startswith(('audio/', 'video/')):
                    mime = 'audio/mpeg'
                return data, mime
        raise RuntimeError('recording_redirect_limit')


class RecordingTranscriber:
    def __init__(self, api):
        self.api = api
        self._analyzer = None

    async def __call__(self, url, duration):
        from src.services.call_analytics.analyzer import CallAnalyzer
        from src.services.call_analytics.helpers import (
            _looks_like_stt_hallucination, _transcript_impossible_for_duration)
        if duration > 1800:
            raise RuntimeError('recording_over_30_minutes')
        if self._analyzer is None:
            self._analyzer = CallAnalyzer(self.api.client)
        analyzer = self._analyzer
        audio, mime = await asyncio.to_thread(download_recording, url, analyzer._settings)
        text = await analyzer._transcribe_inline(audio, mime)
        if (not text or _looks_like_stt_hallucination(text) or
                _transcript_impossible_for_duration(text, duration)):
            return None
        return text

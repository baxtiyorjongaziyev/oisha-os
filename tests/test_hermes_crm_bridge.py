"""Read-only CRM boundary contracts; all customer data here is synthetic."""
import pytest

from src.services.core.hermes_crm_bridge import HermesCrmBridge, RpcServer
from src.services.core.hermes_crm_runtime import recording_url


class FakeApi:
    base_url = 'https://example.amocrm.ru'

    async def read(self, path, params=None):
        if path.endswith('/notes/7'):
            return {'id': 7, 'entity_id': 42, 'note_type': 'call_out',
                    'params': {'duration': 80, 'link': 'https://safe.moizvonki.ru/a.mp3'}}
        return {'_embedded': {'notes': [
            {'id': 7, 'entity_id': 42, 'note_type': 'call_out',
             'created_at': 1793355418, 'params': {'duration': 80, 'link': 'private-url'}},
            {'id': 8, 'entity_id': 42, 'note_type': 'call_out',
             'params': {'duration': 0}},
        ]}}


@pytest.mark.asyncio
async def test_recent_calls_are_evidence_with_no_recording_urls():
    result = await HermesCrmBridge(FakeApi()).list_calls(limit=5)
    assert result['success'] is True
    assert result['calls'][0]['note_id'] == 7
    assert result['calls'][0]['duration_seconds'] == 80
    assert result['calls'][0]['has_recording'] is True
    assert 'private-url' not in str(result)


@pytest.mark.asyncio
async def test_transcript_uses_server_note_and_never_writes_crm():
    async def transcribe(url, duration):
        assert url == 'https://safe.moizvonki.ru/a.mp3'
        return '[00:01] Menejer: Sintetik sinov.\n[00:05] Mijoz: Sinov javobi.'
    bridge = HermesCrmBridge(FakeApi(), transcribe)
    result = await bridge.transcript('contacts', 42, 7)
    assert result['success'] is True
    assert result['audio_processed'] is True
    assert result['crm_modified'] is False
    assert result['talk_ratio'] is None


@pytest.mark.asyncio
async def test_unavailable_transcript_is_not_success_or_zero():
    async def unavailable(url, duration):
        return None
    result = await HermesCrmBridge(FakeApi(), unavailable).transcript('contacts', 42, 7)
    assert result['success'] is False
    assert result['status'] == 'transcription_unavailable'
    assert 'transcript' not in result


@pytest.mark.asyncio
async def test_rpc_rejects_writes_unknown_tools_and_bad_entity():
    rpc = RpcServer(HermesCrmBridge(FakeApi()))
    for name in ['delete_note', 'execute_shell', 'add_lead_note']:
        r = await rpc.respond({'id': 1, 'method': 'tools/call',
                               'params': {'name': name, 'arguments': {}}})
        assert r['result']['isError'] is True
    with pytest.raises(ValueError):
        await rpc.bridge.transcript('../../etc', 42, 7)


@pytest.mark.asyncio
async def test_rpc_lists_tools_and_initializes_without_api_access():
    rpc = RpcServer(HermesCrmBridge(FakeApi()))
    r = await rpc.respond({'id': 1, 'method': 'initialize',
                           'params': {'protocolVersion': '2025-03-26'}})
    assert r['result']['capabilities'] == {'tools': {}}
    r = await rpc.respond({'id': 2, 'method': 'tools/list'})
    assert {t['name'] for t in r['result']['tools']} == {
        'crm_search_leads', 'crm_list_calls', 'crm_get_call_transcript'}
    assert all(t['annotations']['readOnlyHint'] for t in r['result']['tools'])


@pytest.mark.parametrize('url', [
    'http://safe.moizvonki.ru/a.mp3', 'https://127.0.0.1/a.mp3',
    'https://safe.moizvonki.ru.evil.example/a.mp3',
    'https://user:password@safe.moizvonki.ru/a.mp3',
    'https://safe.moizvonki.ru:8443/a.mp3',
])
def test_recordings_cannot_be_arbitrary_urls(url):
    with pytest.raises(ValueError):
        recording_url(url, 'safe.moizvonki.ru')


@pytest.mark.asyncio
async def test_failed_crm_read_does_not_look_like_no_calls():
    class FailedApi:
        async def read(self, *args):
            raise RuntimeError('amocrm_http_401')
    result = await HermesCrmBridge(FailedApi()).list_calls()
    assert result['success'] is False
    assert result['status'] == 'partial'
    assert len(result['errors']) == 2


@pytest.mark.asyncio
async def test_wrong_note_identity_cannot_be_transcribed():
    with pytest.raises(ValueError, match='note_identity_mismatch'):
        await HermesCrmBridge(FakeApi()).transcript('contacts', 99, 7)


@pytest.mark.asyncio
async def test_recording_failure_is_actionable_without_leaking_urls():
    async def failed(url, duration):
        raise RuntimeError('recording_http_502')
    rpc = RpcServer(HermesCrmBridge(FakeApi(), failed))
    result = await rpc.call({'name': 'crm_get_call_transcript', 'arguments': {
        'entity_type': 'contacts', 'entity_id': 42, 'note_id': 7}})
    assert result['isError'] is True
    assert 'recording_http_502' in result['content'][0]['text']
    assert 'https://' not in result['content'][0]['text']

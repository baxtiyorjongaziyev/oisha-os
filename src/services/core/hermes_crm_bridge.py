"""Small CRM & AI Agent Fleet surface for the independent Hermes Telegram gateway."""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone


def positive(value):
    if isinstance(value, bool) or not str(value).isdigit() or int(value) < 1:
        raise ValueError('positive_integer_required')
    return int(value)


def entity_path(entity_type, entity_id):
    if entity_type not in {'contacts', 'leads'}:
        raise ValueError('invalid_entity_type')
    return f'/{entity_type}/{positive(entity_id)}'


def call_evidence(note, entity_type):
    params = note.get('params') or {}
    timestamp = note.get('created_at')
    return {
        'note_id': note['id'], 'entity_type': entity_type,
        'entity_id': note.get('entity_id'),
        'responsible_user_id': note.get('responsible_user_id'),
        'created_at': timestamp,
        'created_at_utc': datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
        if timestamp else None,
        'duration_seconds': int(params.get('duration') or 0),
        'direction': note.get('note_type'),
        'has_recording': bool(params.get('link')),
    }


class HermesCrmBridge:
    def __init__(self, api, transcribe=None):
        self.api = api
        self.transcribe = transcribe

    async def search_leads(self, query, limit=10):
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 200:
            raise ValueError('invalid_query')
        data = await self.api.read('/leads', {
            'query': query.strip(), 'limit': min(positive(limit), 25), 'with': 'contacts'})
        leads = [{k: n.get(k) for k in
                  ['id', 'name', 'responsible_user_id', 'status_id', 'pipeline_id', 'updated_at']}
                 | {'contact_ids': [c['id'] for c in n.get('_embedded', {}).get('contacts', [])]}
                 for n in data.get('_embedded', {}).get('leads', [])]
        return {'success': True, 'source': 'amocrm_live', 'leads': leads}

    async def list_calls(self, limit=10, entity_type=None, entity_id=None, page=1):
        limit = min(positive(limit), 25)
        page = min(positive(page), 20)
        if entity_type is not None and entity_type not in {'contacts', 'leads'}:
            raise ValueError('invalid_entity_type')
        if entity_id is not None and entity_type is None:
            raise ValueError('entity_type_required')
        calls, failures = [], []
        for kind in [entity_type] if entity_type else ['contacts', 'leads']:
            path = entity_path(kind, entity_id) if entity_id is not None else '/' + kind
            try:
                data = await self.api.read(path + '/notes', [
                    ('filter[note_type][]', 'call_in'), ('filter[note_type][]', 'call_out'),
                    ('order[updated_at]', 'desc'), ('limit', limit), ('page', page)])
                calls.extend(call_evidence(n, kind) for n in
                             data.get('_embedded', {}).get('notes', [])
                             if n.get('note_type') in {'call_in', 'call_out'})
            except RuntimeError as exc:
                failures.append({'entity_type': kind, 'error': str(exc)})
        calls.sort(key=lambda n: n['created_at'] or 0, reverse=True)
        return {'success': not failures, 'status': 'partial' if failures else 'ok',
                'source': 'amocrm_live', 'calls': calls, 'errors': failures,
                'page': page, 'scope': 'bounded_page_per_entity_type',
                'guidance': 'Choose a call with recording and nonzero duration. '
                'Use crm_get_call_transcript before judging the conversation.'}

    async def transcript(self, entity_type, entity_id, note_id):
        path = entity_path(entity_type, entity_id)
        note = await self.api.read(path + '/notes/' + str(positive(note_id)))
        if note.get('note_type') not in {'call_in', 'call_out'}:
            raise ValueError('not_a_call_note')
        if note.get('entity_id') != positive(entity_id) or note.get('id') != positive(note_id):
            raise ValueError('note_identity_mismatch')
        evidence = call_evidence(note, entity_type)
        url = (note.get('params') or {}).get('link')
        if not url or not evidence['duration_seconds']:
            return {'success': False, 'status': 'recording_unavailable', 'call': evidence}
        if self.transcribe is None:
            raise RuntimeError('transcription_not_configured')
        text = await self.transcribe(url, evidence['duration_seconds'])
        if not text:
            return {'success': False, 'status': 'transcription_unavailable', 'call': evidence}
        return {'success': True, 'source': 'amocrm_recording_stt', 'call': evidence,
                'transcript': text, 'audio_processed': True, 'crm_modified': False,
                'talk_ratio': None, 'guidance':
                'STT can contain errors. Quote exact transcript evidence, distinguish inference, '
                'do not invent names or speaker timing. No measured 70/30 ratio is available.'}

    async def get_team_roster(self, include_owner=True, role=None):
        from src.services.core.crm.team_roster import EXCLUDED_NON_STAFF_SLUGS, get_active_staff
        roles = (str(role).strip().lower(),) if role else None
        staff = get_active_staff(include_owner=bool(include_owner), roles=roles)
        return {
            'success': True,
            'source': 'team_roster_ssot',
            'staff': [
                {
                    'slug': m.slug,
                    'name': m.name,
                    'role': m.role,
                    'title': m.title,
                    'tg_user_id': m.tg_user_id,
                    'tg_username': m.tg_username,
                    'tg_markdown_mention': m.tg_markdown_mention(),
                    'amocrm_user_id': m.amocrm_user_id,
                    'moizvonki_emails': list(m.moizvonki_emails),
                }
                for m in staff
            ],
            'excluded_non_staff': sorted(EXCLUDED_NON_STAFF_SLUGS),
            'guidance': 'Only members in this list are verified Jon Branding staff. Never treat CRM client/lead names as staff.',
        }

    async def get_rop_digest(self, seller_query=None):
        """Return live AI ROP 50/20/10/3/1 funnel targets and today's Moizvonki call metrics per seller."""
        from src.services.core.crm.team_roster import find_staff, get_active_staff
        from src.services.core.rop.fetchers import RopFetcher
        from src.services.core.rop.service import _find_seller_calls
        from src.services.sales_quality.funnel_policy import daily_funnel_policy
        from src.time_utils import get_local_now

        now = get_local_now()
        policy = daily_funnel_policy()
        stage_map = {st['key']: st['target'] for st in policy.get('stages', [])}
        funnel_targets = {
            'answered_calls': stage_map.get('answered_180s', 50),
            'meaningful': stage_map.get('meaningful', 20),
            'evqn_invited': stage_map.get('evqn_invited', 10),
            'meeting_held': stage_map.get('meeting_held', 3),
            'sale': stage_map.get('sale', 1),
        }
        sellers = get_active_staff(include_owner=False, roles=('seller',))
        if seller_query:
            matched = find_staff(str(seller_query))
            if matched and matched.role == 'seller':
                sellers = [matched]

        fetcher = RopFetcher(None)
        try:
            today_calls = await fetcher.fetch_today_calls(now)
        except Exception:
            today_calls = {}

        rows = []
        for s in sellers:
            c = _find_seller_calls(s.name, today_calls)
            solid = int(c.get('solid_calls', 0))
            total = int(c.get('total', 0))
            answered = int(c.get('answered', 0))
            talk_sec = int(c.get('talk_seconds', 0))
            no_cb = int(c.get('no_callback', 0))
            rows.append({
                'slug': s.slug,
                'name': s.name,
                'tg_user_id': s.tg_user_id,
                'tg_username': s.tg_username,
                'tg_markdown_mention': s.tg_markdown_mention(),
                'amocrm_user_id': s.amocrm_user_id,
                'funnel_targets': dict(funnel_targets),
                'today_telephony': {
                    'total_calls': total,
                    'answered_calls': answered,
                    'solid_calls_ge_3m': solid,
                    'solid_calls_target': funnel_targets['answered_calls'],
                    'solid_calls_pct': round(solid / funnel_targets['answered_calls'] * 100, 1)
                    if funnel_targets['answered_calls'] else 0.0,
                    'talk_minutes': round(talk_sec / 60, 1),
                    'missed_no_callback': no_cb,
                },
            })

        return {
            'success': True,
            'source': 'ai_rop_live',
            'as_of_tashkent': now.isoformat(),
            'funnel_standard': '50 suhbat (>=3 daq) -> 20 mazmunli -> 10 EVQN taklif -> 3 uchrashuv -> 1 sotuv',
            'sellers': rows,
            'guidance': 'Distinguish funnel_targets (50/20/10/3/1 plan) from today_telephony (observed Moizvonki actuals).',
        }

    async def ai_fleet_status(self):
        from src.services.core.ai_agent_orchestrator import evaluate_fleet_status
        return evaluate_fleet_status()

    async def ai_fleet_hire(self, blueprint_slug=None, name=None, prompt=None, cron_expr=None, deliver='telegram:-1003114662117'):
        from src.services.core.ai_agent_orchestrator import hire_ai_agent
        return hire_ai_agent(
            blueprint_slug=blueprint_slug,
            name=name,
            prompt=prompt,
            cron_expr=cron_expr,
            deliver=deliver,
        )

    async def ai_fleet_fire(self, agent_id_or_name, remove_permanently=False):
        from src.services.core.ai_agent_orchestrator import fire_ai_agent
        return fire_ai_agent(agent_id_or_name, remove_permanently=bool(remove_permanently))

    async def ai_fleet_revive(self, auto_fire_zombies=True, auto_hire_missing_core=False):
        from src.services.core.ai_agent_orchestrator import revive_or_cleanup_fleet
        return revive_or_cleanup_fleet(
            auto_fire_zombies=bool(auto_fire_zombies),
            auto_hire_missing_core=bool(auto_hire_missing_core),
        )

    async def devops_server_status(self, include_logs=True):
        from src.services.core.devops_agent import inspect_server_status
        return inspect_server_status(include_logs=bool(include_logs))

    async def devops_server_heal(self, auto_restart_failed=False):
        from src.services.core.devops_agent import heal_server_services
        return heal_server_services(auto_restart_failed=bool(auto_restart_failed))


def tool(name, description, properties, required=(), read_only=True):
    return {'name': name, 'description': description,
            'inputSchema': {'type': 'object', 'properties': properties,
                            'required': list(required), 'additionalProperties': False},
            'annotations': {'readOnlyHint': bool(read_only), 'destructiveHint': False}}


INTEGER = {'type': 'integer', 'minimum': 1}
ENTITY = {'type': 'string', 'enum': ['contacts', 'leads']}
TOOLS = [
    tool('crm_search_leads', 'Search live amoCRM by client name or phone; returns linked contact IDs.',
         {'query': {'type': 'string'}, 'limit': INTEGER}, ['query']),
    tool('crm_list_calls', "Read real recent amoCRM calls. Without IDs searches contacts AND leads. "
         "For 'bitta qo‘ng‘iroqni tahlil qil', select a recorded nonzero call yourself.",
         {'limit': INTEGER, 'entity_type': ENTITY, 'entity_id': INTEGER, 'page': INTEGER}),
    tool('crm_get_call_transcript', 'Fetch the selected CRM call recording and transcribe actual audio. '
         'Use before analyzing mistakes. No CRM writes or Telegram messages. May take 3 minutes.',
         {'entity_type': ENTITY, 'entity_id': INTEGER, 'note_id': INTEGER},
         ['entity_type', 'entity_id', 'note_id']),
    tool('crm_get_team_roster', 'Return the canonical Single Source of Truth (SSoT) active team roster (names, roles, Telegram IDs, handles, AmoCRM/Moizvonki accounts).',
         {'include_owner': {'type': 'boolean'}, 'role': {'type': 'string'}}),
    tool('crm_get_rop_digest', 'Return live AI ROP 50/20/10/3/1 daily funnel targets and today Moizvonki telephony execution metrics per seller.',
         {'seller_query': {'type': 'string'}}),
    tool('ai_fleet_status', 'Audit all AI agents (Oisha-OS + Hermes), report optimal team size, active/stalled/zombie agents, and recommend missing AI agents.',
         {}),
    tool('ai_fleet_hire', 'Hire (create or re-enable) an AI agent from a canonical blueprint_slug (e.g. ai_hr_evening_18, ai_debitor_finance) or custom name/prompt/cron_expr.',
         {'blueprint_slug': {'type': 'string'}, 'name': {'type': 'string'},
          'prompt': {'type': 'string'}, 'cron_expr': {'type': 'string'},
          'deliver': {'type': 'string'}}, read_only=False),
    tool('ai_fleet_fire', 'Fire (disable or remove) an inactive, duplicate, or zombie AI agent by job_id, name, or slug.',
         {'agent_id_or_name': {'type': 'string'}, 'remove_permanently': {'type': 'boolean'}},
         ['agent_id_or_name'], read_only=False),
    tool('ai_fleet_revive', 'Self-heal stalled/failed AI agents, disable zombie/duplicate cron jobs, and optionally auto-hire missing core blueprint agents.',
         {'auto_fire_zombies': {'type': 'boolean'}, 'auto_hire_missing_core': {'type': 'boolean'}},
         read_only=False),
    tool('devops_server_status', 'Inspect live Contabo VPS status: CPU load, RAM, disk, systemd services, Docker containers, /healthz, /readyz, and recent error logs.',
         {'include_logs': {'type': 'boolean'}}),
    tool('devops_server_heal', 'Self-heal Contabo VPS by auditing systemd services and optionally restarting failed allowlisted services (oisha-os, oisha-watchdog, hermes-gateway, shirinlaxza-bot).',
         {'auto_restart_failed': {'type': 'boolean'}}, read_only=False),
]


class RpcServer:
    def __init__(self, bridge):
        self.bridge = bridge

    async def respond(self, request):
        if 'id' not in request:
            return None
        response = {'jsonrpc': '2.0', 'id': request['id']}
        method = request.get('method')
        if method == 'initialize':
            result = {'protocolVersion': request.get('params', {}).get(
                'protocolVersion', '2025-03-26'), 'capabilities': {'tools': {}},
                'serverInfo': {'name': 'oisha-crm-readonly', 'version': '1.0.0'}}
        elif method == 'tools/list':
            result = {'tools': TOOLS}
        elif method == 'ping':
            result = {}
        elif method == 'tools/call':
            result = await self.call(request.get('params', {}))
        else:
            return response | {'error': {'code': -32601, 'message': 'Method not found'}}
        return response | {'result': result}

    async def call(self, params):
        methods = {
            'crm_search_leads': self.bridge.search_leads,
            'crm_list_calls': self.bridge.list_calls,
            'crm_get_call_transcript': self.bridge.transcript,
            'crm_get_team_roster': self.bridge.get_team_roster,
            'crm_get_rop_digest': self.bridge.get_rop_digest,
            'ai_fleet_status': self.bridge.ai_fleet_status,
            'ai_fleet_hire': self.bridge.ai_fleet_hire,
            'ai_fleet_fire': self.bridge.ai_fleet_fire,
            'ai_fleet_revive': self.bridge.ai_fleet_revive,
            'devops_server_status': self.bridge.devops_server_status,
            'devops_server_heal': self.bridge.devops_server_heal,
        }
        try:
            fn = methods.get(params.get('name'))
            if fn is None:
                raise ValueError('unknown_read_tool')
            result = await asyncio.wait_for(fn(**params.get('arguments', {})), timeout=210)
        except (ValueError, TypeError):
            result = {'success': False, 'status': 'invalid_tool_or_arguments'}
        except TimeoutError:
            result = {'success': False, 'status': 'source_timeout'}
        except RuntimeError as exc:
            code = str(exc)
            safe = re.fullmatch(r'(?:amocrm|recording)_http_[1-5][0-9]{2}|'
                                r'recording_(?:too_large|not_audio|redirect_limit|over_30_minutes)|'
                                r'transcription_not_configured', code)
            result = {'success': False, 'status': code if safe else 'source_unavailable'}
        except Exception:
            result = {'success': False, 'status': 'source_unavailable'}
        return {'content': [{'type': 'text', 'text': json.dumps(result, ensure_ascii=False)}],
                'isError': not result.get('success', False)}

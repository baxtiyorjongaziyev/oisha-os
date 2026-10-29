import sqlite3

from src.services.core.ai.hermes_context import HermesSessionStore
from src.services.core.ai.hermes_harness import HermesInvariantEvaluator
from src.services.response_quality.delivery_ledger import DeliveryLedger


def test_sessions_survive_restart_and_remain_scoped(tmp_path):
    path = str(tmp_path / 'sessions.db')
    first = HermesSessionStore(db_path=path)
    first.set_session('telegram:group:1', '42', 'synthetic-session')
    restarted = HermesSessionStore(db_path=path)
    assert restarted.get_session('telegram:group:1', '42') == 'synthetic-session'
    assert restarted.get_session('telegram:group:2', '42') is None
    assert restarted.get_session('telegram:group:1', '43') is None
    restarted.clear_session('telegram:group:1', '42')
    assert first.get_session('telegram:group:1', '42') is None


def test_expired_session_is_not_restored(tmp_path):
    path = str(tmp_path / 'sessions.db')
    store = HermesSessionStore(db_path=path)
    store.set_session('synthetic', '42', 'expired')
    with sqlite3.connect(path) as db:
        db.execute('UPDATE sessions SET accessed=0')
    assert store.get_session('synthetic', '42') is None
    assert store.total_active_sessions() == 0


def test_uncertain_delivery_requires_verified_resolution(tmp_path):
    ledger = DeliveryLedger(str(tmp_path / 'outbox.db'))
    assert ledger.claim('synthetic:1', 'Synthetic message')
    assert not ledger.claim('synthetic:1', 'Synthetic message')
    assert ledger.reconcile('synthetic:1', verified_message_id='123')
    assert not ledger.reconcile('synthetic:1', verified_not_sent=True)
    assert not ledger.claim('synthetic:1', 'Synthetic message')


def test_verified_absence_allows_retry(tmp_path):
    ledger = DeliveryLedger(str(tmp_path / 'outbox.db'))
    assert ledger.claim('synthetic:2', 'Synthetic message')
    ledger.finish('synthetic:2', None)
    assert ledger.reconcile('synthetic:2', verified_not_sent=True)
    assert ledger.claim('synthetic:2', 'Synthetic message')


def test_hermes_rejects_reported_repetition():
    result = HermesInvariantEvaluator.evaluate('Shaxboz aka bilan qayta gaplasha oldingizmi? ' * 4)
    assert not result.is_valid
    assert 'repeated_sentence' in result.violations

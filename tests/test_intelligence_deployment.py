"""Synthetic route integration and provider fallback acceptance checks."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.rbac import Principal, Role
from src.services.sales_quality import intelligence_routes as routes
from src.services.sales_quality.reviews import QualityReviews
from src.services.call_analytics.quality_hook import contextual_review


def test_routes_scope_reviews_and_template(tmp_path, monkeypatch):
    store = QualityReviews(tmp_path / 'reviews.sqlite3')
    evaluation = {'review_ready': True, 'score': 80, 'criteria': [], 'coverage': 1,
                  'sales_quality': True, 'label': 'Test', 'call_type': 'discovery'}
    revision = store.save('mine', 1, 7, evaluation)
    store.save('other', 2, 8, evaluation)
    monkeypatch.setattr(routes, 'QualityReviews', lambda: store)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.READ.dependency] = lambda: Principal('7', Role.SELLER, 'test')
    with TestClient(app) as client:
        assert client.get('/dashboard/conversation-intelligence').status_code == 200
        assert len(client.get('/api/sales-quality/scorecards').json()['scorecards']) == 18
        assert [x['call_id'] for x in client.get('/api/sales-quality/evaluations').json()['evaluations']] == ['mine']
        payload = {'revision': revision, 'decision': 'approved', 'reason': 'test'}
        assert client.post('/api/sales-quality/evaluations/mine/review', json=payload).status_code == 403
        payload['decision'] = 'appealed'
        assert client.post('/api/sales-quality/evaluations/other/review', json=payload).status_code == 404
        assert client.post('/api/sales-quality/evaluations/mine/review', json=payload).status_code == 200
        app.dependency_overrides[routes.READ.dependency] = lambda: Principal('owner', Role.OWNER, 'test')
        payload['decision'] = 'approved'
        assert client.post('/api/sales-quality/evaluations/mine/review', json=payload).status_code == 200


@pytest.mark.asyncio
async def test_contextual_provider_fallback(monkeypatch):
    monkeypatch.setenv('SKIP_LIVE', '0')
    router = SimpleNamespace(generate_text=AsyncMock(return_value=SimpleNamespace(text=json.dumps({
        'conversation_type': 'personal', 'type_confidence': .9, 'type_evidence': 'Shaxsiy suhbat'}))))
    analyzer = SimpleNamespace(_gemini_generate_content=AsyncMock(side_effect=RuntimeError('test')),
                               free_ai_router=router)
    result = await contextual_review(analyzer, 'Shaxsiy suhbat')
    assert result['call_type'] == 'personal'
    router.generate_text.assert_awaited_once()

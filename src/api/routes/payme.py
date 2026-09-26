"""Payme Merchant API endpoint for Oisha invoices."""
from __future__ import annotations

import base64
import hmac
import os
from typing import Any

from fastapi import APIRouter, Request

from src.api.routes.state import api_state

router = APIRouter(tags=["payme"])


def _reply(request_id: Any, result: Any = None, error: dict | None = None) -> dict:
    body = {"jsonrpc": "2.0", "id": request_id}
    body["error" if error else "result"] = error if error else result
    return body


def _error(request_id: Any, code: int, message: str) -> dict:
    return _reply(request_id, error={"code": code, "message": message})


def _authorized(request: Request) -> bool:
    expected = (os.getenv("PAYME_KEY") or "").strip()
    header = request.headers.get("Authorization", "")
    if not expected or not header.startswith("Basic "):
        return False
    try:
        supplied = base64.b64decode(header[6:]).decode("utf-8").split(":", 1)[1]
    except (ValueError, UnicodeDecodeError, IndexError):
        return False
    return hmac.compare_digest(supplied, expected)


def _is_enabled() -> bool:
    val = (os.getenv("PAYME_ENABLED") or "").strip().lower()
    return val in {"1", "true", "yes"}


def _account_id(params: dict) -> int | None:
    value = params.get("account", {}).get("invoice_id")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def _invoice(invoice_id: int) -> dict | None:
    if api_state.db_instance is None:
        return None
    rows = await api_state.db_instance.execute(
        "SELECT id, amount, paid_amount, status FROM invoices WHERE id = ?",
        [invoice_id],
    )
    return dict(rows[0]) if rows else None


@router.post("/payme")
@router.post("/api/payme")
async def payme_merchant_api(request: Request) -> dict:
    payload = await request.json()
    request_id = payload.get("id")
    if not _is_enabled():
        return _error(request_id, -31008, "Невозможно выполнить операцию: интеграция отключена")
    if not _authorized(request):
        return _error(request_id, -32504, "Недостаточно привилегий для выполнения метода")

    method = payload.get("method")
    params = payload.get("params") or {}
    invoice_id = _account_id(params)
    if invoice_id is None:
        return _error(request_id, -31050, "Неверный код заказа")
    invoice = await _invoice(invoice_id)
    if invoice is None:
        return _error(request_id, -31050, "Неверный код заказа")

    amount = int(params.get("amount", 0))
    expected_amount = int(invoice["amount"]) * 100
    if method in {"CheckPerformTransaction", "CreateTransaction"} and amount != expected_amount:
        return _error(request_id, -31001, "Неверная сумма")
    if method == "CheckPerformTransaction":
        if invoice["status"] == "paid":
            return _error(request_id, -31008, "Невозможно выполнить операцию")
        return _reply(request_id, {"allow": True})
    if method == "CreateTransaction":
        return _reply(request_id, {"create_time": 0, "transaction": str(invoice_id), "state": 1})
    if method == "PerformTransaction":
        if api_state.db_instance is not None:
            await api_state.db_instance.execute(
                "UPDATE invoices SET paid_amount = ?, status = 'paid' WHERE id = ?",
                [int(invoice["amount"]), invoice_id],
            )
            await api_state.db_instance.commit()
        return _reply(request_id, {"transaction": str(invoice_id), "perform_time": 0, "state": 2})
    if method == "CheckTransaction":
        state = 2 if invoice["status"] == "paid" else 1
        return _reply(request_id, {"create_time": 0, "perform_time": 0, "cancel_time": 0, "transaction": str(invoice_id), "state": state})
    if method == "CancelTransaction":
        return _reply(request_id, {"cancel_time": 0, "state": -1})
    return _error(request_id, -32601, "Метод не найден")


__all__ = ["router"]

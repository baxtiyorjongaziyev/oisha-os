"""Proposal-only sales KPI simulation. No payroll writes or automatic activation."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from src.services.sales_quality.funnel_policy import daily_funnel_policy

POLICY = {
    "version": "jonbranding-pilot-v1", "status": "proposal", "payroll_enabled": False,
    "weights": {"result": 50, "discipline": 25, "quality": 25},
    "minimum_reviewed_calls": 20,
    "daily_funnel": daily_funnel_policy(),
    "quality_basis": "human-approved sales evaluations in review window; not call occurrence window",
}


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        value = Decimal(str(value))
    except InvalidOperation:
        return None
    return value if value.is_finite() and value >= 0 else None


def percent(done, target):
    done, target = number(done), number(target)
    if done is None or target is None or target <= 0:
        return None
    return min(Decimal(100), done * 100 / target)


def quality_component(evaluations, manager_id, start, end, minimum=20):
    eligible = {}
    groups = {}
    for row in evaluations:
        if str(row.get("manager_id")) != str(manager_id):
            continue
        reviews = row.get("reviews") or []
        if not reviews or not start <= reviews[-1].get("created_at", 0) < end:
            continue
        if not row.get("quality_approved") or not row.get("sales_quality"):
            continue
        score = number(row.get("reviewed_score") if row.get("reviewed_score") is not None else row.get("score"))
        if score is None or score > 100:
            continue
        if row.get("call_id"):
            eligible[row["call_id"]] = (row.get("call_type", "unknown"), score)
    # Protect against repeated rows inflating the sample threshold.
    for kind, score in eligible.values():
        groups.setdefault(kind, []).append(score)
    scores = [score for _, score in eligible.values()]
    return {
        "score": sum(scores) / len(scores) if len(scores) >= minimum else None,
        "reviewed_calls": len(scores), "required_calls": minimum,
        "by_type": {kind: {"count": len(values), "score": float(sum(values) / len(values))}
                    for kind, values in groups.items()},
        "reason": None if len(scores) >= minimum else "insufficient_reviewed_sales_calls",
    }


def simulate_kpi(*, actual, target, completed_on_time, tasks_due, quality, bonus_pool=None, currency=None):
    result = percent(actual, target)
    completed, due = number(completed_on_time), number(tasks_due)
    if completed is not None and due is not None and completed > due:
        raise ValueError("completed_exceeds_due")
    discipline = percent(completed_on_time, tasks_due)
    q = number(quality.get("score"))
    if q is not None and q > 100:
        raise ValueError("quality_out_of_range")
    components = {"result": result, "discipline": discipline, "quality": q}
    complete = all(value is not None for value in components.values())
    total = sum(value * POLICY["weights"][key] / 100 for key, value in components.items()) if complete else None
    pool = number(bonus_pool)
    if bonus_pool is not None and (pool is None or currency not in {"UZS", "USD"}):
        raise ValueError("invalid_bonus_pool_or_currency")
    projected = (pool * total / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if pool is not None and total is not None else None
    return {
        "policy": POLICY, "complete": complete,
        "components": {key: float(value) if value is not None else None for key, value in components.items()},
        "missing": [key for key, value in components.items() if value is None],
        "total_score": float(total) if total is not None else None,
        "quality": {**quality, "score": float(q) if q is not None else None},
        "projected_bonus": str(projected) if projected is not None else None, "currency": currency,
        "input_provenance": "owner_supplied_simulation_values_not_ledger_verified",
        "payroll_enabled": False, "payment_created": False,
    }

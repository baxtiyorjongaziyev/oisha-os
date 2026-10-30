"""Owner-stated daily funnel targets; not observed performance or payroll rules."""
from decimal import Decimal, InvalidOperation, ROUND_CEILING


def daily_funnel_policy():
    """Return fresh policy data so callers cannot mutate shared targets."""
    return {
        "version": "jonbranding-daily-funnel-v1",
        "source": "owner_statement_2026-10-30",
        "status": "owner_stated_targets_definitions_incomplete",
        "period": "working_day",
        "timezone": "Asia/Tashkent",
        "counting_unit": "distinct_customer_per_stage",
        "stages": [
            {"key": "answered_180s", "label": "Kamida 3 daqiqalik javobli mijoz suhbati",
             "target": 50, "minimum_talk_seconds": 180},
            {"key": "meaningful", "label": "Mazmunli suhbat", "target": 20},
            {"key": "evqn_invited", "label": "EVQN bo‘yicha uchrashuvga taklif", "target": 10},
            {"key": "meeting_held", "label": "O‘tkazilgan offline yoki online uchrashuv", "target": 3},
            {"key": "sale", "label": "Sotuv", "target": 1},
        ],
        "planning": {"assumed_answer_rate": 0.5, "estimated_attempts": planned_attempts("0.5"),
                     "attempts_are_kpi_target": False, "minimum_talk_minutes": 150},
        "meaningful_criteria": ["customer_confirmed_need", "service_fit", "agreed_next_step"],
        "meaningful_status": "adapted_pilot_requires_human_review",
        "evqn": {"E": "Ehtiyoj", "V": "Qachonga kerak", "Q": "Qaror qabul qiluvchi va jarayon",
                 "N": "Narx va mijoz munosabati"},
        "unresolved_definitions": ["sale_confirmation",
                                   "single_call_vs_cumulative_talk_time", "conversion_attribution_window"],
        "cohort_note": "Daily activity and later cohort outcomes must be reported separately; no same-day loss inference.",
        "observed_counts": None,
        "payroll_enabled": False,
    }


def planned_attempts(answer_rate):
    """Planning estimate only; an unknown answer rate cannot produce a count."""
    if answer_rate is None:
        return None
    try:
        rate = Decimal(str(answer_rate))
    except InvalidOperation:
        raise ValueError("invalid_answer_rate") from None
    if not rate.is_finite() or not 0 < rate <= 1:
        raise ValueError("invalid_answer_rate")
    return int((Decimal(50) / rate).to_integral_value(rounding=ROUND_CEILING))

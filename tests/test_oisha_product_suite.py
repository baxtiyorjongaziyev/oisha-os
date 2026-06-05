import pytest

from src.services.core.oisha_product_suite import build_oisha_sales_os_suite


def test_suite_contains_three_source_products():
    suite = build_oisha_sales_os_suite()

    source_products = {item["name"] for item in suite["source_products"]}

    assert source_products == {"DeepSales", "Metasell", "Reportagram"}


def test_suite_maps_products_to_operational_layers():
    suite = build_oisha_sales_os_suite()

    layers = {pillar["source_product"]: pillar["oisha_layer"] for pillar in suite["pillars"]}

    assert layers["DeepSales"] == "Lead Intelligence"
    assert layers["Metasell"] == "Conversation Intelligence"
    assert layers["Reportagram"] == "Revenue Reporting"


def test_suite_includes_userbot_call_tags_and_task_rules():
    suite = build_oisha_sales_os_suite()

    tags = {policy["tag"]: policy for policy in suite["call_tag_policy"]}
    task_keys = {rule["key"] for rule in suite["task_decision_rules"]}

    assert tags["mijoz"]["create_sales_task"] is True
    assert tags["shaxsiy"]["create_sales_task"] is False
    assert tags["oila"]["create_sales_task"] is False
    assert "hot_lead" in task_keys
    assert "price_objection" in task_keys
    assert "Telegram userbot" in suite["runtime_integrations"]


def test_suite_contract_has_crm_outputs():
    suite = build_oisha_sales_os_suite()

    outputs = " ".join(suite["amo_crm_outputs"]).lower()

    assert "transcript" in outputs
    assert "task" in outputs
    assert "daily" in outputs


def test_suite_includes_rnp_mission_and_signals():
    suite = build_oisha_sales_os_suite()

    assert suite["rnp_mission"]["name"] == "RNP - Ruka Na Pulse"
    assert "Fake metrics are forbidden" in suite["rnp_mission"]["principles"]

    signal_keys = {signal["key"] for signal in suite["rnp_signals"]}

    assert "new_lead" in signal_keys
    assert "unanswered_customer" in signal_keys
    assert "meeting_agreed" in signal_keys
    assert "source_unhealthy" in signal_keys


@pytest.mark.asyncio
async def test_api_endpoint_returns_suite_contract():
    from src.api_server import oisha_product_suite

    suite = await oisha_product_suite()

    assert suite["name"] == "Oisha Sales OS"
    assert len(suite["pillars"]) == 3
    assert any(
        workflow["key"] == "autonomous_follow_up"
        for workflow in suite["unified_workflows"]
    )
    assert suite["rnp_mission"]["name"] == "RNP - Ruka Na Pulse"

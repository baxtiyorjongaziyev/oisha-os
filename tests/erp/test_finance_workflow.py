import pytest

from src.database import Database
from src.services.erp.action_queue import ActionQueue
from src.services.erp.models import VerificationResult
from src.services.erp.repository import ERPRepository
from src.services.erp.workflows.finance import FinanceStage, FinanceWorkflowService


@pytest.fixture
async def finance(tmp_path):
    db = Database(str(tmp_path / "finance-workflow.db"))
    await db.init_instance()
    repo = ERPRepository(db)
    await repo.initialize()
    service = FinanceWorkflowService(repo, ActionQueue(repo))
    yield service
    await db.close()


async def announce(finance, source_event_id="telegram:-100:88"):
    return await finance.announce_income(
        source_event_id=source_event_id,
        amount=1_500_000,
        currency="UZS",
        client_id="client-777",
        seller_id="seller-12",
        lead_id=2001,
        deal_link="https://example.amocrm.com/leads/detail/2001",
        airtable_project_id="recProject1",
        celebration_chat_id=-100123,
        celebration_text="Sotuvchi, tasdiqlangan kirim bilan tabriklaymiz!",
    )


async def complete_action(finance, action):
    await finance.repo.record_verification(
        action.action_id,
        VerificationResult(
            success=True,
            source=action.target,
            expected=action.expected_result,
            actual=action.expected_result,
            reason="live_readback_confirmed",
        ),
    )
    await finance.repo.mark_action_completed(action.action_id)


@pytest.mark.asyncio
async def test_income_announcement_waits_for_finance_confirmation(finance):
    workflow = await announce(finance)

    assert workflow["data"]["finance_stage"] == FinanceStage.FINANCE_REVIEW.value
    assert await finance.repo.count_rows("erp_actions") == 0


@pytest.mark.asyncio
async def test_finance_confirmation_queues_airtable_before_crm_and_celebration(finance):
    workflow = await announce(finance)

    action = await finance.confirm_income(
        workflow["workflow_id"],
        confirmed_by="finance-user-1",
        confirmer_role="finance",
    )

    assert action.action_type == "airtable.create_income"
    assert action.payload["amount"] == 1_500_000
    assert action.payload["source_event_id"] == "telegram:-100:88"
    stored = await finance.repo.get_workflow(workflow["workflow_id"])
    assert stored["data"]["finance_stage"] == FinanceStage.CONFIRMED.value
    assert await finance.repo.count_rows("erp_actions") == 1


@pytest.mark.asyncio
async def test_finance_rejects_missing_required_payment_data(finance):
    with pytest.raises(ValueError, match="amount_required"):
        await finance.announce_income(
            source_event_id="telegram:-100:89",
            amount=0,
            currency="UZS",
            client_id="client-777",
            seller_id="seller-12",
            lead_id=2001,
            deal_link="https://example.amocrm.com/leads/detail/2001",
            airtable_project_id="recProject1",
            celebration_chat_id=-100123,
            celebration_text="Tabrik",
        )
    with pytest.raises(ValueError, match="deal_link_required"):
        await finance.announce_income(
            source_event_id="telegram:-100:90",
            amount=1_000_000,
            currency="UZS",
            client_id="client-777",
            seller_id="seller-12",
            lead_id=2001,
            deal_link="",
            airtable_project_id="recProject1",
            celebration_chat_id=-100123,
            celebration_text="Tabrik",
        )


@pytest.mark.asyncio
async def test_duplicate_income_announcement_does_not_duplicate_workflow(finance):
    first = await announce(finance)
    second = await announce(finance)

    assert second["workflow_id"] == first["workflow_id"]
    assert await finance.repo.count_rows("erp_workflows") == 1


@pytest.mark.asyncio
async def test_finance_steps_are_sequential_and_verified(finance):
    workflow = await announce(finance)
    airtable_action = await finance.confirm_income(
        workflow["workflow_id"],
        confirmed_by="finance-user-1",
        confirmer_role="finance",
    )
    await complete_action(finance, airtable_action)

    crm_action = await finance.mark_airtable_recorded(
        workflow["workflow_id"],
        airtable_record_id="recIncome1",
    )
    assert crm_action.action_type == "amocrm.add_note"
    stored = await finance.repo.get_workflow(workflow["workflow_id"])
    assert stored["data"]["finance_stage"] == FinanceStage.AIRTABLE_RECORDED.value

    await complete_action(finance, crm_action)
    celebration = await finance.mark_crm_updated(workflow["workflow_id"])
    assert celebration.action_type == "telegram.send_message"
    stored = await finance.repo.get_workflow(workflow["workflow_id"])
    assert stored["data"]["finance_stage"] == FinanceStage.CRM_UPDATED.value

    await complete_action(finance, celebration)
    await finance.mark_sales_congratulated(workflow["workflow_id"])
    stored = await finance.repo.get_workflow(workflow["workflow_id"])
    assert stored["data"]["finance_stage"] == FinanceStage.SALES_CONGRATULATED.value


@pytest.mark.asyncio
async def test_debt_blocks_final_file_handoff(finance):
    with pytest.raises(ValueError, match="outstanding_debt_blocks_file_handoff"):
        finance.assert_final_file_handoff_allowed(
            contract_total=10_000_000,
            confirmed_paid=6_000_000,
        )
    assert finance.assert_final_file_handoff_allowed(
        contract_total=10_000_000,
        confirmed_paid=10_000_000,
    )


@pytest.mark.asyncio
async def test_refund_and_writeoff_require_owner_approval(finance):
    workflow = await announce(finance)

    for operation in ("refund", "write_off"):
        with pytest.raises(ValueError, match="owner_approval_required"):
            await finance.queue_adjustment(
                workflow["workflow_id"],
                operation=operation,
                amount=500_000,
                owner_approved=False,
            )

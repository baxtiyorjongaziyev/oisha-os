from scripts.ci.render_runner_diagnostic import classify_run


def test_queued_run_waits_for_runner():
    assert classify_run(
        {"status": "queued", "conclusion": None},
        [],
    ) == "queued_waiting_for_runner"


def test_no_steps_is_account_or_assignment_failure():
    assert classify_run(
        {"status": "completed", "conclusion": "failure"},
        [{"status": "completed", "conclusion": "failure", "steps": None}],
    ) == "runner_or_account_before_step_one"


def test_failed_named_step_is_workflow_failure():
    assert classify_run(
        {"status": "completed", "conclusion": "failure"},
        [{"steps": [{"name": "Install", "conclusion": "failure"}]}],
    ) == "workflow_step_failure"


def test_success_is_success():
    assert classify_run(
        {"status": "completed", "conclusion": "success"},
        [{"steps": [{"name": "Reach step one", "conclusion": "success"}]}],
    ) == "workflow_success"


def test_cancelled_is_cancelled():
    assert classify_run(
        {"status": "completed", "conclusion": "cancelled"},
        [],
    ) == "cancelled"

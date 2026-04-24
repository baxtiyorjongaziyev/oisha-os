from src.agents import autonomous_sales_agent as module


def test_autonomous_sales_agent_instantiates():
    module._autonomous_agent = None

    agent = module.get_autonomous_agent(db=None)

    assert agent.agent_id == "SurgicalCloser"
    assert agent.db is None

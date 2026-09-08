def test_sales_report_settings_defaults():
    from src.settings import settings
    assert settings.CRM_SALES_REPORT_GROUP_ID == -1003854308552
    assert settings.CRM_SALES_REPORT_TOPIC_ID == 115

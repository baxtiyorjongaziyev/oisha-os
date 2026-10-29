"""
Unit tests for AmoCRMNocoDBSyncer.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.core.crm.amocrm_nocodb_syncer import AmoCRMNocoDBSyncer


class TestAmoCRMNocoDBSyncer(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_amocrm = MagicMock()
        self.mock_amocrm.access_token = "valid_token"
        self.syncer = AmoCRMNocoDBSyncer(amocrm=self.mock_amocrm)

    def test_extract_lead_contact_info(self):
        lead = {
            "_embedded": {"contacts": [{"name": "Akmal aka"}]},
            "custom_fields_values": [
                {
                    "field_code": "PHONE",
                    "values": [{"value": "+998901234567"}],
                }
            ],
        }
        name, phone = self.syncer._extract_lead_contact_info(lead)
        self.assertEqual(name, "Akmal aka")
        self.assertEqual(phone, "+998901234567")

    def test_map_lead_to_row(self):
        lead = {
            "id": 12345,
            "name": "Test Brandbook",
            "price": 25000000,
            "status_id": 142,
            "pipeline_id": 100,
            "responsible_user_id": 55,
            "created_at": 1700000000,
            "updated_at": 1700050000,
            "closed_at": 1700050000,
            "_embedded": {"contacts": [{"name": "Sardor"}]},
            "custom_fields_values": [],
        }
        row = self.syncer._map_lead_to_row(lead)
        self.assertEqual(row[0], 12345)
        self.assertEqual(row[1], "Test Brandbook")
        self.assertEqual(row[2], 25000000)
        self.assertEqual(row[3], 142)
        self.assertEqual(row[4], "CLOSED_WON")
        self.assertEqual(row[10], "Sardor")

    @patch.object(AmoCRMNocoDBSyncer, "get_pg_connection")
    async def test_sync_closed_leads(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        self.mock_amocrm.get_leads = AsyncMock(
            side_effect=[
                [{"id": 1, "name": "Won Lead", "status_id": 142}],  # status 142 page 1 (len < 250 -> breaks to next status)
                [{"id": 2, "name": "Lost Lead", "status_id": 143}],  # status 143 page 1 (len < 250 -> breaks)
            ]
        )

        total = await self.syncer.sync_closed_leads(statuses=[142, 143], max_pages=2)
        self.assertEqual(total, 2)
        self.assertEqual(mock_cur.executemany.call_count, 2)



if __name__ == "__main__":
    unittest.main()

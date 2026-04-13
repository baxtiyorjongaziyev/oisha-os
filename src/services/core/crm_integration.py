import requests
import logging

logger = logging.getLogger(__name__)

class CRMIntegration:
    """AmoCRM va Airtable bilan integratsiya moduli."""

    # --- AmoCRM (Simplified v4 API) ---
    @staticmethod
    def create_amocrm_lead(name, phone, price=0, api_token=None, domain=None):
        """AmoCRM da yangi Lead yaratish."""
        if not api_token or not domain:
            return None
            
        url = f"https://{domain}.amocrm.ru/api/v4/leads/complex"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        data = [
            {
                "name": f"Lead: {name}",
                "price": price,
                "_embedded": {
                    "contacts": [
                        {
                            "first_name": name,
                            "custom_fields_values": [
                                {
                                    "field_code": "PHONE",
                                    "values": [{"value": phone}]
                                }
                            ]
                        }
                    ]
                }
            }
        ]
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"[AMOCRM ERROR] {e}")
            return None

    @staticmethod
    def get_amocrm_tasks(api_token=None, domain=None):
        """AmoCRM dan vazifalarni olish."""
        if not api_token or not domain:
            return []
            
        url = f"https://{domain}.amocrm.ru/api/v4/tasks"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get("_embedded", {}).get("tasks", [])
            return []
        except Exception as e:
            logger.error(f"[AMOCRM TASKS ERROR] {e}")
            return []

    # --- Airtable Integration ---
    @staticmethod
    def save_to_airtable(base_id, table_name, fields, api_token=None):
        """Airtable bazasiga yangi qator (record) qo'shish."""
        if not api_token:
            return False
            
        url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        data = {
            "records": [
                {
                    "fields": fields
                }
            ]
        }
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"[AIRTABLE ERROR] {e}")
            return False

    @staticmethod
    def get_airtable_records(base_id, table_name, api_token=None, max_records=5):
        """Airtable dan oxirgi yozuvlarni olish."""
        if not api_token:
            return []
            
        url = f"https://api.airtable.com/v0/{base_id}/{table_name}?maxRecords={max_records}&sortField=Created&sortDirection=desc"
        headers = {
            "Authorization": f"Bearer {api_token}"
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json().get('records', [])
            return []
        except Exception as e:
            logger.error(f"[AIRTABLE FETCH ERROR] {e}")
            return []

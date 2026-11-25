"""AmoCRM Customers (Pokupateli) API v4 mixin."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests  # type: ignore

from src.services.core.crm.amocrm.auth import retry_with_backoff

logger = logging.getLogger(__name__)


class AmoCRMCustomersMixin:
    """AmoCRM `/api/v4/customers` bilan ishlash uchun mixin."""

    @retry_with_backoff(max_retries=3, initial_delay=1)
    def get_customers(
        self,
        query: Optional[str] = None,
        page: int = 1,
        limit: int = 250,
        with_params: str = "contacts",
    ) -> List[Dict[str, Any]]:
        """AmoCRM dan xaridorlar (pokupateli) roʻyxatini olish."""
        self._load_token()
        url = f"{self.base_url}/api/v4/customers"
        params: Dict[str, Any] = {"page": page, "limit": limit}
        if query:
            params["query"] = query
        if with_params:
            params["with"] = with_params

        try:
            response = requests.get(
                url, headers=self._get_headers(), params=params, timeout=30
            )
            if response.status_code == 200:
                return response.json().get("_embedded", {}).get("customers", [])
            if response.status_code == 204:
                return []
            logger.warning(
                f"[AMOCRM CUSTOMERS GET] status={response.status_code} body={response.text[:200]}"
            )
            return []
        except Exception as exc:
            logger.error(f"[AMOCRM CUSTOMERS GET ERROR] {exc}")
            return []

    def find_customer(
        self,
        name: Optional[str] = None,
        contact_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Xaridorni contact_id yoki ism boʻyicha topish."""
        if contact_id:
            customers = self.get_customers(with_params="contacts")
            for customer in customers:
                contacts = customer.get("_embedded", {}).get("contacts", [])
                if any(c.get("id") == contact_id for c in contacts):
                    return customer

        if name:
            clean_name = name.strip().lower()
            matches = self.get_customers(query=name.strip(), with_params="contacts")
            for customer in matches:
                if (customer.get("name") or "").strip().lower() == clean_name:
                    return customer
            if matches:
                return matches[0]
        return None

    @retry_with_backoff(max_retries=3, initial_delay=1)
    def create_customer(
        self,
        name: str,
        contact_id: Optional[int] = None,
        responsible_user_id: Optional[int] = None,
        next_price: Optional[int] = None,
        next_date: Optional[int] = None,
        custom_fields_values: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[int]:
        """Yangi xaridor (pokupatel) yaratish."""
        self._load_token()
        url = f"{self.base_url}/api/v4/customers"
        payload: Dict[str, Any] = {"name": name}
        if responsible_user_id:
            payload["responsible_user_id"] = responsible_user_id
        if next_price is not None:
            payload["next_price"] = int(next_price)
        if next_date is not None:
            payload["next_date"] = int(next_date)
        if custom_fields_values:
            payload["custom_fields_values"] = custom_fields_values

        embedded: Dict[str, Any] = {}
        if contact_id:
            embedded["contacts"] = [{"id": int(contact_id)}]
        if tags:
            embedded["tags"] = [{"name": t} for t in tags if t]
        if embedded:
            payload["_embedded"] = embedded

        try:
            response = requests.post(
                url, headers=self._get_headers(), json=[payload], timeout=30
            )
            if response.status_code in (200, 201):
                created = response.json().get("_embedded", {}).get("customers", [])
                if created:
                    return created[0].get("id")
            logger.error(
                f"[AMOCRM CUSTOMER CREATE] status={response.status_code} body={response.text[:300]}"
            )
            return None
        except Exception as exc:
            logger.error(f"[AMOCRM CUSTOMER CREATE ERROR] {exc}")
            return None

    @retry_with_backoff(max_retries=3, initial_delay=1)
    def update_customer(
        self,
        customer_id: int,
        name: Optional[str] = None,
        next_price: Optional[int] = None,
        next_date: Optional[int] = None,
        custom_fields_values: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """Mavjud xaridorni yangilash."""
        self._load_token()
        url = f"{self.base_url}/api/v4/customers"
        payload: Dict[str, Any] = {"id": int(customer_id)}
        if name:
            payload["name"] = name
        if next_price is not None:
            payload["next_price"] = int(next_price)
        if next_date is not None:
            payload["next_date"] = int(next_date)
        if custom_fields_values:
            payload["custom_fields_values"] = custom_fields_values
        if tags:
            payload["_embedded"] = {"tags": [{"name": t} for t in tags if t]}

        try:
            response = requests.patch(
                url, headers=self._get_headers(), json=[payload], timeout=30
            )
            if response.status_code in (200, 201):
                return True
            logger.error(
                f"[AMOCRM CUSTOMER UPDATE] status={response.status_code} body={response.text[:300]}"
            )
            return False
        except Exception as exc:
            logger.error(f"[AMOCRM CUSTOMER UPDATE ERROR] {exc}")
            return False

    @retry_with_backoff(max_retries=3, initial_delay=1)
    def link_contact_to_customer(self, customer_id: int, contact_id: int) -> bool:
        """Kontaktni xaridorga bogʻlash."""
        self._load_token()
        url = f"{self.base_url}/api/v4/customers/{int(customer_id)}/link"
        payload = [{"to_entity_id": int(contact_id), "to_entity_type": "contacts"}]
        try:
            response = requests.post(
                url, headers=self._get_headers(), json=payload, timeout=30
            )
            return response.status_code in (200, 201)
        except Exception as exc:
            logger.error(f"[AMOCRM CUSTOMER LINK ERROR] {exc}")
            return False

    @retry_with_backoff(max_retries=3, initial_delay=1)
    def add_customer_note(self, customer_id: int, text: str) -> bool:
        """Xaridorga matnli izoh (note) qoʻshish."""
        self._load_token()
        url = f"{self.base_url}/api/v4/customers/{int(customer_id)}/notes"
        payload = [{"note_type": "common", "params": {"text": text}}]
        try:
            response = requests.post(
                url, headers=self._get_headers(), json=payload, timeout=30
            )
            return response.status_code in (200, 201)
        except Exception as exc:
            logger.error(f"[AMOCRM CUSTOMER NOTE ERROR] {exc}")
            return False

    @retry_with_backoff(max_retries=3, initial_delay=1)
    def add_customer_transaction(
        self,
        customer_id: int,
        price: int,
        comment: str = "",
        completed_at: Optional[int] = None,
    ) -> Optional[int]:
        """Xaridorga tranzaksiya (toʻlov) qoʻshish."""
        self._load_token()
        url = f"{self.base_url}/api/v4/customers/{int(customer_id)}/transactions"
        payload: Dict[str, Any] = {"price": int(price)}
        if comment:
            payload["comment"] = comment
        if completed_at is not None:
            payload["completed_at"] = int(completed_at)
        try:
            response = requests.post(
                url, headers=self._get_headers(), json=[payload], timeout=30
            )
            if response.status_code in (200, 201):
                txs = response.json().get("_embedded", {}).get("transactions", [])
                if txs:
                    return txs[0].get("id")
            return None
        except Exception as exc:
            logger.error(f"[AMOCRM CUSTOMER TX ERROR] {exc}")
            return None

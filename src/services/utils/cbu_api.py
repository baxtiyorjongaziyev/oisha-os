import requests
import logging

logger = logging.getLogger(__name__)


class CBUApi:
    """Markaziy Bank valyuta kurslari bilan ishlash uchun bepul API yordamchisi."""

    BASE_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"

    @staticmethod
    def get_rates():
        """Barcha valyuta kurslarini olish."""
        try:
            response = requests.get(CBUApi.BASE_URL, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"[CBU API ERROR] Kurslarni olishda xatolik: {e}")
            return None

    @staticmethod
    def get_usd_rate():
        """USD kursini olish."""
        rates = CBUApi.get_rates()
        if rates:
            for rate in rates:
                if rate.get("Ccy") == "USD":
                    return {
                        "rate": rate.get("Rate"),
                        "diff": rate.get("Diff"),
                        "date": rate.get("Date"),
                    }
        return None

    @staticmethod
    def convert_to_uzs(amount, currency="USD"):
        """Miqdorni so'mga konvertatsiya qilish."""
        rates = CBUApi.get_rates()
        if rates:
            for rate in rates:
                if rate.get("Ccy") == currency:
                    try:
                        rate_val = float(rate.get("Rate"))
                        return amount * rate_val
                    except Exception:
                        return None
        return None

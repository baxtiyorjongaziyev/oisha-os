import requests
import logging

logger = logging.getLogger(__name__)


class WeatherApi:
    """Open-Meteo orqali bepul ob-havo ma'lumotlarini olish (API key shart emas)."""

    # Toshkent koordinatalari: 41.2995, 69.2401
    BASE_URL = "https://api.open-meteo.com/v1/forecast?latitude=41.30&longitude=69.24&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&timezone=Asia%2FTashkent"

    @staticmethod
    def get_current_weather():
        """Toshkentdagi joriy ob-havoni olish."""
        try:
            response = requests.get(WeatherApi.BASE_URL, timeout=10)
            if response.status_code == 200:
                data = response.json()
                current = data.get("current", {})

                # Weather code tahlili (Soddalashtirilgan)
                w_code = current.get("weather_code", 0)
                condition = "Ochiq havo"
                if w_code > 0:
                    if w_code < 3:
                        condition = "Qisman bulutli"
                    elif w_code < 50:
                        condition = "Tumanli"
                    elif w_code < 60:
                        condition = "Yomg'ir shivalayapti"
                    elif w_code < 70:
                        condition = "Yomg'ir"
                    elif w_code < 80:
                        condition = "Qor yo'g'yapti"
                    else:
                        condition = "Momaqaldiroq"

                return {
                    "temp": current.get("temperature_2m"),
                    "feels_like": current.get("apparent_temperature"),
                    "humidity": current.get("relative_humidity_2m"),
                    "condition": condition,
                    "wind": current.get("wind_speed_10m"),
                }
            return None
        except Exception as e:
            logger.error(f"[WEATHER API ERROR] Ob-havoni olishda xatolik: {e}")
            return None

    @staticmethod
    def get_weather_summary():
        """Bot uchun qisqa matnli xulosa tayyorlash."""
        w = WeatherApi.get_current_weather()
        if w:
            return f"Toshkentda hozir {w['temp']}°C, {w['condition']}. Namlik: {w['humidity']}%, Shamol: {w['wind']} km/soat."
        return "Ob-havo ma'lumotlarini olib bo'lmadi."

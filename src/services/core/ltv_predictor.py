import structlog
import os
import json
import pickle
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from src.settings import settings

logger = structlog.get_logger()


@dataclass
class LeadFeatures:
    """ML model uchun kirish ma'lumotlari."""
    company_size: float = 0.0
    price: float = 0.0
    contact_count: float = 0.0
    task_count: float = 0.0
    call_duration_avg: float = 0.0
    message_count: float = 0.0
    days_in_pipeline: float = 0.0
    tag_count: float = 0.0
    is_repeat_client: float = 0.0
    industry_encoded: float = 0.0


class LTVPredictor:
    """🔮 Predictive LTV — ML orqali mijozning kelajakdagi qiymatini bashorat qilish.

    Ishlash tartibi:
    1. AmoCRM dan tarixiy lead ma'lumotlari olinadi
    2. Feature engineering: lead dan raqamli xususiyatlar chiqariladi
    3. Scikit-Learn RandomForest modeli train qilinadi
    4. Yangi lead kelganda LTV bashorat qilinadi
    5. Agar LTV yuqori bo'lsa → VIP menejer ulanishi
    """

    def __init__(self):
        self.model_path = settings.LTV_MODEL_PATH
        self.enabled = settings.ENABLE_LTV_PREDICTION
        self.model = None
        self._load_model()

    def _load_model(self):
        """Diskdan modelni yuklash."""
        if os.path.exists(self.model_path):
            try:
                with open(self.model_path, "rb") as f:
                    self.model = pickle.load(f)
                logger.info("[LTV] Model loaded", path=self.model_path)
            except Exception as e:
                logger.warning("[LTV] Failed to load model", error=str(e))
                self.model = None

    def _save_model(self):
        """Modelni diskka saqlash."""
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        with open(self.model_path, "wb") as f:
            pickle.dump(self.model, f)
        logger.info("[LTV] Model saved", path=self.model_path)

    def extract_features(self, lead: Dict[str, Any]) -> LeadFeatures:
        """Lead dict dan ML feature larini chiqarish."""
        features = LeadFeatures()

        features.price = float(lead.get("price", 0) or 0)
        features.days_in_pipeline = float(lead.get("days_in_pipeline", 0) or 0)

        # Custom fields dan ma'lumot olish
        for cf in lead.get("custom_fields_values") or []:
            code = cf.get("field_code", "")
            values = cf.get("values", [{}])
            val = values[0].get("value", 0) if values else 0

            if code == "COMPANY_SIZE":
                features.company_size = float(val) if val else 0.0
            elif code == "IS_REPEAT":
                features.is_repeat_client = 1.0 if str(val).lower() in ("yes", "ha", "true") else 0.0
            elif code == "INDUSTRY":
                features.industry_encoded = self._encode_industry(str(val))

        # _embedded dan kontakt va vazifalar soni
        embedded = lead.get("_embedded", {})
        features.contact_count = float(len(embedded.get("contacts", [])))
        features.task_count = float(len(embedded.get("tasks", [])))

        # Tag count
        tags = embedded.get("tags", [])
        features.tag_count = float(len(tags))

        # Message count (agar ajratilgan bo'lsa)
        features.message_count = float(lead.get("message_count", 0))
        features.call_duration_avg = float(lead.get("call_duration_avg", 0))

        return features

    async def predict_ltv(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Yangi lead uchun LTV bashorat qilish.

        Returns:
            {
                "ltv": 15000000,       # Bashorat qilingan LTV (so'm)
                "tier": "vip|standard|low",
                "confidence": 0.85,    # Ishonchlilik darajasi
                "should_alert_vip": True  # VIP menejer kerakmi?
            }
        """
        if not self.enabled or self.model is None:
            return self._rule_based_estimate(lead)

        try:
            features = self.extract_features(lead)
            X = [[
                features.company_size, features.price, features.contact_count,
                features.task_count, features.call_duration_avg, features.message_count,
                features.days_in_pipeline, features.tag_count, features.is_repeat_client,
                features.industry_encoded,
            ]]

            pred = self.model.predict(X)[0]
            proba = self.model.predict_proba(X).max() if hasattr(self.model, "predict_proba") else 0.5

            ltv = max(0, float(pred))
            tier = self._get_tier(ltv)
            return {
                "ltv": ltv,
                "tier": tier,
                "confidence": round(float(proba), 2),
                "should_alert_vip": tier == "vip",
            }
        except Exception as e:
            logger.warning("[LTV] ML prediction failed, using rule-based", error=str(e))
            return self._rule_based_estimate(lead)

    def _rule_based_estimate(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """ML model bo'lmaganda, qoidalar asosida LTV bashorati."""
        price = float(lead.get("price", 0) or 0)
        is_repeat = False
        for cf in lead.get("custom_fields_values") or []:
            if cf.get("field_code") == "IS_REPEAT":
                vals = cf.get("values", [{}])
                if vals and str(vals[0].get("value", "")).lower() in ("yes", "ha", "true"):
                    is_repeat = True

        # Qoidalar:
        # - Takroriy mijoz: price * 3
        # - Birinchi mijoz: price * 1.5
        # - Kichik (0-5M): price * 1.2
        if is_repeat:
            ltv = price * 3.0
        elif price > 10_000_000:
            ltv = price * 2.0
        elif price > 5_000_000:
            ltv = price * 1.5
        else:
            ltv = price * 1.2

        tier = self._get_tier(ltv)
        return {
            "ltv": ltv,
            "tier": tier,
            "confidence": 0.5,
            "should_alert_vip": tier == "vip",
        }

    async def train_model(self, leads: List[Dict[str, Any]]) -> bool:
        """Tarixiy lead ma'lumotlari bo'yicha modelni train qilish."""
        try:
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.model_selection import train_test_split

            X, y = [], []
            for lead in leads:
                features = self.extract_features(lead)
                total_revenue = float(lead.get("total_revenue", lead.get("price", 0)))
                if total_revenue <= 0:
                    continue
                X.append([
                    features.company_size, features.price, features.contact_count,
                    features.task_count, features.call_duration_avg, features.message_count,
                    features.days_in_pipeline, features.tag_count, features.is_repeat_client,
                    features.industry_encoded,
                ])
                y.append(total_revenue)

            if len(X) < 50:
                logger.warning("[LTV] Not enough data for training", samples=len(X))
                return False

            model = RandomForestRegressor(
                n_estimators=100, max_depth=10, random_state=42, n_jobs=-1
            )
            model.fit(X, y)
            self.model = model
            self._save_model()
            logger.info("[LTV] Model trained successfully", samples=len(X))
            return True
        except ImportError as e:
            logger.warning("[LTV] Scikit-learn not installed, skipping training", error=str(e))
            return False
        except Exception as e:
            logger.error("[LTV] Training failed", error=str(e))
            return False

    def _get_tier(self, ltv: float) -> str:
        """LTV bo'yicha tier aniqlash."""
        if ltv >= 20_000_000:
            return "vip"
        elif ltv >= 5_000_000:
            return "standard"
        return "low"

    def _encode_industry(self, industry: str) -> float:
        """Soha nomini raqamga aylantirish."""
        mapping = {
            "meditsina": 1.0, "ta'lim": 2.0, "retail": 3.0,
            "food": 4.0, "service": 5.0, "qurilish": 6.0,
            "transport": 7.0, "it": 8.0, "other": 9.0,
        }
        return mapping.get(industry.lower(), 9.0)

    async def get_vip_alert_message(self, lead: Dict[str, Any], ltv_result: Dict[str, Any]) -> str:
        """VIP mijoz uchun ogohlantirish xabari."""
        name = lead.get("name", "Noma'lum")
        price = lead.get("price", 0)
        ltv = ltv_result.get("ltv", 0)
        tier = ltv_result.get("tier", "low")
        link = f"https://{settings.AMOCRM_SUBDOMAIN}.amocrm.ru/leads/detail/{lead.get('id')}"

        return (
            f"🚨 <b>VIP MIJOZ ANIQLANDI!</b>\n\n"
            f"👤 <b>{name}</b>\n"
            f"💰 Bitim summasi: {price:,.0f} so'm\n"
            f"🔮 Bashorat qilingan LTV: <b>{ltv:,.0f} so'm</b> ({tier.upper()})\n"
            f"📊 Ishonchlilik: {ltv_result.get('confidence', 0)*100:.0f}%\n\n"
            f"🔗 <a href='{link}'>AmoCRM da ochish</a>\n\n"
            f"👑 Iltimos, VIP menejer mijoz bilan bog'lansin!"
        )
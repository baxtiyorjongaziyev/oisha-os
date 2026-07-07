import asyncio
import structlog
from src.settings import settings
from src.services.core.ltv_predictor import LTVPredictor

logger = structlog.get_logger()


class LTVTrainer:
    """🔮 Predictive LTV — avtomatik model train va deploy.

    Workflow:
    1. Har 24 soatda: AmoCRM dan tarixiy leadlarni yuklash
    2. Feature extraction
    3. Model train (RandomForest)
    4. Modelni diskka saqlash
    5. Yangi leadlar uchun prediction
    """

    def __init__(self, crm=None):
        self.crm = crm
        self.predictor = LTVPredictor()
        self.enabled = settings.ENABLE_LTV_PREDICTION

    async def auto_train(self) -> bool:
        """AmoCRM dan ma'lumotlarni yuklab, modelni train qilish."""
        if not self.enabled or not self.crm:
            logger.warning("[LTV] Training skipped: not enabled or no CRM")
            return False

        try:
            leads = await self.crm.amocrm.get_leads_detailed(limit=500)
            if not leads:
                logger.warning("[LTV] No leads fetched for training")
                return False

            success = await self.predictor.train_model(leads)
            if success:
                logger.info("[LTV] Auto-training completed", leads=len(leads))
            return success
        except Exception as e:
            logger.error("[LTV] Auto-training failed", error=str(e))
            return False

    async def process_new_lead(self, lead: dict) -> dict:
        """Yangi lead kelganda LTV bashorat qilish va VIP alert."""
        if not self.enabled:
            return {"enabled": False}

        result = await self.predictor.predict_ltv(lead)
        logger.info("[LTV] Lead processed", name=lead.get("name"), ltv=result.get("ltv"), tier=result.get("tier"))
        return result

    async def get_team_alert_message(self, lead: dict, ltv_result: dict) -> str:
        """Team uchun VIP xabar."""
        if not ltv_result.get("should_alert_vip"):
            return ""
        return await self.predictor.get_vip_alert_message(lead, ltv_result)
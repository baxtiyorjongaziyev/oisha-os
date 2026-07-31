"""AmoCRM Customers (Покупатели) Manager Service."""
import structlog
from typing import Dict, Any, Optional

from src.settings import settings
from src.services.core.crm.amocrm_sync import AmoCRMSync

logger = structlog.get_logger()

class AmoCRMCustomersManager:
    """Manages AmoCRM Customers (Покупатели) events and integrations.
    
    Responsibilities:
    - Fetches customer data from AmoCRM when webhook is triggered.
    - Calculates Predictive LTV using LTVPredictor.
    - Sends VIP alerts or dynamic segmentation notes to Telegram.
    """

    def __init__(self, amocrm: AmoCRMSync, db):
        self.amocrm = amocrm
        self.db = db

    async def process_customer(self, customer_id: int):
        """Called when a customer is added or updated."""
        logger.info("[CUSTOMERS] Processing customer event", customer_id=customer_id)
        
        customer_data = await self.amocrm.get_customer(customer_id)
        if not customer_data:
            logger.warning("[CUSTOMERS] Could not fetch customer data", customer_id=customer_id)
            return

        name = customer_data.get("name", "Noma'lum")
        
        # Oisha LTV Predictor integratsiyasi
        await self._run_ltv_prediction(customer_id, customer_data)
        
        # Qo'shimcha reaktivatsiya va NPS logikasi kelajakda shu yerda bo'ladi
        # masalan: await self._schedule_nps_survey(customer_id, customer_data)

    async def _run_ltv_prediction(self, customer_id: int, customer_data: Dict[str, Any]):
        """Runs LTV prediction on the customer based on their linked leads."""
        if not getattr(settings, "ENABLE_LTV_PREDICTION", False):
            return

        try:
            from src.services.core.ltv_predictor import LTVPredictor
            
            predictor = LTVPredictor()
            
            # Predict LTV based on customer data (or linked lead data if necessary)
            ltv_result = await predictor.predict_ltv(customer_data)
            
            if ltv_result.get("should_alert_vip"):
                alert_msg = await predictor.get_vip_alert_message(customer_data, ltv_result)
                alert_msg = alert_msg.replace("AmoCRM da ochish", "AmoCRM (Покупатели) da ochish")
                
                # Send to Telegram team group (Farmer)
                team_group_id = getattr(settings, "TELEGRAM_TEAM_GROUP_ID", None)
                if team_group_id:
                    # Depending on how oisha-os sends telegram message. Using business command center or direct.
                    from src.services.core.telegram.telegram_bot import get_bot
                    bot = get_bot()
                    if bot:
                        await bot.send_message(
                            chat_id=team_group_id,
                            text=f"👨‍🌾 <b>Farmer Alert:</b>\n\n{alert_msg}",
                            parse_mode="HTML"
                        )
                        logger.info("[CUSTOMERS] VIP alert sent to team group", customer_id=customer_id)
        except Exception as e:
            logger.error("[CUSTOMERS] Failed to run LTV prediction", customer_id=customer_id, error=str(e), exc_info=True)

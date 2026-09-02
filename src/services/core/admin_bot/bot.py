import structlog
from src.database import Database
from src.controllers.message_controller import MessageController
from src.services.core.crm.crm_night_shift import CRMNightShift
from src.services.core.telegram.bot_runtime import BotRuntimePort, TelethonBotRuntime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.utils.access_manager import AccessManager

logger = structlog.get_logger()

from src.services.core.admin_bot.reports import AdminReportsMixin
from src.services.core.admin_bot.alerts import AdminAlertsMixin
from src.services.core.admin_bot.cron_runner import AdminCronRunnerMixin
from src.services.core.admin_bot.mission_scheduler import AdminMissionSchedulerMixin
from src.services.core.admin_bot.lookup import AdminLookupMixin
from src.services.core.admin_bot.handlers import AdminHandlersMixin

class AdminBot(
    AdminHandlersMixin,
    AdminCronRunnerMixin,
    AdminMissionSchedulerMixin,
    AdminReportsMixin,
    AdminAlertsMixin,
    AdminLookupMixin,
):
    """
    Oisha Enterprise AdminBot.
    Telegram orqali boshqaruv, schedulerlar va monitoring markazi.
    """
    def __init__(
        self,
        bot_client,
        user_client,
        db: Database,
        msg_controller: MessageController,
        access_manager: "AccessManager",
        night_shift: CRMNightShift = None,
        team_group_id: int = None,
        juma_notifier=None,
        bot_runtime: BotRuntimePort = None,
    ):
        self.bot_client = bot_client
        self.bot_runtime = bot_runtime or TelethonBotRuntime(bot_client)
        self.user_client = user_client
        self.db = db
        self.msg_controller = msg_controller
        self.access_manager = access_manager
        self.night_shift = night_shift
        self.team_group_id = team_group_id
        self.juma_notifier = juma_notifier
        self.active_searches = {}
        self.pending_drafts = {}
        from src.services.core.self_improvement import SelfImprovementService

        self.self_improvement = SelfImprovementService(
            db,
            bot_client=self.bot_runtime,
            owner_id=access_manager.owner_id,
        )

        self.PHONE_GETTING_SCRIPTS = {
            "agency_standard": (
                "📍 **Agency Standard:**\n"
                '"Tafsilotlar uchun rahmat! Loyihani texnik tomondan baholashimiz uchun '
                "siz bilan telefon orqali bog'lansak bo'ladimi? Raqamingizni qoldirsangiz, "
                'mutaxassisimiz bilan vaqtni kelishib olamiz."'
            ),
            "value_first": (
                "🎁 **Value-First (Kasbiy):**\n"
                "\"Sizning sohangiz bo'yicha bizda tayyor keyslar va narxlar paketi bor. "
                "Ularni Telegram orqali yuborishim uchun kontaktlaringizni yangilab yuborsangiz (ulashsangiz), "
                "sizga mos yechimni jo'nataman.\""
            ),
            "emergency_pm": (
                "⚡ **Dynamic (PM uslubi):**\n"
                "\"Loyiha bo'yicha tezkor savollar bor edi. Yozishib o'tirmasdan, "
                "qisqa qo'ng'iroqda hal qilsak tezroq bitar edi. Qaysi raqamga bog'lansak bo'ladi?\""
            ),
        }

    def _outbound_bot_runtime(self) -> BotRuntimePort:
        runtime = getattr(self, "bot_runtime", None)
        if runtime is not None:
            return runtime
        runtime = TelethonBotRuntime(self.bot_client)
        self.bot_runtime = runtime
        return runtime

    async def start(self):
        """Botni ishga tushirish va handlerlarni ro'yxatdan o'tkazish."""
        await self.register_admin_handlers()

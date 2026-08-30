"""
ERP command registry and help texts.
"""
from src.services.core.finance.erp.reports import (
    cmd_erp_holat,
    cmd_erp_salomatlik,
    cmd_jamoa,
    cmd_loyihalar,
    cmd_moliya,
)
from src.services.core.finance.erp.mutations import (
    cmd_qo_shish_loyiha,
    cmd_xarajat_qosh,
)

COMMAND_REGISTRY: dict[str, object] = {
    "/erp_holat":      cmd_erp_holat,
    "/moliya":         cmd_moliya,
    "/jamoa":          cmd_jamoa,
    "/loyihalar":      cmd_loyihalar,
    "/erp_salomatlik": cmd_erp_salomatlik,
    "/loyiha_qosh":    cmd_qo_shish_loyiha,
    "/xarajat":        cmd_xarajat_qosh,
}

ERP_HELP_TEXT = """
🏢 *OISHA ERP — BUYRUQLAR RO'YXATI*

📊 *Holat va hisobotlar:*
  /erp_holat           — Umumiy ERP holati (moliya + jamoa + loyihalar)
  /erp_salomatlik      — ERP sog'liqlik balli (0–100) va tavsiyalar

💰 *Moliya:*
  /moliya              — Joriy oy moliyaviy hisoboti
  /moliya 2025-06      — Muayyan oy uchun moliyaviy hisobot
  /xarajat [kategoriya] | [tavsif] | [miqdor]
                       — Yangi xarajat qo'shish

👥 *Jamoa:*
  /jamoa               — Joriy oy jamoa va KPI hisoboti
  /jamoa 2025-06       — Muayyan oy uchun jamoa hisoboti

📁 *Loyihalar:*
  /loyihalar           — Barcha faol loyihalar ro'yxati
  /loyiha_qosh [sarlavha] | [mijoz] | [byudjet] | [muddat]
                       — Yangi loyiha yaratish

ℹ️ *Misollar:*
  /xarajat ofis | Printer qog'oz | 150000
  /loyiha_qosh Brend identifikatsiya | Tex Corp | 5000000 | 2025-08-01
  /moliya 2025-05
""".strip()

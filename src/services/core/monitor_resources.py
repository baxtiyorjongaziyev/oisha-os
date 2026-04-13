import psutil
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class ResourceMonitor:
    def __init__(self, db, threshold_ram=85):
        self.db = db
        self.threshold_ram = threshold_ram

    async def get_stats(self):
        ram = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=1)
        disk = psutil.disk_usage('/')
        
        return {
            "ram_percent": ram.percent,
            "ram_available_mb": ram.available / (1024 * 1024),
            "cpu_percent": cpu,
            "disk_percent": disk.percent,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    async def run_forever(self, interval=3600):
        """Runs the monitoring loop."""
        logger.info(f"📊 ResourceMonitor started (Threshold: {self.threshold_ram}%)")
        while True:
            try:
                stats = await self.get_stats()
                logger.info(f"📈 [RESOURCE CHECK] RAM: {stats['ram_percent']}% | CPU: {stats['cpu_percent']}%")
                
                # Check for critical usage
                if stats['ram_percent'] > self.threshold_ram:
                    logger.warning(f"⚠️ [CRITICAL RAM] Oisha is choking! Usage: {stats['ram_percent']}%")
                    # Here we could send a Telegram alert if needed
                
                # Log to DB locally for history
                # self.db.log_event("resource_stats", stats) 
                
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"[RESOURCE MONITOR ERROR] {e}")
                await asyncio.sleep(60)

async def check_resources_now():
    monitor = ResourceMonitor(None)
    stats = await monitor.get_stats()
    return (
        f"📊 **SERVER TAHLILI (e2-micro)**\n\n"
        f"🧠 **RAM**: {stats['ram_percent']}% ({int(stats['ram_available_mb'])}MB bo'sh)\n"
        f"⚡ **CPU**: {stats['cpu_percent']}%\n"
        f"💾 **Disk**: {stats['disk_percent']}%\n"
        f"🕒 **Vaqt**: {stats['timestamp']}\n\n"
        f"💡 _Eslatma: RAM 85% dan oshsa, e2-small ga o'tish tavsiya etiladi._"
    )

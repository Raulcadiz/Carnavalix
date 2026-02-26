"""
Tareas programadas con APScheduler.
- Scraping de YouTube cada N horas
- Sincronización con Odysee diaria
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from backend.config import config

_scheduler: BackgroundScheduler | None = None


def start_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone="Europe/Madrid")

    # Scraping YouTube — cada N horas (por defecto 24h a las 3:00)
    _scheduler.add_job(
        _job_scraper_youtube,
        trigger=CronTrigger(hour=3, minute=0),
        id="scraper_youtube",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Sincronización Odysee — diaria a las 4:00
    _scheduler.add_job(
        _job_odysee_sync,
        trigger=CronTrigger(hour=4, minute=0),
        id="odysee_sync",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    _scheduler.start()
    print("[Scheduler] Tareas programadas iniciadas.")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        print("[Scheduler] Detenido.")


def _job_scraper_youtube():
    print("[Scheduler] Iniciando scraping YouTube...")
    try:
        from backend.services.youtube_scraper import scrapear_coac
        scrapear_coac()
    except Exception as e:
        print(f"[Scheduler] Error scraper: {e}")


def _job_odysee_sync():
    print("[Scheduler] Iniciando sincronización Odysee...")
    try:
        from backend.services.odysee_uploader import sincronizar_pendientes
        sincronizar_pendientes(limite=10)
    except Exception as e:
        print(f"[Scheduler] Error Odysee: {e}")

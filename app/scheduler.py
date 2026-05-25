import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .database import SessionLocal
from .models import SearchConfig

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Tokyo")


def _run_config(config_id: int):
    from .scraper_manager import run_scrape
    logger.info(f"スケジューラー実行: config_id={config_id}")
    run_scrape(config_id)


def refresh_jobs():
    """DBの検索設定を読み込んでスケジューラーのジョブを再設定する"""
    db = SessionLocal()
    try:
        configs = db.query(SearchConfig).filter(SearchConfig.is_active == True).all()

        # 既存ジョブをクリア
        for job in scheduler.get_jobs():
            job.remove()

        for config in configs:
            hours = max(1, config.interval_hours)
            scheduler.add_job(
                _run_config,
                trigger=IntervalTrigger(hours=hours),
                args=[config.id],
                id=f"scrape_{config.id}",
                replace_existing=True,
                next_run_time=_calc_next_run(config, hours),
            )
            logger.info(f"ジョブ登録: {config.name} (毎{hours}時間)")
    finally:
        db.close()


def _calc_next_run(config: SearchConfig, interval_hours: int) -> datetime:
    """前回実行時刻 + interval_hours を次回実行時刻にする（未実行なら即時）"""
    if config.last_run_at:
        next_run = config.last_run_at + timedelta(hours=interval_hours)
        if next_run > datetime.utcnow():
            return next_run
    return datetime.utcnow()


def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        refresh_jobs()
        logger.info("スケジューラー起動")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("スケジューラー停止")

"""
Entry point. Starts the Discord bot and schedules the pipeline to run daily at 7 PM.
"""
import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from database.db import Database
from discord_bot.bot import OpportunitiesBot
from pipeline.runner import run_pipeline

logger = logging.getLogger(__name__)


async def main():
    # ── Validate required config ──────────────────────────────────────────────
    missing = []
    if not config.DISCORD_BOT_TOKEN:
        missing.append("DISCORD_BOT_TOKEN")
    if not config.ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if missing:
        raise SystemExit(f"Missing required env vars: {', '.join(missing)}\nCopy .env.example → .env and fill them in.")

    # ── Initialize shared resources ───────────────────────────────────────────
    db = Database(config.DB_PATH)
    bot = OpportunitiesBot()
    bot.setup_commands(db)

    await bot.start()

    # ── Scheduler ─────────────────────────────────────────────────────────────
    scheduler = AsyncIOScheduler(timezone=config.SCHEDULE_TIMEZONE)
    scheduler.add_job(
        run_pipeline,
        trigger=CronTrigger(
            hour=config.SCHEDULE_HOUR,
            minute=config.SCHEDULE_MINUTE,
            timezone=config.SCHEDULE_TIMEZONE,
        ),
        args=[bot, db],
        id="daily_pipeline",
        name="Daily opportunities pipeline",
        replace_existing=True,
    )
    scheduler.start()

    logger.info(
        "Scheduler started — pipeline runs daily at %02d:%02d %s",
        config.SCHEDULE_HOUR,
        config.SCHEDULE_MINUTE,
        config.SCHEDULE_TIMEZONE,
    )
    logger.info("Type Ctrl+C to stop.")

    # ── Keep alive ────────────────────────────────────────────────────────────
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
        scheduler.shutdown(wait=False)
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())

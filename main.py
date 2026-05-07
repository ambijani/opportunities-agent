"""
Entry point. Starts the Discord bot, schedules the pipeline, and serves a
health endpoint on $PORT (default 8080) for Cloud Run.
"""
import asyncio
import logging
import os

import uvicorn
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from database.db import Database
from discord_bot.bot import OpportunitiesBot
from pipeline.runner import run_pipeline

logger = logging.getLogger(__name__)

health_app = FastAPI()


@health_app.get("/health")
async def health():
    return {"status": "ok"}


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
    db = Database()
    bot = OpportunitiesBot()
    bot.setup_commands(db)

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

    # ── Health server config ───────────────────────────────────────────────────
    port = int(os.getenv("PORT", "8080"))
    server_config = uvicorn.Config(health_app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(server_config)

    logger.info(
        "Scheduler will run daily at %02d:%02d %s",
        config.SCHEDULE_HOUR,
        config.SCHEDULE_MINUTE,
        config.SCHEDULE_TIMEZONE,
    )

    # ── Run everything concurrently ───────────────────────────────────────────
    scheduler.start()
    await asyncio.gather(
        bot.start(),
        server.serve(),
    )


if __name__ == "__main__":
    asyncio.run(main())

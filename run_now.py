"""Run the pipeline once immediately (for local testing)."""
import asyncio
import config
from database.db import Database
from pipeline.webhook_poster import WebhookPoster
from pipeline.runner import run_pipeline


async def main():
    db = Database()
    poster = WebhookPoster(config.WEBHOOK_MAP)
    await run_pipeline(poster, db)


asyncio.run(main())

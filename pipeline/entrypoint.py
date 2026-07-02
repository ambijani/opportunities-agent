"""
GitHub Actions entry point — runs the pipeline once and exits.
Replaces main.py's APScheduler + always-on bot setup.
"""
import asyncio
import logging
import os
import sys

import config
from database.db import Database
from pipeline.webhook_poster import WebhookPoster
from pipeline.runner import run_pipeline

logger = logging.getLogger(__name__)


async def main() -> None:
    missing = []
    if not config.ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if not config.TURSO_DATABASE_URL:
        missing.append("TURSO_DATABASE_URL")
    if missing:
        logger.error("Missing required env vars: %s", ", ".join(missing))
        sys.exit(1)

    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
    if dry_run:
        logger.info("DRY RUN — jobs will be classified and validated but NOT posted to Discord")

    db = Database()
    poster = WebhookPoster(config.WEBHOOK_MAP)

    if dry_run:
        # Wrap poster so nothing is sent and nothing is marked posted
        class _DryRunPoster:
            def post_jobs(self, channel_id, jobs):
                logger.info("[dry-run] Would post %d jobs to channel %s", len(jobs), channel_id)
                return []
        poster = _DryRunPoster()

    await run_pipeline(poster, db)


if __name__ == "__main__":
    asyncio.run(main())

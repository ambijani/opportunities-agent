"""
Pipeline orchestrator.
  1. Runs all scrapers (in a thread pool — they use sync Playwright)
  2. Deduplicates against the SQLite DB
  3. Classifies each new job (keywords first, Claude for ambiguous ones)
  4. Posts to Discord and records in the DB
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

import config
from database.db import Database
from database.models import Job
from scrapers.github_scraper import GitHubScraper
from scrapers.intern_list_scraper import InternListScraper
from scrapers.newgrad_jobs_scraper import NewGradJobsScraper
from classifier import keyword_filter
from classifier.claude_classifier import ClaudeClassifier
from discord_bot.bot import OpportunitiesBot
from pipeline.link_validator import validate_jobs

logger = logging.getLogger(__name__)


async def run_pipeline(bot: OpportunitiesBot, db: Database) -> None:
    logger.info("═══ Pipeline started ═══")

    # ── 1. Scrape all sources in parallel (sync scrapers → thread pool) ───────
    loop = asyncio.get_event_loop()
    scrapers = [
        GitHubScraper(),
        InternListScraper(),
        NewGradJobsScraper(),
    ]

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [loop.run_in_executor(executor, s.scrape) for s in scrapers]
        results = await asyncio.gather(*futures, return_exceptions=True)

    all_jobs: list[Job] = []
    for scraper, result in zip(scrapers, results):
        if isinstance(result, Exception):
            logger.error("Scraper %s failed: %s", type(scraper).__name__, result)
        else:
            all_jobs.extend(result)

    logger.info("Scraped %d total jobs", len(all_jobs))

    # ── 2. Deduplicate ────────────────────────────────────────────────────────
    new_jobs = [j for j in all_jobs if not db.has_been_posted(j.url)]
    logger.info("%d new (unposted) jobs", len(new_jobs))

    if not new_jobs:
        logger.info("Nothing new to post today.")
        return

    # ── 3. Classify ───────────────────────────────────────────────────────────
    # Pass 1: fast keyword filter
    for job in new_jobs:
        keyword_filter.classify(job)

    kw_done = [j for j in new_jobs if j.job_type is not None and j.category is not None]
    needs_claude = [j for j in new_jobs if j.job_type is None or j.category is None]
    logger.info("Keywords classified %d; sending %d to Claude", len(kw_done), len(needs_claude))

    # Pass 2: Claude batch for the remainder
    if needs_claude:
        claude = ClaudeClassifier()
        needs_claude = await claude.classify_batch(needs_claude)

    classified = new_jobs  # mutations were in-place

    # ── 4. Validate links ─────────────────────────────────────────────────────
    classified = await validate_jobs(classified)
    if not classified:
        logger.info("No valid links to post after validation.")
        return

    # ── 5. Post to Discord ────────────────────────────────────────────────────
    posted = 0
    for job in classified:
        channel_id = await bot.post_job(job)
        if channel_id:
            db.mark_posted(job, channel_id)
            posted += 1

    logger.info("═══ Pipeline done: %d/%d jobs posted ═══", posted, len(classified))
    db_stats = db.stats()
    logger.info("DB totals: %s", db_stats)

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
from scrapers.slack_scraper import SlackScraper
from classifier import keyword_filter
from classifier.claude_classifier import ClaudeClassifier
from discord_bot.bot import OpportunitiesBot

logger = logging.getLogger(__name__)


async def run_pipeline(bot: OpportunitiesBot, db: Database) -> None:
    logger.info("═══ Pipeline started ═══")

    # ── 1. Scrape all sources in parallel (sync scrapers → thread pool) ───────
    loop = asyncio.get_event_loop()
    scrapers = [
        GitHubScraper(),
        InternListScraper(),
        NewGradJobsScraper(),
        SlackScraper(),
    ]

    with ThreadPoolExecutor(max_workers=4) as executor:
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
    claude = ClaudeClassifier()
    classified: list[Job] = []

    for job in new_jobs:
        job = keyword_filter.classify(job)
        if job.job_type is None or job.category is None:
            job = claude.classify(job)
        classified.append(job)

    kw_classified = sum(
        1 for j in classified if j.job_type is not None and j.category is not None
    )
    logger.info(
        "Classification done: %d via keywords, %d via Claude",
        kw_classified,
        len(classified) - kw_classified,
    )

    # ── 4. Post to Discord ────────────────────────────────────────────────────
    posted = 0
    for job in classified:
        channel_id = await bot.post_job(job)
        if channel_id:
            db.mark_posted(job, channel_id)
            posted += 1

    logger.info("═══ Pipeline done: %d/%d jobs posted ═══", posted, len(classified))
    db_stats = db.stats()
    logger.info("DB totals: %s", db_stats)

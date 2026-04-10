"""
Dry run — executes the full pipeline (scrape → dedup → classify → validate)
but does NOT post to Discord. Writes a report to reports/dry_run_<timestamp>.txt.

Usage:
    python dry_run.py                  # full pipeline with link validation
    python dry_run.py --skip-validation  # skip HTTP link checks (faster)
"""
import asyncio
import sys
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import config
from database.db import Database
from database.models import Job
from scrapers.github_scraper import GitHubScraper
from scrapers.intern_list_scraper import InternListScraper
from scrapers.newgrad_jobs_scraper import NewGradJobsScraper
from classifier import keyword_filter
from classifier.claude_classifier import ClaudeClassifier
from pipeline.link_validator import validate_jobs, _check_url, _sanity_check

SKIP_VALIDATION = "--skip-validation" in sys.argv
REPORTS_DIR = "./reports"

CHANNEL_LABELS = {
    ("internship", "programs"):                    "Internships → #programs",
    ("internship", "cs-engineering-tech"):         "Internships → #cs-engineering-tech",
    ("internship", "business-finance-banking"):    "Internships → #business-finance-banking",
    ("internship", "consulting"):                  "Internships → #consulting",
    ("internship", "humanities-healthcare-medicine"): "Internships → #humanities-healthcare-medicine",
    ("internship", "scholarships"):               "#scholarships",
    ("full_time",  "programs"):                    "Full-Time → #programs",
    ("full_time",  "cs-engineering-tech"):         "Full-Time → #cs-engineering-tech",
    ("full_time",  "business-finance-banking"):    "Full-Time → #business-finance-banking",
    ("full_time",  "consulting"):                  "Full-Time → #consulting",
    ("full_time",  "humanities-healthcare-medicine"): "Full-Time → #humanities-healthcare-medicine",
    ("full_time",  "scholarships"):               "#scholarships",
}


def channel_label(job: Job) -> str:
    return CHANNEL_LABELS.get(
        (job.job_type or "internship", job.category or "programs"),
        f"{job.job_type} → #{job.category}",
    )


async def main():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_path = os.path.join(REPORTS_DIR, f"dry_run_{timestamp}.txt")

    lines: list[str] = []

    def log(text: str = ""):
        print(text)
        lines.append(text)

    log(f"DRY RUN — {timestamp}")
    log(f"Link validation: {'SKIPPED' if SKIP_VALIDATION else 'ENABLED'}")
    log("=" * 70)

    # ── 1. Scrape ─────────────────────────────────────────────────────────────
    log("\n── SCRAPING ──────────────────────────────────────────────────────────")
    scrapers = [GitHubScraper(), InternListScraper(), NewGradJobsScraper()]
    scraper_results: dict[str, list[Job]] = {}

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            type(s).__name__: loop.run_in_executor(executor, s.scrape)
            for s in scrapers
        }
        for name, future in futures.items():
            try:
                result = await future
                scraper_results[name] = result
                log(f"  {name}: {len(result)} jobs")
            except Exception as e:
                scraper_results[name] = []
                log(f"  {name}: ERROR — {e}")

    all_jobs = [j for jobs in scraper_results.values() for j in jobs]
    log(f"\n  Total scraped: {len(all_jobs)}")

    # ── 2. Deduplicate ────────────────────────────────────────────────────────
    log("\n── DEDUPLICATION ─────────────────────────────────────────────────────")
    db = Database(config.DB_PATH)
    already_posted = [j for j in all_jobs if db.has_been_posted(j.url)]
    new_jobs = [j for j in all_jobs if not db.has_been_posted(j.url)]
    log(f"  Already posted (skipped): {len(already_posted)}")
    log(f"  New jobs to process:      {len(new_jobs)}")

    if not new_jobs:
        log("\nNothing new to post. Done.")
        _write_report(report_path, lines)
        return

    # ── 3. Classify ───────────────────────────────────────────────────────────
    log("\n── CLASSIFICATION ────────────────────────────────────────────────────")
    for job in new_jobs:
        keyword_filter.classify(job)

    kw_done = [j for j in new_jobs if j.job_type is not None and j.category is not None]
    needs_claude = [j for j in new_jobs if j.job_type is None or j.category is None]
    log(f"  Keyword classifier: {len(kw_done)} jobs")
    log(f"  Claude classifier:  {len(needs_claude)} jobs (batched)")

    if needs_claude:
        claude = ClaudeClassifier()
        await claude.classify_batch(needs_claude)

    classified = new_jobs  # mutations were in-place

    # ── 4. Link validation ────────────────────────────────────────────────────
    parse_error_jobs: list[tuple[Job, str]] = []
    dead_link_jobs: list[tuple[Job, str]] = []
    valid_jobs: list[Job] = []

    if SKIP_VALIDATION:
        log("\n── LINK VALIDATION ───────────────────────────────────────────────────")
        log("  Skipped.")
        valid_jobs = classified
    else:
        log("\n── LINK VALIDATION ───────────────────────────────────────────────────")
        log(f"  Checking {len(classified)} URLs...")

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures_v = [
                loop.run_in_executor(executor, _check_url, job.url)
                for job in classified
            ]
            results = await asyncio.gather(*futures_v)

        url_result = {url: (ok, reason) for url, ok, reason in results}

        for job in classified:
            ok, reason = url_result.get(job.url, (True, "ok"))
            if ok:
                valid_jobs.append(job)
            elif reason.startswith("PARSE ERROR"):
                parse_error_jobs.append((job, reason))
            else:
                dead_link_jobs.append((job, reason))

        log(f"  Valid:       {len(valid_jobs)}")
        log(f"  Dead links:  {len(dead_link_jobs)}")
        log(f"  Parse errors (scraper bugs): {len(parse_error_jobs)}")

    # ── 5. What would be posted ───────────────────────────────────────────────
    log("\n── WOULD BE POSTED ───────────────────────────────────────────────────")
    if not valid_jobs:
        log("  (nothing)")
    else:
        by_channel: dict[str, list[Job]] = {}
        for job in valid_jobs:
            label = channel_label(job)
            by_channel.setdefault(label, []).append(job)

        for ch_label, ch_jobs in sorted(by_channel.items()):
            log(f"\n  {ch_label}  ({len(ch_jobs)} jobs)")
            for job in ch_jobs:
                log(f"    • {job.title} — {job.company}")
                log(f"      {job.url}")
                log(f"      Location: {job.location}  |  Posted: {job.date_posted}  |  Source: {job.source}")

    # ── 6. Removed jobs ───────────────────────────────────────────────────────
    if dead_link_jobs:
        log("\n── REMOVED — DEAD LINKS ──────────────────────────────────────────────")
        for job, reason in dead_link_jobs:
            log(f"  • {job.title} — {job.company}")
            log(f"    {job.url}")
            log(f"    Reason: {reason}")

    if parse_error_jobs:
        log("\n── REMOVED — SCRAPER PARSE ERRORS (fix the scraper!) ─────────────────")
        for job, reason in parse_error_jobs:
            log(f"  • {job.title} — {job.company}")
            log(f"    URL as parsed: {job.url!r}")
            log(f"    Reason: {reason}")

    # ── Summary ───────────────────────────────────────────────────────────────
    log("\n── SUMMARY ───────────────────────────────────────────────────────────")
    log(f"  Scraped:       {len(all_jobs)}")
    log(f"  Already posted:{len(already_posted)}")
    log(f"  New:           {len(new_jobs)}")
    log(f"  Would post:    {len(valid_jobs)}")
    log(f"  Dead links:    {len(dead_link_jobs)}")
    log(f"  Parse errors:  {len(parse_error_jobs)}")
    log(f"\n  Report saved → {report_path}")

    _write_report(report_path, lines)


def _write_report(path: str, lines: list[str]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())

"""
Validates job apply URLs before posting to Discord.

Two-stage process:
  1. Sanity check — is the URL well-formed? Catches scraper parse errors before
     we ever make an HTTP request.
  2. HTTP check — does the URL actually resolve? Catches dead/closed listings.

These are logged separately so you can tell the difference between a scraper bug
(malformed URL) and a genuinely dead link.
"""
import logging
import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

TIMEOUT = 10
MAX_WORKERS = 10
VALID_STATUSES = set(range(200, 400))  # 2xx and 3xx

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Known job board domains — used to flag unexpected domains as possible parse errors
KNOWN_JOB_DOMAINS = {
    "linkedin.com", "greenhouse.io", "lever.co", "workday.com", "myworkdayjobs.com",
    "jobright.ai", "indeed.com", "glassdoor.com", "ziprecruiter.com", "simplify.jobs",
    "careers.google.com", "jobs.apple.com", "amazon.jobs", "microsoft.com",
    "recruiting.ultipro.com", "icims.com", "taleo.net", "smartrecruiters.com",
    "breezy.hr", "ashbyhq.com", "rippling.com", "workable.com", "applytojob.com",
    "internships.com", "wayup.com", "handshake.com", "joinhandshake.com",
    "college.handshake.com", "airtable.com", "notion.so", "wellfound.com",
}

# Patterns that suggest a URL was parsed incorrectly
MALFORMED_PATTERNS = [
    r"\s",                    # whitespace in URL
    r"\]\(",                  # markdown artifact ](
    r"\)\[",                  # markdown artifact )[
    r"!\[",                   # image markdown artifact
    r"<|>",                   # HTML tag remnants
    r"\|",                    # pipe character (table artifact)
    r"\.\.\.+",               # truncated with ellipsis
]
_MALFORMED_RE = re.compile("|".join(MALFORMED_PATTERNS))


def _sanity_check(url: str) -> tuple[bool, str | None]:
    """
    Returns (is_sane, reason).
    reason is None if sane, or a human-readable explanation if not.
    """
    if not url or not isinstance(url, str):
        return False, "empty or non-string URL"

    if not url.startswith(("http://", "https://")):
        return False, f"missing http(s) scheme: {url!r}"

    if _MALFORMED_RE.search(url):
        return False, f"contains parsing artifact: {url!r}"

    try:
        parsed = urlparse(url)
    except Exception:
        return False, f"urlparse failed: {url!r}"

    if not parsed.netloc or "." not in parsed.netloc:
        return False, f"no valid domain in: {url!r}"

    if len(url) < 15:
        return False, f"suspiciously short URL: {url!r}"

    return True, None


def _check_url(url: str) -> tuple[str, bool, str]:
    """
    Returns (url, is_valid, reason).
    reason describes why a link was rejected (for logging).
    """
    # Stage 1: sanity check
    sane, reason = _sanity_check(url)
    if not sane:
        return url, False, f"PARSE ERROR — {reason}"

    # Stage 2: HTTP check
    try:
        resp = requests.head(
            url, timeout=TIMEOUT, allow_redirects=True, headers=HEADERS
        )
        if resp.status_code in VALID_STATUSES:
            return url, True, "ok"

        if resp.status_code == 403:
            # Anti-bot blocking ≠ dead link
            return url, True, "ok"

        if resp.status_code == 405:
            # Server doesn't support HEAD — try GET
            resp = requests.get(
                url, timeout=TIMEOUT, allow_redirects=True,
                headers=HEADERS, stream=True,
            )
            resp.close()
            if resp.status_code in VALID_STATUSES:
                return url, True, "ok"
            if resp.status_code == 403:
                return url, True, "ok"

        return url, False, f"DEAD LINK — HTTP {resp.status_code}"

    except requests.exceptions.SSLError:
        return url, True, "ok"       # cert issue ≠ dead site
    except requests.exceptions.ConnectionError:
        return url, False, "DEAD LINK — connection refused / DNS failure"
    except requests.exceptions.Timeout:
        return url, True, "ok"       # slow ≠ dead
    except Exception as e:
        return url, True, "ok"       # unknown → allow through


# Sources whose URLs come directly from a live API — sanity check only, no HTTP
_TRUSTED_SOURCES = {"intern_list", "newgrad_jobs"}


async def validate_jobs(jobs: list) -> list:
    """
    Validates job URLs.
    - Trusted sources (jobright.ai): sanity check only — URLs come from a live API.
    - Other sources (github_readme): full HTTP check to catch dead/closed listings.
    Returns only jobs with valid, reachable URLs.
    """
    if not jobs:
        return jobs

    # Split: trusted = sanity only, untrusted = full HTTP check
    trusted = [j for j in jobs if j.source in _TRUSTED_SOURCES]
    untrusted = [j for j in jobs if j.source not in _TRUSTED_SOURCES]

    loop = asyncio.get_event_loop()

    # Sanity-check trusted URLs (no network, instant)
    trusted_results = []
    for j in trusted:
        ok, reason = _sanity_check(j.url)
        trusted_results.append((j.url, ok, reason or "ok"))

    # Full HTTP check for untrusted URLs (github_readme etc.)
    http_results = []
    if untrusted:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [
                loop.run_in_executor(executor, _check_url, job.url)
                for job in untrusted
            ]
            http_results = list(await asyncio.gather(*futures))

    results = trusted_results + http_results

    url_to_result: dict[str, tuple[bool, str]] = {
        url: (ok, reason) for url, ok, reason in results
    }

    valid_jobs = []
    parse_errors = []
    dead_links = []

    for job in jobs:
        ok, reason = url_to_result.get(job.url, (True, "ok"))
        if ok:
            valid_jobs.append(job)
        elif reason.startswith("PARSE ERROR"):
            parse_errors.append((job, reason))
        else:
            dead_links.append((job, reason))

    if parse_errors:
        logger.warning(
            "⚠️  %d URL(s) look malformed — likely a scraper parsing bug:\n%s",
            len(parse_errors),
            "\n".join(
                f"  [{j.source}] {j.title!r} → {j.url!r}  ({r})"
                for j, r in parse_errors
            ),
        )

    if dead_links:
        logger.info(
            "🔗 %d dead link(s) removed (job closed or page removed):\n%s",
            len(dead_links),
            "\n".join(
                f"  [{j.source}] {j.title!r} → {j.url}  ({r})"
                for j, r in dead_links
            ),
        )

    logger.info(
        "Link validation: %d valid, %d dead, %d malformed (out of %d)",
        len(valid_jobs), len(dead_links), len(parse_errors), len(jobs),
    )
    return valid_jobs

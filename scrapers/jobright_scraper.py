"""
Shared Playwright scraper for jobright.ai-powered sites (intern-list.com, newgrad-jobs.com).
Both sites embed job listings via iframes pointing to jobright.ai minisites.
"""
import logging
import time

from playwright.sync_api import sync_playwright, Page, ElementHandle

from database.models import Job
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# How long to wait (ms) for job cards to appear after navigation
LOAD_TIMEOUT = 15_000
CARD_WAIT_TIMEOUT = 10_000


class JobrightScraper(BaseScraper):
    """
    Base class for scraping jobright.ai minisite embeds.

    Subclasses set:
      - parent_url: the containing page URL
      - source_name: label for the Job.source field
      - minisite_type: "intern-list" or "newgrad" (used in the iframe URL)
    """

    parent_url: str = ""
    source_name: str = ""
    minisite_type: str = ""

    def scrape(self) -> list[Job]:
        jobs: list[Job] = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )
                )
                page = context.new_page()
                jobs = self._scrape_page(page)
                browser.close()
        except Exception as e:
            logger.error("Playwright error scraping %s: %s", self.parent_url, e)
        return jobs

    def _scrape_page(self, page: Page) -> list[Job]:
        logger.info("Loading %s", self.parent_url)
        page.goto(self.parent_url, wait_until="domcontentloaded", timeout=LOAD_TIMEOUT)
        page.wait_for_timeout(3000)  # let JS initialize

        # Collect all job-path buttons/tabs on the parent page
        job_paths = self._collect_job_paths(page)
        if not job_paths:
            logger.warning("No data-job-path attributes found on %s", self.parent_url)
            return []

        logger.info("Found %d job paths on %s", len(job_paths), self.parent_url)

        all_jobs: list[Job] = []
        for job_path in job_paths:
            iframe_url = self._build_iframe_url(job_path)
            path_jobs = self._scrape_iframe(page, iframe_url, job_path)
            logger.info("  [%s] %s → %d jobs", self.source_name, job_path, len(path_jobs))
            all_jobs.extend(path_jobs)
            time.sleep(1)  # be polite

        return all_jobs

    def _collect_job_paths(self, page: Page) -> list[str]:
        """Extract unique data-job-path values from the parent page."""
        elements = page.query_selector_all("[data-job-path]")
        seen: set[str] = set()
        paths: list[str] = []
        for el in elements:
            path = el.get_attribute("data-job-path")
            if path and path not in seen:
                seen.add(path)
                paths.append(path)
        return paths

    def _build_iframe_url(self, job_path: str) -> str:
        return f"https://jobright.ai/minisites-jobs/{self.minisite_type}/{job_path}?embed=true"

    def _scrape_iframe(self, page: Page, iframe_url: str, job_path: str) -> list[Job]:
        try:
            page.goto(iframe_url, wait_until="networkidle", timeout=LOAD_TIMEOUT)
        except Exception:
            # networkidle can time out on heavy pages; try domcontentloaded
            try:
                page.goto(iframe_url, wait_until="domcontentloaded", timeout=LOAD_TIMEOUT)
                page.wait_for_timeout(4000)
            except Exception as e:
                logger.warning("Failed to load iframe %s: %s", iframe_url, e)
                return []

        # Try to wait for job cards
        card_selector = self._card_selector()
        try:
            page.wait_for_selector(card_selector, timeout=CARD_WAIT_TIMEOUT)
        except Exception:
            logger.debug("No cards found at %s", iframe_url)
            return []

        cards = page.query_selector_all(card_selector)
        jobs = []
        for card in cards:
            job = self._parse_card(card, job_path)
            if job:
                jobs.append(job)
        return jobs

    def _card_selector(self) -> str:
        # jobright.ai minisites render job cards — try common selectors
        # These may need adjustment if the site changes its HTML
        return "div[class*='job-card'], article[class*='job'], div[class*='JobCard'], li[class*='job']"

    def _parse_card(self, card: ElementHandle, job_path: str) -> Job | None:
        try:
            title = self._text(card, [
                "[class*='job-title']", "[class*='title']", "h2", "h3", "h4"
            ])
            company = self._text(card, [
                "[class*='company']", "[class*='employer']", "[class*='org']"
            ])
            location = self._text(card, [
                "[class*='location']", "[class*='city']", "[class*='place']"
            ]) or "Unknown"
            date_posted = self._text(card, [
                "[class*='date']", "[class*='posted']", "[class*='time']", "time"
            ]) or "Unknown"
            description = self._text(card, [
                "[class*='description']", "[class*='summary']", "[class*='snippet']", "p"
            ]) or ""

            # Apply URL: prefer <a> inside the card
            url = None
            link_el = card.query_selector("a[href]")
            if link_el:
                href = link_el.get_attribute("href") or ""
                if href.startswith("http"):
                    url = href
                elif href.startswith("/"):
                    url = f"https://jobright.ai{href}"

            if not url or not title:
                return None

            return Job(
                id=self._make_id(url),
                title=title.strip(),
                company=(company or "Unknown").strip(),
                location=location.strip(),
                description=description.strip(),
                url=url,
                date_posted=date_posted.strip(),
                source=self.source_name,
                job_type=None,
                category=None,
            )
        except Exception as e:
            logger.debug("Failed to parse card: %s", e)
            return None

    def _text(self, root: ElementHandle, selectors: list[str]) -> str | None:
        for sel in selectors:
            el = root.query_selector(sel)
            if el:
                text = el.inner_text().strip()
                if text:
                    return text
        return None

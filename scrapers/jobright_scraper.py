"""
Shared Playwright scraper for jobright.ai-powered sites (intern-list.com, newgrad-jobs.com).

Strategy:
  1. Load the parent page once to establish session cookies.
  2. Collect all /us/ job-path slugs from [data-job-path] attributes.
  3. Navigate directly to each jobright.ai minisite URL using the same browser
     context (cookies intact) with the parent page set as Referer.
  4. On each minisite page, try __NEXT_DATA__ JSON first (reliable), then fall
     back to DOM parsing.
  5. US-only paths — skips /ca/ to halve the tab count.
"""
import json
import logging
import time

from playwright.sync_api import sync_playwright, Page

from database.models import Job
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

PAGE_LOAD_TIMEOUT = 20_000
MINISITE_TIMEOUT = 15_000


# Map jobright.ai path slug → our category
PATH_CATEGORY_MAP: dict[str, str] = {
    "/us/swe":                    "cs-engineering-tech",
    "/us/data_analysis":          "cs-engineering-tech",
    "/us/ml_ai":                  "cs-engineering-tech",
    "/us/data_engineer":          "cs-engineering-tech",
    "/us/cyber_security":         "cs-engineering-tech",
    "/us/engineering_development":"cs-engineering-tech",
    "/us/product_management":     "cs-engineering-tech",
    "/us/project_manager":        "cs-engineering-tech",
    "/us/business_analyst":       "business-finance-banking",
    "/us/accounting_finance":     "business-finance-banking",
    "/us/human_resources":        "business-finance-banking",
    "/us/management_executive":   "business-finance-banking",
    "/us/sales":                  "business-finance-banking",
    "/us/supply_chain":           "business-finance-banking",
    "/us/consulting":             "consulting",
    "/us/marketing_gen":          "business-finance-banking",
    "/us/creatives_design":       "humanities-healthcare-medicine",
    "/us/customer_service":       "humanities-healthcare-medicine",
    "/us/education_training":     "humanities-healthcare-medicine",
    "/us/healthcare":             "humanities-healthcare-medicine",
    "/us/legal_compliance":       "humanities-healthcare-medicine",
    "/us/arts_entertainment":     "humanities-healthcare-medicine",
    "/us/public_sector":          "humanities-healthcare-medicine",
}


class JobrightScraper(BaseScraper):
    parent_url: str = ""
    source_name: str = ""
    minisite_type: str = ""
    default_job_type: str | None = None  # set in subclasses

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
                    ),
                    viewport={"width": 1280, "height": 900},
                )
                page = context.new_page()
                jobs = self._scrape_all(page)
                browser.close()
        except Exception as e:
            logger.error("Playwright error scraping %s: %s", self.parent_url, e)
        return jobs

    def _scrape_all(self, page: Page) -> list[Job]:
        # Step 1: load parent to get session cookies
        logger.info("Loading %s", self.parent_url)
        try:
            page.goto(self.parent_url, wait_until="networkidle", timeout=PAGE_LOAD_TIMEOUT)
        except Exception:
            page.goto(self.parent_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
        page.wait_for_timeout(2000)

        # Step 2: collect job-path slugs (prefer /us/ paths, fall back to all)
        tab_els = page.query_selector_all("[data-job-path]")
        seen_paths: set[str] = set()
        all_paths: list[str] = []
        for el in tab_els:
            path = el.get_attribute("data-job-path") or ""
            if path and path not in seen_paths:
                seen_paths.add(path)
                all_paths.append(path)

        job_paths = [p for p in all_paths if p.startswith("/us/")]
        if not job_paths and all_paths:
            # Site may use different region prefix — use all discovered paths
            logger.warning(
                "No /us/ paths found on %s; sample paths: %s",
                self.parent_url, all_paths[:5],
            )
            job_paths = all_paths
        elif not all_paths:
            logger.warning("No [data-job-path] elements found on %s", self.parent_url)

        logger.info("Found %d job paths on %s", len(job_paths), self.parent_url)

        # Step 2b: try to detect the correct minisite_type from the parent page
        minisite_type = self._detect_minisite_type(page) or self.minisite_type
        if minisite_type != self.minisite_type:
            logger.info(
                "Auto-detected minisite_type=%r (overrides class default %r)",
                minisite_type, self.minisite_type,
            )

        # Step 3: navigate to each minisite URL directly
        page.set_extra_http_headers({"Referer": self.parent_url})

        all_jobs: list[Job] = []
        seen_urls: set[str] = set()

        for path in job_paths:
            url = f"https://jobright.ai/minisites-jobs/{minisite_type}{path}?embed=true"
            path_jobs = self._scrape_minisite(page, url, path, seen_urls)
            logger.info("  [%s] %s → %d jobs", self.source_name, path, len(path_jobs))
            all_jobs.extend(path_jobs)
            time.sleep(0.3)

        return all_jobs

    def _detect_minisite_type(self, page: Page) -> str | None:
        """
        Try to read the minisite_type from the page's own jobright.ai embed URLs.
        Looks for iframes or script-injected URLs like:
          https://jobright.ai/minisites-jobs/<type>/us/...
        """
        import re as _re
        try:
            html = page.content()
            m = _re.search(
                r'jobright\.ai/minisites-jobs/([^/\s"\'?]+)',
                html,
            )
            if m:
                return m.group(1)
        except Exception:
            pass
        return None

    def _scrape_minisite(
        self, page: Page, url: str, path: str, seen_urls: set[str]
    ) -> list[Job]:
        try:
            page.goto(url, wait_until="networkidle", timeout=MINISITE_TIMEOUT)
        except Exception:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=MINISITE_TIMEOUT)
                page.wait_for_timeout(3000)
            except Exception as e:
                logger.debug("Failed to load %s: %s", url, e)
                return []

        # Try __NEXT_DATA__ first — most reliable for Next.js apps
        jobs = self._parse_next_data(page, path, seen_urls)
        if jobs:
            return jobs

        # Fall back to DOM parsing
        jobs = self._parse_dom(page, path, seen_urls)

        if not jobs:
            # Log page title to help diagnose wrong minisite_type
            try:
                title = page.title()
                current_url = page.url
                logger.debug(
                    "0 jobs from %s | page title: %r | final URL: %s",
                    url, title, current_url,
                )
            except Exception:
                pass

        return jobs

    # ── __NEXT_DATA__ parser ───────────────────────────────────────────────────

    def _parse_next_data(
        self, page: Page, path: str, seen_urls: set[str]
    ) -> list[Job]:
        try:
            raw = page.evaluate(
                "() => { const el = document.getElementById('__NEXT_DATA__'); "
                "return el ? el.textContent : null; }"
            )
            if not raw:
                return []
            data = json.loads(raw)
        except Exception:
            return []

        # Walk the Next.js page props tree looking for job arrays
        job_records = self._find_jobs_in_dict(data)
        if not job_records:
            return []

        jobs = []
        for record in job_records:
            job = self._record_to_job(record, path, seen_urls)
            if job:
                seen_urls.add(job.url)
                jobs.append(job)
        return jobs

    def _find_jobs_in_dict(self, obj, depth: int = 0) -> list[dict]:
        """Recursively search for an array of job-like dicts in the Next.js data tree."""
        if depth > 8:
            return []
        if isinstance(obj, list):
            if obj and isinstance(obj[0], dict) and self._looks_like_job(obj[0]):
                return obj
            for item in obj:
                result = self._find_jobs_in_dict(item, depth + 1)
                if result:
                    return result
        elif isinstance(obj, dict):
            for val in obj.values():
                result = self._find_jobs_in_dict(val, depth + 1)
                if result:
                    return result
        return []

    def _looks_like_job(self, d: dict) -> bool:
        job_keys = {"title", "company", "location", "url", "applyUrl", "jobUrl",
                    "companyName", "jobTitle", "position", "role"}
        return bool(job_keys & set(d.keys()))

    def _record_to_job(
        self, record: dict, path: str, seen_urls: set[str]
    ) -> Job | None:
        # Try common key names used by jobright.ai
        title = (
            record.get("title") or record.get("jobTitle") or
            record.get("position") or record.get("role") or ""
        ).strip()
        company = (
            record.get("company") or record.get("companyName") or
            record.get("employer") or "Unknown"
        ).strip()
        location = (
            record.get("location") or record.get("city") or
            record.get("locationName") or "Unknown"
        ).strip()
        description = (
            record.get("description") or record.get("summary") or
            record.get("snippet") or ""
        ).strip()
        date_posted = (
            record.get("datePosted") or record.get("postedAt") or
            record.get("createdAt") or record.get("date") or "Unknown"
        ).strip() if isinstance(
            record.get("datePosted") or record.get("postedAt") or
            record.get("createdAt") or record.get("date"), str
        ) else "Unknown"

        url = (
            record.get("applyUrl") or record.get("jobUrl") or
            record.get("url") or record.get("link") or record.get("applicationUrl") or ""
        ).strip()

        # Some records have a relative path — make it absolute
        if url and url.startswith("/"):
            url = "https://jobright.ai" + url

        if not url or not title:
            return None
        if url in seen_urls:
            return None

        return Job(
            id=self._make_id(url),
            title=title,
            company=company,
            location=location,
            description=description[:300],
            url=url,
            date_posted=date_posted,
            source=self.source_name,
            job_type=self.default_job_type,
            category=PATH_CATEGORY_MAP.get(path),
        )

    # ── DOM fallback ───────────────────────────────────────────────────────────

    def _parse_dom(
        self, page: Page, path: str, seen_urls: set[str]
    ) -> list[Job]:
        card_sel = (
            "div[class*='job-card'], div[class*='JobCard'], "
            "article[class*='job'], li[class*='job-item'], "
            "div[class*='listing-card'], div[class*='job-listing']"
        )
        try:
            page.wait_for_selector(card_sel, timeout=5000)
        except Exception:
            # Last resort: grab all links that look like job postings
            return self._extract_links(page, path, seen_urls)

        cards = page.query_selector_all(card_sel)
        jobs = []
        for card in cards:
            try:
                title = self._text(card, ["[class*='title']", "h2", "h3", "h4"])
                company = self._text(card, ["[class*='company']", "[class*='employer']"])
                location = self._text(card, ["[class*='location']", "[class*='city']"]) or "Unknown"
                date_posted = self._text(card, ["[class*='date']", "[class*='posted']", "time"]) or "Unknown"
                description = self._text(card, ["[class*='description']", "[class*='summary']", "p"]) or ""

                link_el = card.query_selector("a[href]")
                url = ""
                if link_el:
                    href = link_el.get_attribute("href") or ""
                    url = href if href.startswith("http") else ("https://jobright.ai" + href if href.startswith("/") else "")

                if not url or not title or url in seen_urls:
                    continue

                seen_urls.add(url)
                jobs.append(Job(
                    id=self._make_id(url),
                    title=title.strip(),
                    company=(company or "Unknown").strip(),
                    location=location.strip(),
                    description=description.strip()[:300],
                    url=url,
                    date_posted=date_posted.strip(),
                    source=self.source_name,
                    job_type=self.default_job_type,
                    category=PATH_CATEGORY_MAP.get(path),
                ))
            except Exception as e:
                logger.debug("Card parse error: %s", e)
        return jobs

    def _extract_links(self, page: Page, path: str, seen_urls: set[str]) -> list[Job]:
        jobs = []
        try:
            for link in page.query_selector_all("a[href]"):
                href = link.get_attribute("href") or ""
                if not href.startswith("http") and not href.startswith("/"):
                    continue
                if href.startswith("/"):
                    href = "https://jobright.ai" + href
                if href in seen_urls:
                    continue
                text = (link.inner_text() or "").strip()
                if not text or len(text) < 5 or len(text) > 120:
                    continue
                seen_urls.add(href)
                jobs.append(Job(
                    id=self._make_id(href),
                    title=text,
                    company="Unknown",
                    location="Unknown",
                    description="",
                    url=href,
                    date_posted="Unknown",
                    source=self.source_name,
                    job_type=self.default_job_type,
                    category=PATH_CATEGORY_MAP.get(path),
                ))
        except Exception as e:
            logger.debug("Link extract error: %s", e)
        return jobs

    def _text(self, root, selectors: list[str]) -> str | None:
        for sel in selectors:
            try:
                el = root.query_selector(sel)
                if el:
                    t = el.inner_text().strip()
                    if t:
                        return t
            except Exception:
                continue
        return None

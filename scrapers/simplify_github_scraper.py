import logging

import requests
from bs4 import BeautifulSoup

from database.models import Job
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

README_URL = (
    "https://raw.githubusercontent.com/"
    "SimplifyJobs/Summer2027-Internships/dev/README.md"
)

# Rows under the same company show this in the Company cell instead of repeating the name
CONTINUATION_MARKER = "↳"
CLOSED_MARKER = "🔒"
REQUIRED_HEADERS = {"Company", "Role", "Application"}


class SimplifyGitHubScraper(BaseScraper):
    """Scrapes SimplifyJobs/Summer2027-Internships. Its tables are HTML <table> blocks, not markdown."""

    def scrape(self) -> list[Job]:
        try:
            resp = requests.get(README_URL, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error("Failed to fetch Simplify GitHub README: %s", e)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        jobs: list[Job] = []
        seen: set[str] = set()

        for table in soup.find_all("table"):
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            if not REQUIRED_HEADERS <= set(headers):
                continue

            table_jobs = self._parse_table(table, headers)
            logger.info("Simplify GitHub: found %d jobs in table", len(table_jobs))
            for job in table_jobs:
                if job.url not in seen:
                    seen.add(job.url)
                    jobs.append(job)

        return jobs

    def _parse_table(self, table, headers: list[str]) -> list[Job]:
        jobs: list[Job] = []
        company = "Unknown"

        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) != len(headers):
                continue  # header row or malformed row

            row = dict(zip(headers, (c.get_text(" ", strip=True) for c in cells)))
            link_cells = dict(zip(headers, cells))

            company_text = row.get("Company", "")
            if company_text and company_text != CONTINUATION_MARKER:
                company = company_text

            if CLOSED_MARKER in tr.get_text():
                continue

            apply_link = link_cells["Application"].find("a", href=True)
            if not apply_link or not apply_link["href"].startswith("http"):
                continue
            url = apply_link["href"]

            age = row.get("Age", "")
            jobs.append(Job(
                id=self._make_id(url),
                title=row.get("Role") or "Unknown Role",
                company=company,
                location=row.get("Location") or "Unknown",
                description="",
                url=url,
                date_posted=f"Posted {age} ago" if age else "Unknown",
                source="simplify_github",
                job_type=None,
                category=None,
            ))

        return jobs

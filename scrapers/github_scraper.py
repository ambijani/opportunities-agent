import logging
import re

import requests

from database.models import Job
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

README_URL = (
    "https://raw.githubusercontent.com/"
    "Jose-Gael-Cruz-Lopez/underclassmen-opportunities/main/README.md"
)

SECTIONS = {
    "internships": ("<!-- INTERNSHIPS_TABLE_START -->", "<!-- INTERNSHIPS_TABLE_END -->"),
    "programs":    ("<!-- PROGRAMS_TABLE_START -->",    "<!-- PROGRAMS_TABLE_END -->"),
    "research":    ("<!-- RESEARCH_TABLE_START -->",    "<!-- RESEARCH_TABLE_END -->"),
    "scholarships":("<!-- SCHOLARSHIPS_TABLE_START -->","<!-- SCHOLARSHIPS_TABLE_END -->"),
}


class GitHubScraper(BaseScraper):

    def scrape(self) -> list[Job]:
        try:
            resp = requests.get(README_URL, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error("Failed to fetch GitHub README: %s", e)
            return []

        readme = resp.text
        jobs: list[Job] = []

        for section_name, (start_tag, end_tag) in SECTIONS.items():
            section_text = self._extract_section(readme, start_tag, end_tag)
            if not section_text:
                logger.warning("Section %s not found in README", section_name)
                continue
            section_jobs = self._parse_section(section_text, section_name)
            logger.info("GitHub [%s]: found %d jobs", section_name, len(section_jobs))
            jobs.extend(section_jobs)

        # Deduplicate by URL within this scraper
        seen: set[str] = set()
        unique: list[Job] = []
        for job in jobs:
            if job.url not in seen:
                seen.add(job.url)
                unique.append(job)

        return unique

    # ── helpers ───────────────────────────────────────────────────────────────

    def _extract_section(self, text: str, start: str, end: str) -> str | None:
        s = text.find(start)
        e = text.find(end)
        if s == -1 or e == -1:
            return None
        return text[s + len(start):e].strip()

    def _parse_section(self, text: str, section_name: str) -> list[Job]:
        rows = self._parse_markdown_table(text)
        jobs = []
        for row in rows:
            try:
                job = self._row_to_job(row, section_name)
                if job:
                    jobs.append(job)
            except Exception as e:
                logger.debug("Skipping row in %s: %s | row=%s", section_name, e, row)
        return jobs

    def _parse_markdown_table(self, text: str) -> list[dict]:
        lines = [l.strip() for l in text.splitlines() if l.strip().startswith("|")]
        if len(lines) < 2:
            return []

        headers = [h.strip() for h in lines[0].split("|") if h.strip()]
        rows: list[dict] = []
        for line in lines[2:]:  # skip header + separator
            cells = [c.strip() for c in line.split("|")]
            cells = [c for c in cells if c != ""]
            if len(cells) < len(headers):
                # Pad with empty strings
                cells += [""] * (len(headers) - len(cells))
            rows.append(dict(zip(headers, cells[:len(headers)])))

        return rows

    def _extract_url(self, cell: str) -> str | None:
        # <a href="url"><img ...></a> (HTML anchor in markdown cell)
        m = re.search(r'href="(https?://[^"]+)"', cell)
        if m:
            return m.group(1)
        # [![Apply](badge)](url) or [![text](img)](url)
        m = re.search(r"\[!\[.*?\]\(.*?\)\]\((https?://[^)]+)\)", cell)
        if m:
            return m.group(1)
        # [text](url)
        m = re.search(r"\[.*?\]\((https?://[^)]+)\)", cell)
        if m:
            return m.group(1)
        # bare https://...
        m = re.search(r"https?://\S+", cell)
        if m:
            return m.group(0).rstrip(")")
        return None

    def _clean(self, text: str) -> str:
        text = re.sub(r"\[!\[.*?\]\(.*?\)\]\(.*?\)", "", text)  # badge links
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)             # images
        text = re.sub(r"\[([^\]]+)\]\(.*?\)", r"\1", text)      # [text](url) → text
        text = re.sub(r"[*_`]", "", text)
        return text.strip()

    def _row_to_job(self, row: dict, section_name: str) -> Job | None:
        # Find apply URL
        apply_cell = row.get("Application") or row.get("Link") or ""
        if ":lock:" in apply_cell or "lock" in apply_cell.lower():
            return None  # closed position

        url = self._extract_url(apply_cell)
        if not url:
            return None

        title = (
            row.get("Role")
            or row.get("Program")
            or row.get("Scholarship")
            or "Unknown Role"
        )
        company = (
            row.get("Company")
            or row.get("Organization")
            or row.get("University/Organization")
            or "Unknown"
        )
        location = row.get("Location", "Unknown")
        date_posted = row.get("Date Posted") or row.get("Deadline", "Unknown")

        return Job(
            id=self._make_id(url),
            title=self._clean(title),
            company=self._clean(company),
            location=self._clean(location),
            description="",
            url=url,
            date_posted=self._clean(date_posted),
            source="github_readme",
            job_type=None,
            category=None,
        )

from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse

_UTM_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}


def _strip_utm(url: str) -> str:
    """Remove UTM tracking params so the same job from different campaign links deduplicates."""
    try:
        parsed = urlparse(url)
        qs = [(k, v) for k, v in parse_qsl(parsed.query) if k.lower() not in _UTM_PARAMS]
        return urlunparse(parsed._replace(query=urlencode(qs)))
    except Exception:
        return url


@dataclass
class Job:
    id: str           # sha256 of normalized URL
    title: str
    company: str
    location: str
    description: str
    url: str
    date_posted: str
    source: str       # "github_readme" | "intern_list" | "newgrad_jobs" | "slack"
    job_type: str | None = None    # "internship" | "full_time"
    category: str | None = None    # one of 5 channel slugs

    def __post_init__(self):
        # Strip UTM tracking params for consistent deduplication
        self.url = _strip_utm(self.url)
        # Truncate description to 300 chars for embed safety
        if len(self.description) > 300:
            self.description = self.description[:297] + "..."

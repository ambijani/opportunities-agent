import hashlib
import re
from abc import ABC, abstractmethod

from database.models import Job


class BaseScraper(ABC):

    @abstractmethod
    def scrape(self) -> list[Job]:
        """Return a list of Jobs from the source."""
        ...

    def _make_id(self, url: str) -> str:
        return hashlib.sha256(self._normalize_url(url).encode()).hexdigest()[:16]

    def _normalize_url(self, url: str) -> str:
        # Strip common tracking params
        url = re.sub(r"[?&](utm_[^&]+|ref=[^&]+|source=[^&]+)", "", url)
        return url.rstrip("/?&")

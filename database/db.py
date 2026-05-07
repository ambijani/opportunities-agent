import hashlib
import logging
from datetime import datetime, timezone

from google.cloud import firestore

logger = logging.getLogger(__name__)

_COLLECTION = "posted_jobs"


def _url_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


class Database:
    def __init__(self, db_path: str = ""):
        # db_path kept for API compatibility but unused — Firestore is serverless
        self._db = firestore.Client()
        self._col = self._db.collection(_COLLECTION)
        logger.debug("Firestore client initialized (collection: %s)", _COLLECTION)

    def has_been_posted(self, url: str) -> bool:
        doc = self._col.document(_url_key(url)).get()
        return doc.exists

    def mark_posted(self, job, channel_id: int) -> None:
        self._col.document(_url_key(job.url)).set(
            {
                "url": job.url,
                "job_id": job.id,
                "title": job.title,
                "company": job.company,
                "channel_id": str(channel_id),
                "job_type": job.job_type,
                "category": job.category,
                "source": job.source,
                "posted_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def stats(self) -> dict:
        docs = self._col.stream()
        total = 0
        by_source: dict[str, int] = {}
        for doc in docs:
            total += 1
            src = doc.get("source") or "unknown"
            by_source[src] = by_source.get(src, 0) + 1
        return {"total": total, "by_source": by_source}

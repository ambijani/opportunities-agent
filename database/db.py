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

    # ── Manual-pick subscriptions ─────────────────────────────────────────────

    def set_subscriber_channels(self, user_id: int, channel_ids: list[int]) -> None:
        """Save (or replace) a user's channel subscription preferences."""
        ref = self._db.collection("manual_subscribers").document(str(user_id))
        ref.set({
            "user_id": str(user_id),
            "channels": [str(c) for c in channel_ids],
            "subscribed_at": datetime.now(timezone.utc).isoformat(),
        })

    def remove_subscriber(self, user_id: int) -> bool:
        """Remove a subscriber. Returns False if wasn't subscribed."""
        ref = self._db.collection("manual_subscribers").document(str(user_id))
        if not ref.get().exists:
            return False
        ref.delete()
        return True

    def get_subscribers_for_channel(self, channel_id: int) -> list[int]:
        """Return user IDs subscribed to a specific channel."""
        docs = (
            self._db.collection("manual_subscribers")
            .where("channels", "array_contains", str(channel_id))
            .stream()
        )
        return [int(doc.get("user_id")) for doc in docs]

    def get_subscriber_channels(self, user_id: int) -> list[str] | None:
        """Return the channel IDs a user is subscribed to, or None if not subscribed."""
        doc = self._db.collection("manual_subscribers").document(str(user_id)).get()
        if not doc.exists:
            return None
        return doc.get("channels") or []

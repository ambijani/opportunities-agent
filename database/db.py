import hashlib
import logging
import os
from datetime import datetime, timezone

import libsql_client

logger = logging.getLogger(__name__)


def _url_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


class Database:
    def __init__(self, db_path: str = ""):
        # db_path accepted for API compatibility but unused — Turso is remote
        self._client = libsql_client.create_client_sync(
            url=os.environ["TURSO_DATABASE_URL"],
            auth_token=os.environ.get("TURSO_AUTH_TOKEN", ""),
        )
        logger.debug("Turso client initialized")

    def has_been_posted(self, url: str) -> bool:
        rs = self._client.execute(
            "SELECT 1 FROM posted_jobs WHERE url_hash = ?", [_url_key(url)]
        )
        return len(rs.rows) > 0

    def filter_new_jobs(self, jobs: list) -> list:
        """Return only jobs not yet posted — batched IN queries instead of one per job."""
        if not jobs:
            return []
        hashes = [_url_key(j.url) for j in jobs]
        already_posted: set[str] = set()
        chunk_size = 500
        for i in range(0, len(hashes), chunk_size):
            chunk = hashes[i:i + chunk_size]
            placeholders = ",".join("?" * len(chunk))
            rs = self._client.execute(
                f"SELECT url_hash FROM posted_jobs WHERE url_hash IN ({placeholders})", chunk
            )
            already_posted.update(row[0] for row in rs.rows)
        return [j for j, h in zip(jobs, hashes) if h not in already_posted]

    def mark_posted(self, job, channel_id: int) -> None:
        self._client.execute(
            "INSERT OR IGNORE INTO posted_jobs VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                _url_key(job.url),
                job.url,
                job.id,
                job.title,
                job.company,
                str(channel_id),
                job.job_type,
                job.category,
                job.source,
                datetime.now(timezone.utc).isoformat(),
            ],
        )

    def stats(self) -> dict:
        rs = self._client.execute(
            "SELECT source, COUNT(*) FROM posted_jobs GROUP BY source"
        )
        by_source = {row[0]: row[1] for row in rs.rows}
        return {"total": sum(by_source.values()), "by_source": by_source}

    # ── Subscriptions ─────────────────────────────────────────────────────────

    def set_subscriber_channels(self, user_id: int, channel_ids: list[int]) -> None:
        uid = str(user_id)
        now = datetime.now(timezone.utc).isoformat()
        stmts = [libsql_client.Statement("DELETE FROM subscribers WHERE user_id = ?", [uid])]
        for cid in channel_ids:
            stmts.append(
                libsql_client.Statement(
                    "INSERT INTO subscribers VALUES (?,?,?)", [uid, str(cid), now]
                )
            )
        self._client.batch(stmts)

    def remove_subscriber(self, user_id: int) -> bool:
        uid = str(user_id)
        # Check existence first (libsql doesn't support RETURNING in all versions)
        rs = self._client.execute(
            "SELECT 1 FROM subscribers WHERE user_id = ?", [uid]
        )
        if len(rs.rows) == 0:
            return False
        self._client.execute("DELETE FROM subscribers WHERE user_id = ?", [uid])
        return True

    def get_subscribers_for_channel(self, channel_id: int) -> list[int]:
        rs = self._client.execute(
            "SELECT user_id FROM subscribers WHERE channel_id = ?", [str(channel_id)]
        )
        return [int(row[0]) for row in rs.rows]

    def close(self) -> None:
        self._client.close()

    def get_subscriber_channels(self, user_id: int) -> list[str] | None:
        rs = self._client.execute(
            "SELECT channel_id FROM subscribers WHERE user_id = ?", [str(user_id)]
        )
        if len(rs.rows) == 0:
            return None
        return [row[0] for row in rs.rows]

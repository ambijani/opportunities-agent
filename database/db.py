import sqlite3
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.db_path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS posted_jobs (
                    url         TEXT PRIMARY KEY,
                    job_id      TEXT NOT NULL,
                    title       TEXT,
                    company     TEXT,
                    channel_id  TEXT,
                    job_type    TEXT,
                    category    TEXT,
                    source      TEXT,
                    posted_at   TEXT NOT NULL
                )
            """)
            conn.commit()
        logger.debug("Database schema initialized at %s", self.db_path)

    def has_been_posted(self, url: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM posted_jobs WHERE url = ?", (url,)
            ).fetchone()
            return row is not None

    def mark_posted(self, job, channel_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO posted_jobs
                    (url, job_id, title, company, channel_id, job_type, category, source, posted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.url,
                    job.id,
                    job.title,
                    job.company,
                    str(channel_id),
                    job.job_type,
                    job.category,
                    job.source,
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()

    def stats(self) -> dict:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM posted_jobs").fetchone()[0]
            by_source = conn.execute(
                "SELECT source, COUNT(*) as cnt FROM posted_jobs GROUP BY source"
            ).fetchall()
            return {
                "total": total,
                "by_source": {r["source"]: r["cnt"] for r in by_source},
            }

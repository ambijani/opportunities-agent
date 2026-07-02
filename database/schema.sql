CREATE TABLE IF NOT EXISTS posted_jobs (
    url_hash   TEXT PRIMARY KEY,  -- sha256(url) hex
    url        TEXT NOT NULL,
    job_id     TEXT,
    title      TEXT,
    company    TEXT,
    channel_id TEXT,
    job_type   TEXT,
    category   TEXT,
    source     TEXT,
    posted_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscribers (
    user_id       TEXT NOT NULL,
    channel_id    TEXT NOT NULL,
    subscribed_at TEXT NOT NULL,
    PRIMARY KEY (user_id, channel_id)
);

CREATE INDEX IF NOT EXISTS idx_subscribers_channel ON subscribers(channel_id);

"""
One-time migration: Google Cloud Firestore → Turso/libSQL.

Prerequisites:
  - GCP Application Default Credentials active (gcloud auth application-default login)
  - TURSO_DATABASE_URL and TURSO_AUTH_TOKEN set in environment
  - Turso schema already applied: turso db shell opportunities-agent < database/schema.sql

Usage:
    TURSO_DATABASE_URL=libsql://... TURSO_AUTH_TOKEN=... python database/migrate_to_turso.py
"""
import hashlib
import os
import sys
from datetime import datetime, timezone

try:
    from google.cloud import firestore
except ImportError:
    print("google-cloud-firestore is required for migration. It may have been removed from requirements.txt.")
    print("Install it temporarily: pip install google-cloud-firestore")
    sys.exit(1)

try:
    import libsql_client
except ImportError:
    print("libsql-client is required. Install it: pip install libsql-client")
    sys.exit(1)


def main() -> None:
    turso_url = os.environ.get("TURSO_DATABASE_URL")
    turso_token = os.environ.get("TURSO_AUTH_TOKEN", "")
    if not turso_url:
        print("TURSO_DATABASE_URL is not set.")
        sys.exit(1)

    print("Connecting to Firestore...")
    fs = firestore.Client()

    print(f"Connecting to Turso: {turso_url}")
    turso = libsql_client.create_client_sync(url=turso_url, auth_token=turso_token)

    # ── Apply schema ──────────────────────────────────────────────────────────
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path) as f:
        for stmt in f.read().split(";"):
            stmt = stmt.strip()
            if stmt:
                turso.execute(stmt)
    print("Schema applied.")

    # ── Migrate posted_jobs ───────────────────────────────────────────────────
    print("Migrating posted_jobs...")
    posted_count = 0
    skipped = 0
    last_doc = None
    PAGE = 100

    while True:
        query = fs.collection("posted_jobs").order_by("__name__").limit(PAGE)
        if last_doc:
            query = query.start_after(last_doc)

        docs = list(query.stream())
        if not docs:
            break

        for doc in docs:
            d = doc.to_dict() or {}
            url_hash = doc.id
            try:
                turso.execute(
                    "INSERT OR IGNORE INTO posted_jobs VALUES (?,?,?,?,?,?,?,?,?,?)",
                    [
                        url_hash,
                        d.get("url", ""),
                        d.get("job_id", ""),
                        d.get("title", ""),
                        d.get("company", ""),
                        d.get("channel_id", ""),
                        d.get("job_type", ""),
                        d.get("category", ""),
                        d.get("source", ""),
                        d.get("posted_at", datetime.now(timezone.utc).isoformat()),
                    ],
                )
                posted_count += 1
            except Exception as e:
                print(f"  Warning: skipped doc {doc.id}: {e}")
                skipped += 1

        last_doc = docs[-1]
        print(f"  {posted_count} posted_jobs migrated...")

    print(f"posted_jobs: {posted_count} migrated, {skipped} skipped.")

    # ── Migrate subscribers ───────────────────────────────────────────────────
    print("Migrating manual_subscribers...")
    sub_count = 0
    for doc in fs.collection("manual_subscribers").stream():
        d = doc.to_dict() or {}
        user_id = str(d.get("user_id", doc.id))
        channels = d.get("channels", [])
        subscribed_at = d.get("subscribed_at", datetime.now(timezone.utc).isoformat())

        stmts = [
            libsql_client.Statement(
                "INSERT OR IGNORE INTO subscribers VALUES (?,?,?)",
                [user_id, str(cid), subscribed_at],
            )
            for cid in channels
        ]
        if stmts:
            turso.batch(stmts)
        sub_count += 1

    print(f"subscribers: {sub_count} users migrated.")

    # ── Verify ────────────────────────────────────────────────────────────────
    rs = turso.execute("SELECT COUNT(*) FROM posted_jobs")
    print(f"\nVerification — posted_jobs rows in Turso: {rs.rows[0][0]}")
    rs = turso.execute("SELECT COUNT(DISTINCT user_id) FROM subscribers")
    print(f"Verification — subscriber users in Turso: {rs.rows[0][0]}")
    print("\nMigration complete.")


if __name__ == "__main__":
    main()

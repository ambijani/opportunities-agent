import os
import logging
from dotenv import load_dotenv

load_dotenv()

# ─── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ─── Anthropic ────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ─── Discord ──────────────────────────────────────────────────────────────────
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

# Category slugs (must match channel names)
CATEGORIES = [
    "cs-engineering-tech",
    "business-finance-banking",
    "consulting",
    "humanities-healthcare-medicine",
    "programs",
    "scholarships",
]

JOB_TYPES = ["internship", "full_time"]

# Maps (job_type, category) → Discord channel ID
_SCHOLARSHIPS_CHANNEL_ID = int(os.getenv("DISCORD_SCHOLARSHIPS_CHANNEL_ID", "0"))

CHANNEL_MAP: dict[tuple[str, str], int] = {
    ("internship", "programs"):                       int(os.getenv("DISCORD_INTERN_PROGRAMS_CHANNEL_ID", "0")),
    ("internship", "cs-engineering-tech"):            int(os.getenv("DISCORD_INTERN_CS_ENGINEERING_CHANNEL_ID", "0")),
    ("internship", "business-finance-banking"):       int(os.getenv("DISCORD_INTERN_BUSINESS_FINANCE_CHANNEL_ID", "0")),
    ("internship", "consulting"):                     int(os.getenv("DISCORD_INTERN_CONSULTING_CHANNEL_ID", "0")),
    ("internship", "humanities-healthcare-medicine"): int(os.getenv("DISCORD_INTERN_HUMANITIES_HEALTHCARE_CHANNEL_ID", "0")),
    ("internship", "scholarships"):                   _SCHOLARSHIPS_CHANNEL_ID,
    ("full_time", "programs"):                        int(os.getenv("DISCORD_FT_PROGRAMS_CHANNEL_ID", "0")),
    ("full_time", "cs-engineering-tech"):             int(os.getenv("DISCORD_FT_CS_ENGINEERING_CHANNEL_ID", "0")),
    ("full_time", "business-finance-banking"):        int(os.getenv("DISCORD_FT_BUSINESS_FINANCE_CHANNEL_ID", "0")),
    ("full_time", "consulting"):                      int(os.getenv("DISCORD_FT_CONSULTING_CHANNEL_ID", "0")),
    ("full_time", "humanities-healthcare-medicine"):  int(os.getenv("DISCORD_FT_HUMANITIES_HEALTHCARE_CHANNEL_ID", "0")),
    ("full_time", "scholarships"):                    _SCHOLARSHIPS_CHANNEL_ID,
}

# Maps channel_id → Discord webhook URL (used by WebhookPoster in GHA pipeline)
WEBHOOK_MAP: dict[int, str] = {
    int(os.getenv("DISCORD_INTERN_CS_ENGINEERING_CHANNEL_ID", "0")):        os.getenv("DISCORD_WEBHOOK_INTERN_CS_ENGINEERING", ""),
    int(os.getenv("DISCORD_INTERN_BUSINESS_FINANCE_CHANNEL_ID", "0")):      os.getenv("DISCORD_WEBHOOK_INTERN_BUSINESS_FINANCE", ""),
    int(os.getenv("DISCORD_INTERN_CONSULTING_CHANNEL_ID", "0")):             os.getenv("DISCORD_WEBHOOK_INTERN_CONSULTING", ""),
    int(os.getenv("DISCORD_INTERN_HUMANITIES_HEALTHCARE_CHANNEL_ID", "0")): os.getenv("DISCORD_WEBHOOK_INTERN_HUMANITIES", ""),
    int(os.getenv("DISCORD_INTERN_PROGRAMS_CHANNEL_ID", "0")):               os.getenv("DISCORD_WEBHOOK_INTERN_PROGRAMS", ""),
    int(os.getenv("DISCORD_FT_CS_ENGINEERING_CHANNEL_ID", "0")):             os.getenv("DISCORD_WEBHOOK_FT_CS_ENGINEERING", ""),
    int(os.getenv("DISCORD_FT_BUSINESS_FINANCE_CHANNEL_ID", "0")):           os.getenv("DISCORD_WEBHOOK_FT_BUSINESS_FINANCE", ""),
    int(os.getenv("DISCORD_FT_CONSULTING_CHANNEL_ID", "0")):                 os.getenv("DISCORD_WEBHOOK_FT_CONSULTING", ""),
    int(os.getenv("DISCORD_FT_HUMANITIES_HEALTHCARE_CHANNEL_ID", "0")):      os.getenv("DISCORD_WEBHOOK_FT_HUMANITIES", ""),
    int(os.getenv("DISCORD_FT_PROGRAMS_CHANNEL_ID", "0")):                   os.getenv("DISCORD_WEBHOOK_FT_PROGRAMS", ""),
    _SCHOLARSHIPS_CHANNEL_ID:                                                 os.getenv("DISCORD_WEBHOOK_SCHOLARSHIPS", ""),
}

# ─── Turso ────────────────────────────────────────────────────────────────────
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL", "")
TURSO_AUTH_TOKEN   = os.getenv("TURSO_AUTH_TOKEN", "")

# ─── Category colors for Discord embeds ───────────────────────────────────────
CATEGORY_COLORS: dict[str, int] = {
    "cs-engineering-tech":            0x5865F2,  # Electric blue
    "business-finance-banking":       0xF0B429,  # Gold
    "consulting":                     0x2D9B27,  # Forest green
    "humanities-healthcare-medicine": 0xED4245,  # Warm red
    "programs":                       0x9B59B6,  # Purple
    "scholarships":                   0xE67E22,  # Orange
}

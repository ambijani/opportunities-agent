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
]

JOB_TYPES = ["internship", "full_time"]

# Maps (job_type, category) → Discord channel ID
CHANNEL_MAP: dict[tuple[str, str], int] = {
    ("internship", "programs"):                    int(os.getenv("DISCORD_INTERN_PROGRAMS_CHANNEL_ID", "0")),
    ("internship", "cs-engineering-tech"):         int(os.getenv("DISCORD_INTERN_CS_ENGINEERING_CHANNEL_ID", "0")),
    ("internship", "business-finance-banking"):    int(os.getenv("DISCORD_INTERN_BUSINESS_FINANCE_CHANNEL_ID", "0")),
    ("internship", "consulting"):                  int(os.getenv("DISCORD_INTERN_CONSULTING_CHANNEL_ID", "0")),
    ("internship", "humanities-healthcare-medicine"): int(os.getenv("DISCORD_INTERN_HUMANITIES_HEALTHCARE_CHANNEL_ID", "0")),
    ("full_time", "programs"):                     int(os.getenv("DISCORD_FT_PROGRAMS_CHANNEL_ID", "0")),
    ("full_time", "cs-engineering-tech"):          int(os.getenv("DISCORD_FT_CS_ENGINEERING_CHANNEL_ID", "0")),
    ("full_time", "business-finance-banking"):     int(os.getenv("DISCORD_FT_BUSINESS_FINANCE_CHANNEL_ID", "0")),
    ("full_time", "consulting"):                   int(os.getenv("DISCORD_FT_CONSULTING_CHANNEL_ID", "0")),
    ("full_time", "humanities-healthcare-medicine"): int(os.getenv("DISCORD_FT_HUMANITIES_HEALTHCARE_CHANNEL_ID", "0")),
}

# ─── Slack ────────────────────────────────────────────────────────────────────
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID", "")

# ─── Scheduler ────────────────────────────────────────────────────────────────
SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "19"))
SCHEDULE_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "0"))
SCHEDULE_TIMEZONE = os.getenv("SCHEDULE_TIMEZONE", "America/Chicago")

# ─── Database ─────────────────────────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "./data/opportunities.db")

# ─── Category colors for Discord embeds ───────────────────────────────────────
CATEGORY_COLORS: dict[str, int] = {
    "cs-engineering-tech":          0x5865F2,   # Electric blue
    "business-finance-banking":     0xF0B429,   # Gold
    "consulting":                   0x2D9B27,   # Forest green
    "humanities-healthcare-medicine": 0xED4245, # Warm red
    "programs":                     0x9B59B6,   # Purple
}

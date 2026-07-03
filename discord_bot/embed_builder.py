from datetime import datetime, timezone
import config
from database.models import Job
from pipeline.link_validator import is_email

CATEGORY_DISPLAY = {
    "cs-engineering-tech":            "CS / Engineering / Tech",
    "business-finance-banking":       "Business / Finance / Banking",
    "consulting":                     "Consulting",
    "humanities-healthcare-medicine": "Humanities / Healthcare / Medicine",
    "programs":                       "Fellowships & Programs",
    "scholarships":                   "Scholarships",
}

TYPE_LABEL = {
    "internship": "[Internship]",
    "full_time":  "[Full-Time]",
}

SOURCE_DISPLAY = {
    "github_readme": "GitHub (underclassmen-opportunities)",
    "intern_list":   "intern-list.com",
    "newgrad_jobs":  "newgrad-jobs.com",
    "slack":         "Slack",
    "manual":        "Manual submission",
}

_EMBED_TOTAL_LIMIT = 5900  # Discord max is 6000; leave headroom


def _t(s: str | None, limit: int) -> str:
    s = (s or "").strip()
    return s[:limit - 3] + "..." if len(s) > limit else s or "Unknown"


def build_embed(job: Job) -> dict:
    """Returns a Discord embed as a plain dict (compatible with webhook and REST API payloads)."""
    is_manual = job.source == "manual"
    color     = 0xF39C12 if is_manual else config.CATEGORY_COLORS.get(job.category or "programs", 0x9B59B6)
    type_label = TYPE_LABEL.get(job.job_type or "internship", "")
    cat_label  = CATEGORY_DISPLAY.get(job.category or "programs", "Programs & Fellowships")
    src_label  = SOURCE_DISPLAY.get(job.source, job.source)

    title = f"{'📌 ' if is_manual else ''}{type_label}  {_t(job.title, 200)} — {_t(job.company, 100)}"
    title = title[:256]

    company   = _t(job.company, 100)
    location  = _t(job.location, 100)
    date      = _t(job.date_posted, 50)
    desc      = _t(job.description, 200) if job.description else None
    footer    = f"Source: {src_label}  •  {cat_label}"
    is_email_url = is_email(job.url)
    apply_url = f"mailto:{job.url.removeprefix('mailto:')}" if is_email_url else job.url
    apply_val = f"Email {job.url} to apply" if is_email_url else f"[Click here to apply]({apply_url})"

    fields = [
        {"name": "Company",     "value": company,  "inline": True},
        {"name": "Location",    "value": location, "inline": True},
        {"name": "Date Posted", "value": date,     "inline": True},
    ]
    if desc:
        fields.append({"name": "Description", "value": desc, "inline": False})
    fields.append({"name": "Apply", "value": apply_val, "inline": False})

    # Guard: ensure total character count stays under Discord's 6000 limit
    total = len(title) + len(footer) + sum(len(f["name"]) + len(f["value"]) for f in fields)
    if total > _EMBED_TOTAL_LIMIT and desc:
        # Trim description further until we're under the limit
        trim = len(desc) - (total - _EMBED_TOTAL_LIMIT) - 3
        if trim > 0:
            fields[-2]["value"] = desc[:trim] + "..."
        else:
            fields = [f for f in fields if f["name"] != "Description"]

    embed: dict = {
        "title":     title,
        "color":     color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fields":    fields,
        "footer":    {"text": footer},
    }
    # Discord only hyperlinks the title for http(s) urls — omit it for mailto links.
    if not is_email_url:
        embed["url"] = apply_url
    if is_manual:
        embed["author"] = {"name": "✋ Manually Submitted Opportunity"}

    return embed

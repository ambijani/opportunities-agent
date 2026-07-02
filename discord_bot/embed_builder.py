from datetime import datetime, timezone
import config
from database.models import Job

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


def build_embed(job: Job) -> dict:
    """Returns a Discord embed as a plain dict (compatible with webhook and REST API payloads)."""
    is_manual = job.source == "manual"
    color = 0xF39C12 if is_manual else config.CATEGORY_COLORS.get(job.category or "programs", 0x9B59B6)
    type_label  = TYPE_LABEL.get(job.job_type or "internship", "")
    cat_label   = CATEGORY_DISPLAY.get(job.category or "programs", "Programs & Fellowships")
    src_label   = SOURCE_DISPLAY.get(job.source, job.source)

    title = f"{'📌 ' if is_manual else ''}{type_label}  {job.title} — {job.company}"

    fields = [
        {"name": "Company",     "value": (job.company    or "Unknown")[:1024], "inline": True},
        {"name": "Location",    "value": (job.location   or "Unknown")[:1024], "inline": True},
        {"name": "Date Posted", "value": (job.date_posted or "Unknown")[:1024], "inline": True},
    ]
    if job.description:
        fields.append({"name": "Description", "value": job.description[:1024], "inline": False})
    fields.append({"name": "Apply", "value": f"[Click here to apply]({job.url})", "inline": False})

    embed: dict = {
        "title":     title[:256],
        "url":       job.url,
        "color":     color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fields":    fields,
        "footer":    {"text": f"Source: {src_label}  •  {cat_label}"},
    }
    if is_manual:
        embed["author"] = {"name": "✋ Manually Submitted Opportunity"}

    return embed

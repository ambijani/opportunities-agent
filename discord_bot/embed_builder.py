from datetime import datetime, timezone
import discord
import config
from database.models import Job

CATEGORY_DISPLAY = {
    "cs-engineering-tech":          "CS / Engineering / Tech",
    "business-finance-banking":     "Business / Finance / Banking",
    "consulting":                   "Consulting",
    "humanities-healthcare-medicine": "Humanities / Healthcare / Medicine",
    "programs":                     "Fellowships & Programs",
    "scholarships":                 "Scholarships",
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


def build_embed(job: Job) -> discord.Embed:
    is_manual = job.source == "manual"
    color = 0xF39C12 if is_manual else config.CATEGORY_COLORS.get(job.category or "programs", 0x9B59B6)
    type_label = TYPE_LABEL.get(job.job_type or "internship", "")
    category_label = CATEGORY_DISPLAY.get(job.category or "programs", "Programs & Fellowships")
    source_label = SOURCE_DISPLAY.get(job.source, job.source)

    title = f"{'📌 ' if is_manual else ''}{type_label}  {job.title} — {job.company}"
    embed = discord.Embed(
        title=title,
        url=job.url,
        color=color,
        timestamp=datetime.now(timezone.utc),
    )

    if is_manual:
        embed.set_author(name="✋ Manually Submitted Opportunity")

    embed.add_field(name="Company",      value=(job.company or "Unknown")[:1024],    inline=True)
    embed.add_field(name="Location",     value=(job.location or "Unknown")[:1024],   inline=True)
    embed.add_field(name="Date Posted",  value=(job.date_posted or "Unknown")[:1024], inline=True)

    if job.description:
        embed.add_field(name="Description", value=job.description[:1024], inline=False)

    embed.add_field(
        name="Apply",
        value=f"[Click here to apply]({job.url})",
        inline=False,
    )

    footer = f"Source: {source_label}  •  {category_label}"
    embed.set_footer(text=footer)

    return embed

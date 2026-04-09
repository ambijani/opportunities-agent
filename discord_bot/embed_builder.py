from datetime import datetime
import discord
import config
from database.models import Job

CATEGORY_DISPLAY = {
    "cs-engineering-tech":          "CS / Engineering / Tech",
    "business-finance-banking":     "Business / Finance / Banking",
    "consulting":                   "Consulting",
    "humanities-healthcare-medicine": "Humanities / Healthcare / Medicine",
    "programs":                     "Programs & Fellowships",
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
}


def build_embed(job: Job) -> discord.Embed:
    color = config.CATEGORY_COLORS.get(job.category or "programs", 0x9B59B6)
    type_label = TYPE_LABEL.get(job.job_type or "internship", "")
    category_label = CATEGORY_DISPLAY.get(job.category or "programs", "Programs & Fellowships")
    source_label = SOURCE_DISPLAY.get(job.source, job.source)

    embed = discord.Embed(
        title=f"{type_label}  {job.title} — {job.company}",
        url=job.url,
        color=color,
        timestamp=datetime.utcnow(),
    )

    embed.add_field(name="Company",      value=job.company or "Unknown",  inline=True)
    embed.add_field(name="Location",     value=job.location or "Unknown", inline=True)
    embed.add_field(name="Date Posted",  value=job.date_posted or "Unknown", inline=True)

    if job.description:
        embed.add_field(name="Description", value=job.description, inline=False)

    embed.add_field(
        name="Apply",
        value=f"[Click here to apply]({job.url})",
        inline=False,
    )

    embed.set_footer(text=f"Source: {source_label}  •  {category_label}")

    return embed

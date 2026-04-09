from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Job:
    id: str           # sha256 of normalized URL
    title: str
    company: str
    location: str
    description: str
    url: str
    date_posted: str
    source: str       # "github_readme" | "intern_list" | "newgrad_jobs" | "slack"
    job_type: str | None = None    # "internship" | "full_time"
    category: str | None = None    # one of 5 channel slugs

    def __post_init__(self):
        # Truncate description to 300 chars for embed safety
        if len(self.description) > 300:
            self.description = self.description[:297] + "..."

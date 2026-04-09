"""
Claude-based classifier for jobs that keyword_filter couldn't confidently classify.
Only called when job_type or category is still None after the keyword pass.
"""
import json
import logging

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

import config
from database.models import Job

logger = logging.getLogger(__name__)

CATEGORIES = [
    "cs-engineering-tech",
    "business-finance-banking",
    "consulting",
    "humanities-healthcare-medicine",
    "programs",
]

SYSTEM_PROMPT = """You are a job classification assistant. Given a job posting, you output a JSON object with two fields:
- "job_type": either "internship" or "full_time"
- "category": one of exactly these five strings:
    - "cs-engineering-tech"
    - "business-finance-banking"
    - "consulting"
    - "humanities-healthcare-medicine"
    - "programs"

Rules:
- If the role is for students/undergrads/summer, it's "internship". Otherwise "full_time".
- "programs" is for fellowships, scholarships, rotational programs, and diversity initiatives.
- If uncertain about category, pick the closest match — never return null.
- Respond with ONLY the JSON object, no explanation."""

USER_TEMPLATE = """Title: {title}
Company: {company}
Location: {location}
Description: {description}
Source: {source}"""


class ClaudeClassifier:
    def __init__(self):
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=False,
    )
    def classify(self, job: Job) -> Job:
        """
        Fills in job.job_type and/or job.category using Claude.
        Only sends fields that are still None.
        """
        if job.job_type is not None and job.category is not None:
            return job  # already fully classified

        user_message = USER_TEMPLATE.format(
            title=job.title,
            company=job.company,
            location=job.location,
            description=job.description[:300],
            source=job.source,
        )

        try:
            response = self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            raw = response.content[0].text.strip()
            result = json.loads(raw)

            if job.job_type is None:
                job_type = result.get("job_type", "").lower()
                if job_type in ("internship", "full_time"):
                    job.job_type = job_type

            if job.category is None:
                category = result.get("category", "").lower()
                if category in CATEGORIES:
                    job.category = category

        except (json.JSONDecodeError, KeyError, IndexError, anthropic.APIError) as e:
            logger.warning("Claude classification failed for '%s': %s", job.title, e)

        # Hard fallbacks — never leave None
        if job.job_type is None:
            job.job_type = "internship"
        if job.category is None:
            job.category = "programs"

        return job

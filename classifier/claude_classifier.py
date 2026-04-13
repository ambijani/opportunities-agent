"""
Claude-based classifier for jobs that keyword_filter couldn't confidently classify.
Batches multiple jobs into a single API call to avoid sequential slowness.
"""
import json
import logging
import re
import asyncio

import anthropic

import config
from database.models import Job

logger = logging.getLogger(__name__)

CATEGORIES = [
    "cs-engineering-tech",
    "business-finance-banking",
    "consulting",
    "humanities-healthcare-medicine",
    "programs",
    "scholarships",
]

# How many jobs to classify per API call
BATCH_SIZE = 20

SYSTEM_PROMPT = """\
You are a job classification assistant. You will receive a JSON array of job postings.
For each one, return a JSON array (same order) where each element has exactly:
  - "job_type": "internship" or "full_time"
  - "category": one of these six exact strings:
      "cs-engineering-tech"
      "business-finance-banking"
      "consulting"
      "humanities-healthcare-medicine"
      "programs"
      "scholarships"

Category rules (apply top-to-bottom; first match wins):
- "scholarships": financial awards only — scholarships, grants, bursaries, tuition assistance, academic awards. NOT paid internships or programs that mention funding.
- "programs": fellowships, rotational programs, diversity initiatives, hackathons, summits, leadership development programs, short cohort programs. NOT regular internships or full-time jobs.
- "consulting": consulting, advisory, or strategy consulting roles; includes big-4 and MBB firms (McKinsey, Bain, BCG, Deloitte, Accenture, KPMG, PwC, EY).
- "cs-engineering-tech": SWE/SDE, data analyst, data engineer, data scientist, machine learning/AI/deep learning/NLP, product management, engineering & development (hardware, firmware, electrical, mechanical, robotics, aerospace, R&D), cybersecurity/infosec, DevOps, cloud, IT, QA.
- "business-finance-banking": marketing, business analyst, accounting & finance, banking, investment banking, private equity, management & executive, sales, project management, supply chain/logistics/procurement, operations.
- "humanities-healthcare-medicine": creative & design, human resources/HR/recruiting, arts & entertainment, customer service & support, legal & compliance, public sector & government, education & training, healthcare/medicine/clinical/nursing.
- If uncertain, pick the closest match — never omit a result.
- Return ONLY the JSON array, no explanation, no markdown fences."""


class ClaudeClassifier:
    def __init__(self):
        self._client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

    async def classify_batch(self, jobs: list[Job]) -> list[Job]:
        """
        Classify jobs in batches, paced to stay under the 10k output tokens/min limit.
        Each batch of 20 jobs produces ~500 tokens → max 20 batches/min → 1 per 3 seconds.
        Sequential + sleep is more efficient than concurrent + retries at this tier.
        """
        chunks = [jobs[i:i + BATCH_SIZE] for i in range(0, len(jobs), BATCH_SIZE)]
        results: list[list[Job]] = []
        for i, chunk in enumerate(chunks):
            if i > 0:
                await asyncio.sleep(3)  # pace to ~20 batches/min (10k token limit)
            results.append(await self._classify_chunk(chunk))
        return [job for chunk_result in results for job in chunk_result]

    async def classify(self, job: Job) -> Job:
        """Classify a single job (convenience wrapper)."""
        results = await self.classify_batch([job])
        return results[0]

    async def _classify_chunk(self, jobs: list[Job]) -> list[Job]:
        payload = [
            {
                "index": i,
                "title": job.title,
                "company": job.company,
                "description": job.description[:200],
                "source": job.source,
            }
            for i, job in enumerate(jobs)
        ]

        for attempt in range(3):
            try:
                response = await self._client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=BATCH_SIZE * 30,  # ~30 tokens per job result
                    system=SYSTEM_PROMPT,
                    messages=[{
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    }],
                )
                raw = response.content[0].text.strip()
                logger.debug("Claude raw response (batch of %d): %r", len(jobs), raw[:300])

                # Strip markdown fences if present
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)
                raw = raw.strip()

                results = json.loads(raw)
                if not isinstance(results, list) or len(results) != len(jobs):
                    raise ValueError(
                        f"Expected list of {len(jobs)}, got {type(results).__name__} "
                        f"of length {len(results) if isinstance(results, list) else '?'}"
                    )

                for job, result in zip(jobs, results):
                    jt = str(result.get("job_type", "")).lower()
                    cat = str(result.get("category", "")).lower()
                    if job.job_type is None:
                        job.job_type = jt if jt in ("internship", "full_time") else "internship"
                    if job.category is None:
                        job.category = cat if cat in CATEGORIES else "programs"

                return jobs

            except Exception as e:
                logger.warning(
                    "Claude batch attempt %d/%d failed: %s", attempt + 1, 3, e
                )
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)

        # Fallback: apply defaults for anything still unclassified
        logger.warning("All Claude attempts failed — applying fallback defaults to batch of %d", len(jobs))
        for job in jobs:
            if job.job_type is None:
                job.job_type = "internship"
            if job.category is None:
                job.category = "programs"
        return jobs

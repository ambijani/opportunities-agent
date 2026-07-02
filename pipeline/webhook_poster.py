"""
Posts job embeds to Discord channels via webhook URLs.
Replaces OpportunitiesBot.post_jobs for the stateless GHA pipeline.
"""
import logging
import time

import requests

from database.models import Job
from discord_bot.embed_builder import build_embed

logger = logging.getLogger(__name__)

POST_DELAY = 0.6       # seconds between requests (Discord rate limit headroom)
EMBEDS_PER_BATCH = 10  # Discord webhook max embeds per message


class WebhookPoster:
    def __init__(self, webhook_map: dict[int, str]):
        """webhook_map: channel_id → webhook URL"""
        self._webhooks = webhook_map

    def post_jobs(self, channel_id: int, jobs: list[Job]) -> list[Job]:
        """
        POST embeds to the webhook URL for channel_id.
        Returns the jobs that were successfully posted.
        Mirrors the batching behaviour from bot.py: ≤10 jobs per message.
        """
        if not jobs:
            return []

        webhook_url = self._webhooks.get(channel_id)
        if not webhook_url:
            logger.warning("No webhook configured for channel %s — skipping %d jobs", channel_id, len(jobs))
            return []

        posted: list[Job] = []
        batches = [jobs[i:i + EMBEDS_PER_BATCH] for i in range(0, len(jobs), EMBEDS_PER_BATCH)]

        for batch in batches:
            embeds = [build_embed(job) for job in batch]
            try:
                resp = requests.post(
                    webhook_url,
                    json={"embeds": embeds},
                    timeout=15,
                )
                if resp.status_code in (200, 204):
                    posted.extend(batch)
                elif resp.status_code == 429:
                    retry_after = resp.json().get("retry_after", 1)
                    logger.warning("Webhook rate-limited; sleeping %.1fs", retry_after)
                    time.sleep(retry_after)
                    # Retry once
                    resp = requests.post(webhook_url, json={"embeds": embeds}, timeout=15)
                    if resp.status_code in (200, 204):
                        posted.extend(batch)
                    else:
                        logger.error("Webhook retry failed for channel %s: HTTP %s", channel_id, resp.status_code)
                else:
                    logger.error("Webhook error for channel %s: HTTP %s — %s", channel_id, resp.status_code, resp.text[:200])
            except requests.RequestException as e:
                logger.error("Webhook request failed for channel %s: %s", channel_id, e)

            time.sleep(POST_DELAY)

        return posted

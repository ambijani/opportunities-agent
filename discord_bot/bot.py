import asyncio
import logging

import discord

import config
from database.models import Job
from .embed_builder import build_embed

logger = logging.getLogger(__name__)

# Seconds between messages to stay under Discord's 5 msg/5s rate limit
POST_DELAY = 0.6

# If a channel has more than this many new jobs, batch them 10 per message
BATCH_THRESHOLD = 10
EMBEDS_PER_MESSAGE = 10


class OpportunitiesBot:
    def __init__(self):
        intents = discord.Intents.default()
        self._client = discord.Client(intents=intents)
        self._ready = asyncio.Event()

        @self._client.event
        async def on_ready():
            logger.info("Discord bot logged in as %s", self._client.user)
            self._ready.set()

    async def start(self):
        """Connect to Discord (non-blocking; call once at startup)."""
        asyncio.create_task(self._client.start(config.DISCORD_BOT_TOKEN))
        await asyncio.wait_for(self._ready.wait(), timeout=30)

    async def close(self):
        await self._client.close()

    async def _get_channel(self, channel_id: int):
        channel = self._client.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self._client.fetch_channel(channel_id)
            except discord.NotFound:
                logger.error("Channel %s not found. Check your channel IDs.", channel_id)
                return None
        return channel

    async def post_jobs(self, jobs: list[Job]) -> list[Job]:
        """
        Post a list of jobs, all destined for the same channel.
        - ≤ BATCH_THRESHOLD jobs → one embed per message (more visible).
        - > BATCH_THRESHOLD jobs → up to EMBEDS_PER_MESSAGE embeds per message (less spam).
        Returns the jobs that were successfully posted.
        """
        if not jobs:
            return []

        key = (jobs[0].job_type or "internship", jobs[0].category or "programs")
        channel_id = config.CHANNEL_MAP.get(key)
        if not channel_id:
            logger.warning("No channel configured for %s — skipping %d jobs", key, len(jobs))
            return []

        channel = await self._get_channel(channel_id)
        if channel is None:
            return []

        posted: list[Job] = []

        if len(jobs) <= BATCH_THRESHOLD:
            # Individual embeds
            for job in jobs:
                try:
                    await channel.send(embed=build_embed(job))
                    await asyncio.sleep(POST_DELAY)
                    posted.append(job)
                except discord.Forbidden:
                    logger.error("No permission to post in channel %s", channel_id)
                    break
                except discord.HTTPException as e:
                    logger.error("Discord HTTP error posting to %s: %s", channel_id, e)
        else:
            # Batched embeds — up to 10 per message
            for i in range(0, len(jobs), EMBEDS_PER_MESSAGE):
                batch = jobs[i:i + EMBEDS_PER_MESSAGE]
                embeds = [build_embed(job) for job in batch]
                try:
                    await channel.send(embeds=embeds)
                    await asyncio.sleep(POST_DELAY)
                    posted.extend(batch)
                except discord.Forbidden:
                    logger.error("No permission to post in channel %s", channel_id)
                    break
                except discord.HTTPException as e:
                    logger.error("Discord HTTP error posting to %s: %s", channel_id, e)

        return posted

    async def post_job(self, job: Job) -> int | None:
        """Single-job convenience wrapper (used by runner for DB tracking)."""
        posted = await self.post_jobs([job])
        if posted:
            key = (job.job_type or "internship", job.category or "programs")
            return config.CHANNEL_MAP.get(key)
        return None

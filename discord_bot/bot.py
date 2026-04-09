import asyncio
import logging

import discord

import config
from database.models import Job
from .embed_builder import build_embed

logger = logging.getLogger(__name__)

# Seconds between posts to stay under Discord's 5 msg/5s rate limit
POST_DELAY = 0.6


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

    async def post_job(self, job: Job) -> int | None:
        """
        Posts a job embed to the correct channel.
        Returns the channel_id on success, None on failure.
        """
        key = (job.job_type or "internship", job.category or "programs")
        channel_id = config.CHANNEL_MAP.get(key)

        if not channel_id:
            logger.warning("No channel configured for key %s — skipping '%s'", key, job.title)
            return None

        channel = self._client.get_channel(channel_id)
        if channel is None:
            # fetch_channel for channels not in cache
            try:
                channel = await self._client.fetch_channel(channel_id)
            except discord.NotFound:
                logger.error("Channel %s not found. Check your channel IDs.", channel_id)
                return None

        embed = build_embed(job)
        try:
            await channel.send(embed=embed)
            await asyncio.sleep(POST_DELAY)
            return channel_id
        except discord.Forbidden:
            logger.error("No permission to post in channel %s", channel_id)
        except discord.HTTPException as e:
            logger.error("Discord HTTP error posting to %s: %s", channel_id, e)

        return None

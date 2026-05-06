import asyncio
import hashlib
import logging
from datetime import datetime, timezone

import discord
from discord import app_commands

import config
from classifier import keyword_filter
from classifier.claude_classifier import ClaudeClassifier
from database.models import Job
from pipeline.link_validator import _check_url

logger = logging.getLogger(__name__)


class AddJobModal(discord.ui.Modal, title="Add Opportunity"):
    url = discord.ui.TextInput(
        label="URL",
        placeholder="https://...",
        required=True,
        max_length=500,
    )
    job_title = discord.ui.TextInput(
        label="Title",
        placeholder="Software Engineer Intern",
        required=True,
        max_length=200,
    )
    company = discord.ui.TextInput(
        label="Company",
        placeholder="Acme Corp",
        required=True,
        max_length=200,
    )
    location = discord.ui.TextInput(
        label="Location (optional)",
        placeholder="Remote / New York, NY",
        required=False,
        max_length=200,
    )
    description = discord.ui.TextInput(
        label="Description (optional)",
        placeholder="Brief description of the role...",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=300,
    )

    def __init__(self, bot, db):
        super().__init__()
        self._bot = bot
        self._db = db

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        raw_url = self.url.value.strip()

        if self._db.has_been_posted(raw_url):
            await interaction.followup.send(
                "This URL has already been posted.", ephemeral=True
            )
            return

        job = Job(
            id=hashlib.sha256(raw_url.encode()).hexdigest()[:16],
            title=self.job_title.value.strip(),
            company=self.company.value.strip(),
            location=self.location.value.strip() or "Not specified",
            description=self.description.value.strip() or "",
            url=raw_url,
            date_posted=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            source="manual",
        )

        # Classify — keywords first, Claude for anything ambiguous
        keyword_filter.classify(job)
        if job.job_type is None or job.category is None:
            try:
                job = (await ClaudeClassifier().classify_batch([job]))[0]
            except Exception as e:
                logger.warning("Claude classification failed for manual job: %s", e)
                job.job_type = job.job_type or "internship"
                job.category = job.category or "programs"

        # Validate the link is reachable
        loop = asyncio.get_running_loop()
        _, valid, reason = await loop.run_in_executor(None, _check_url, job.url)
        if not valid:
            await interaction.followup.send(
                f"URL check failed: {reason}\nDouble-check the link and try again.",
                ephemeral=True,
            )
            return

        # Resolve Discord channel
        channel_id = config.CHANNEL_MAP.get((job.job_type, job.category))
        if not channel_id:
            await interaction.followup.send(
                f"No channel configured for `{job.job_type}` / `{job.category}`.",
                ephemeral=True,
            )
            return

        # Post and record
        posted = await self._bot.post_jobs(channel_id, [job])
        if not posted:
            await interaction.followup.send(
                "Failed to post — check bot permissions in the target channel.",
                ephemeral=True,
            )
            return

        self._db.mark_posted(job, channel_id)

        channel = self._bot._client.get_channel(channel_id)
        mention = channel.mention if channel else f"<#{channel_id}>"

        await interaction.followup.send(
            f"Posted **{job.title}** at **{job.company}** → {mention} "
            f"(`{job.job_type}` / `{job.category}`).",
            ephemeral=True,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error("Error in AddJobModal: %s", error, exc_info=True)
        try:
            await interaction.followup.send(
                "Something went wrong. Check the bot logs.", ephemeral=True
            )
        except Exception:
            pass


def register(tree: app_commands.CommandTree, bot, db) -> None:
    @tree.command(
        name="add-job",
        description="Manually add an opportunity and post it immediately",
    )
    async def add_job(interaction: discord.Interaction):
        await interaction.response.send_modal(AddJobModal(bot, db))

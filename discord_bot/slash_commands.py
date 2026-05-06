import asyncio
import hashlib
import logging
from datetime import datetime, timezone

import discord
from discord import app_commands

import config
from database.models import Job
from pipeline.link_validator import _check_url

logger = logging.getLogger(__name__)

# Human-readable labels for channel map keys
_TYPE_LABEL = {"internship": "Internship", "full_time": "Full-time"}
_CAT_LABEL = {
    "cs-engineering-tech":            "CS / Engineering / Tech",
    "business-finance-banking":       "Business / Finance / Banking",
    "consulting":                     "Consulting",
    "humanities-healthcare-medicine": "Humanities / Healthcare / Medicine",
    "programs":                       "Programs",
    "scholarships":                   "Scholarships",
}


def _channel_options() -> list[discord.SelectOption]:
    seen = set()
    options = []
    for (job_type, category), channel_id in config.CHANNEL_MAP.items():
        if not channel_id or channel_id in seen:
            continue
        seen.add(channel_id)
        label = f"{_TYPE_LABEL.get(job_type, job_type)} · {_CAT_LABEL.get(category, category)}"
        options.append(discord.SelectOption(
            label=label,
            value=f"{job_type}|{category}|{channel_id}",
        ))
    return options


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

    def __init__(self, bot, db, channel_id: int, job_type: str, category: str):
        super().__init__()
        self._bot = bot
        self._db = db
        self._channel_id = channel_id
        self._job_type = job_type
        self._category = category

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
            job_type=self._job_type,
            category=self._category,
        )

        # Validate the link is reachable
        loop = asyncio.get_running_loop()
        _, valid, reason = await loop.run_in_executor(None, _check_url, job.url)
        if not valid:
            await interaction.followup.send(
                f"URL check failed: {reason}\nDouble-check the link and try again.",
                ephemeral=True,
            )
            return

        posted = await self._bot.post_jobs(self._channel_id, [job])
        if not posted:
            await interaction.followup.send(
                "Failed to post — check bot permissions in the target channel.",
                ephemeral=True,
            )
            return

        self._db.mark_posted(job, self._channel_id)

        channel = self._bot._client.get_channel(self._channel_id)
        mention = channel.mention if channel else f"<#{self._channel_id}>"

        await interaction.followup.send(
            f"Posted **{job.title}** at **{job.company}** → {mention}.",
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


class ChannelSelectView(discord.ui.View):
    def __init__(self, bot, db):
        super().__init__(timeout=60)
        self._bot = bot
        self._db = db

        select = discord.ui.Select(
            placeholder="Pick a channel to post in...",
            options=_channel_options(),
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        job_type, category, channel_id_str = interaction.data["values"][0].split("|")
        await interaction.response.send_modal(
            AddJobModal(self._bot, self._db, int(channel_id_str), job_type, category)
        )


def register(tree: app_commands.CommandTree, bot, db) -> None:
    @tree.command(
        name="add-job",
        description="Manually add an opportunity and post it immediately",
    )
    async def add_job(interaction: discord.Interaction):
        await interaction.response.send_message(
            "Where should this be posted?",
            view=ChannelSelectView(bot, db),
            ephemeral=True,
        )

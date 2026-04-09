"""
Slack scraper — reads messages from a configured channel and extracts job URLs.

Setup requirements:
  1. Create a Slack App at https://api.slack.com/apps
  2. Add OAuth scopes: channels:history (public) or groups:history (private)
  3. Install the app to your workspace and copy the Bot User OAuth Token
  4. Invite the bot to your target channel: /invite @YourBotName
  5. Set SLACK_BOT_TOKEN and SLACK_CHANNEL_ID in .env
"""
import logging
import re
from datetime import datetime, timedelta

from database.models import Job
from .base_scraper import BaseScraper
import config

logger = logging.getLogger(__name__)

# Regex to extract URLs from Slack message text (handles Slack's <url|label> format)
URL_PATTERN = re.compile(r"<(https?://[^|>]+)(?:\|[^>]*)?>|https?://\S+")
LOOKBACK_DAYS = 2  # how many days back to scan for new messages


class SlackScraper(BaseScraper):

    def scrape(self) -> list[Job]:
        if not config.SLACK_BOT_TOKEN or not config.SLACK_CHANNEL_ID:
            logger.info("Slack not configured — skipping")
            return []

        try:
            from slack_sdk import WebClient
            from slack_sdk.errors import SlackApiError
        except ImportError:
            logger.error("slack_sdk not installed")
            return []

        client = WebClient(token=config.SLACK_BOT_TOKEN)
        oldest = (datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)).timestamp()

        try:
            result = client.conversations_history(
                channel=config.SLACK_CHANNEL_ID,
                oldest=str(oldest),
                limit=200,
            )
        except Exception as e:  # SlackApiError
            logger.error("Slack API error: %s", e)
            return []

        messages = result.get("messages", [])
        jobs: list[Job] = []
        seen_urls: set[str] = set()

        for msg in messages:
            text = msg.get("text", "")
            ts = msg.get("ts", "0")
            posted_dt = datetime.utcfromtimestamp(float(ts)).strftime("%Y-%m-%d")

            for match in URL_PATTERN.finditer(text):
                url = match.group(1) or match.group(0)
                url = self._normalize_url(url)
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # Skip non-job-looking URLs (e.g. images, slack internal links)
                if self._is_noise_url(url):
                    continue

                jobs.append(Job(
                    id=self._make_id(url),
                    title="Job Opportunity",   # title enriched by classifier later
                    company="Unknown",
                    location="Unknown",
                    description=text[:300].strip(),
                    url=url,
                    date_posted=posted_dt,
                    source="slack",
                    job_type=None,
                    category=None,
                ))

        logger.info("Slack: found %d URLs from last %d days", len(jobs), LOOKBACK_DAYS)
        return jobs

    def _is_noise_url(self, url: str) -> bool:
        noise_domains = (
            "slack.com", "giphy.com", "tenor.com", "youtube.com",
            "youtu.be", "twitter.com", "x.com", "reddit.com",
        )
        return any(d in url for d in noise_domains)

# opportunities-agent

Scrapes job/internship postings from multiple sources daily and posts them to the correct Discord channels.

## Sources

| Source | Type |
|--------|------|
| [underclassmen-opportunities](https://github.com/Jose-Gael-Cruz-Lopez/underclassmen-opportunities) | GitHub README |
| [intern-list.com](https://www.intern-list.com/) | Web (jobright.ai embed) |
| [newgrad-jobs.com](https://www.newgrad-jobs.com/) | Web (jobright.ai embed) |

## Discord Channel Structure

```
Internships
  #programs
  #cs-engineering-tech
  #business-finance-banking
  #consulting
  #humanities-healthcare-medicine

Full-Time
  #programs
  #cs-engineering-tech
  #business-finance-banking
  #consulting
  #humanities-healthcare-medicine
```

---

## Setup

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium     # one-time browser install
```

### 2. Create a Discord Bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** → give it a name (e.g. `opportunities-bot`)
3. Go to **Bot** in the left sidebar → click **Add Bot**
4. Under **Token**, click **Reset Token** and copy it — this is your `DISCORD_BOT_TOKEN`
5. Scroll down to **Privileged Gateway Intents** — enable **Server Members Intent** and **Message Content Intent**
6. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`
   - Bot Permissions: `Send Messages`, `Embed Links`, `View Channels`
7. Copy the generated URL, open it in your browser, and invite the bot to your server

### 3. Get Discord Channel IDs

1. In Discord, go to **User Settings → Advanced** and enable **Developer Mode**
2. Right-click each channel → **Copy Channel ID**
3. You'll need one ID per channel (10 channels total)

### 4. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in:
- `DISCORD_BOT_TOKEN` — from step 2
- All 10 `DISCORD_*_CHANNEL_ID` values — from step 3
- `ANTHROPIC_API_KEY` — from [console.anthropic.com](https://console.anthropic.com)
- `SCHEDULE_TIMEZONE` — your local timezone (e.g. `America/New_York`, `America/Chicago`, `America/Los_Angeles`)

### 5. Run

```bash
python main.py
```

The agent will start, connect to Discord, and run every day at **7:00 PM** in your configured timezone. Jobs already posted are tracked in `data/opportunities.db` and will never be re-posted.

### Run once immediately (for testing)

```python
# In a Python shell or separate script
import asyncio
from database.db import Database
from discord_bot.bot import OpportunitiesBot
from pipeline.runner import run_pipeline
import config

async def test():
    db = Database(config.DB_PATH)
    bot = OpportunitiesBot()
    await bot.start()
    await run_pipeline(bot, db)
    await bot.close()

asyncio.run(test())
```

---

## How classification works

Each job goes through two stages:

1. **Keyword filter** (`classifier/keyword_filter.py`) — fast regex matching assigns `job_type` (internship/full-time) and `category`. Runs instantly, no API cost.

2. **Claude classifier** (`classifier/claude_classifier.py`) — only called if keywords were ambiguous. Uses `claude-haiku-4-5` (fast + cheap) to classify the remaining jobs.

Both stages always produce a result — `programs` is the fallback category if nothing else matches.

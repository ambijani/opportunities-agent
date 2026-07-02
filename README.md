# opportunities-agent

Scrapes job/internship postings from multiple sources daily and posts them to the correct Discord channels. Runs as a **GitHub Actions cron job** (free tier) with **Turso/libSQL** for deduplication and **Cloudflare Workers** for slash commands.

## Architecture

| Component | Tool | Purpose |
|-----------|------|---------|
| Scheduler | GitHub Actions cron (`0 0 * * *`) | Runs pipeline daily at midnight UTC (7pm CDT) |
| Dedup DB | [Turso](https://turso.tech) (libSQL) | Stores posted job hashes; prevents re-posting |
| Discord posting | Webhook URLs (per channel) | Posts embeds — no bot token required |
| Slash commands | Cloudflare Worker | `/subscribe`, `/unsubscribe`, `/add-job` |

## Sources

| Source | Type |
|--------|------|
| [underclassmen-opportunities](https://github.com/Jose-Gael-Cruz-Lopez/underclassmen-opportunities) | GitHub README |
| [intern-list.com](https://www.intern-list.com/) | Web (jobright.ai embed) |
| [newgrad-jobs.com](https://www.newgrad-jobs.com/) | Web (jobright.ai embed) |

## Discord Channel Structure

```
Internships
  #cs-engineering-tech
  #business-finance-banking
  #consulting
  #humanities-healthcare-medicine
  #programs

Full-Time
  #cs-engineering-tech
  #business-finance-banking
  #consulting
  #humanities-healthcare-medicine
  #programs

#scholarships
```

---

## Local Development

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure environment

Copy and fill in the required variables:

```bash
cp .env.example .env
```

Key variables:

- `ANTHROPIC_API_KEY` — from [console.anthropic.com](https://console.anthropic.com)
- `TURSO_DATABASE_URL` — from `turso db show opportunities-agent --url`
- `TURSO_AUTH_TOKEN` — from `turso db tokens create opportunities-agent`
- `DISCORD_WEBHOOK_*` — one webhook URL per channel (created in Discord channel settings)
- `DISCORD_*_CHANNEL_ID` — right-click channels in Discord (Developer Mode on)

### 3. Run

```bash
python -m pipeline.entrypoint
```

To do a dry run (classify + validate but skip Discord posting):

```bash
DRY_RUN=true python -m pipeline.entrypoint
```

---

## GitHub Actions (production)

The pipeline runs automatically via `.github/workflows/daily_pipeline.yml`.

### Required GitHub Secrets

Add these under **Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `TURSO_DATABASE_URL` | Turso database URL (`https://...`) |
| `TURSO_AUTH_TOKEN` | Turso auth token |
| `DISCORD_WEBHOOK_INTERN_CS_ENGINEERING` | Webhook for each channel... |
| `DISCORD_WEBHOOK_INTERN_BUSINESS_FINANCE` | |
| `DISCORD_WEBHOOK_INTERN_CONSULTING` | |
| `DISCORD_WEBHOOK_INTERN_HUMANITIES` | |
| `DISCORD_WEBHOOK_INTERN_PROGRAMS` | |
| `DISCORD_WEBHOOK_FT_CS_ENGINEERING` | |
| `DISCORD_WEBHOOK_FT_BUSINESS_FINANCE` | |
| `DISCORD_WEBHOOK_FT_CONSULTING` | |
| `DISCORD_WEBHOOK_FT_HUMANITIES` | |
| `DISCORD_WEBHOOK_FT_PROGRAMS` | |
| `DISCORD_WEBHOOK_SCHOLARSHIPS` | |

### Manual trigger

Go to **Actions → Daily Opportunities Pipeline → Run workflow**. Check the `dry_run` box to classify without posting.

---

## Cloudflare Worker (slash commands)

The Worker in `worker/` handles Discord slash commands via the Interactions Endpoint.

### Deploy

```bash
cd worker
npm install
npx wrangler deploy
```

### Required Worker secrets (set once)

```bash
npx wrangler secret put DISCORD_BOT_TOKEN
npx wrangler secret put DISCORD_PUBLIC_KEY
npx wrangler secret put TURSO_DATABASE_URL
npx wrangler secret put TURSO_AUTH_TOKEN
```

### Register slash commands (one-time)

```bash
python scripts/register_commands.py
```

Then set the Interactions Endpoint URL in Discord Developer Portal to:
`https://opportunities-agent.<your-subdomain>.workers.dev`

### Slash commands

| Command | Description |
|---------|-------------|
| `/subscribe` | Select channels to get DM notifications when new jobs are posted |
| `/unsubscribe` | Remove all subscriptions |
| `/add-job` | Manually submit a job posting to a channel |

---

## Database

Schema is in `database/schema.sql`. Two tables:

- `posted_jobs` — URL hashes of every posted job (dedup key)
- `subscribers` — user → channel subscriptions for DM notifications

To initialize a fresh Turso database:

```bash
turso db shell opportunities-agent < database/schema.sql
```

---

## How classification works

Each job goes through two stages:

1. **Keyword filter** (`classifier/keyword_filter.py`) — fast regex matching assigns `job_type` (internship/full-time) and `category`. No API cost.

2. **Claude classifier** (`classifier/claude_classifier.py`) — only called if keywords were ambiguous. Uses `claude-haiku-4-5` to classify the remaining jobs.

Both stages always produce a result — `programs` is the fallback category if nothing else matches.

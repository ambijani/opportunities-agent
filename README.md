# opportunities-agent

Scrapes job/internship postings from multiple sources daily and posts them to the correct Discord channels. Runs on Google Cloud Run with Firestore for deduplication.

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

## Local Development

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure environment

```bash
cp .env.example .env
```

Fill in `.env`:
- `DISCORD_BOT_TOKEN` — from [discord.com/developers/applications](https://discord.com/developers/applications)
- All `DISCORD_*_CHANNEL_ID` values — right-click channels in Discord (Developer Mode on)
- `ANTHROPIC_API_KEY` — from [console.anthropic.com](https://console.anthropic.com)
- `SCHEDULE_TIMEZONE` — e.g. `America/Chicago`

### 3. Authenticate with GCP (for Firestore)

```bash
gcloud auth application-default login
```

### 4. Run

```bash
python main.py
```

Connects to Discord, starts the scheduler (daily at 7pm Central), and serves a health check at `http://localhost:8080/health`.

---

## Deploying to Cloud Run

### Prerequisites (one-time)

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com firestore.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com
```

### 1. Create Firestore database

```bash
gcloud firestore databases create --location=us-central1 --project=YOUR_PROJECT_ID
```

### 2. Store secrets

```bash
echo -n "YOUR_BOT_TOKEN" | gcloud secrets create DISCORD_BOT_TOKEN --data-file=- --project=YOUR_PROJECT_ID
echo -n "YOUR_ANTHROPIC_KEY" | gcloud secrets create ANTHROPIC_API_KEY --data-file=- --project=YOUR_PROJECT_ID
```

Grant the Cloud Run service account access:

```bash
gcloud secrets add-iam-policy-binding DISCORD_BOT_TOKEN --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" --role="roles/secretmanager.secretAccessor" --project=YOUR_PROJECT_ID
gcloud secrets add-iam-policy-binding ANTHROPIC_API_KEY --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" --role="roles/secretmanager.secretAccessor" --project=YOUR_PROJECT_ID
```

### 3. Fill in channel IDs

Edit `deploy/env-vars.txt` with your Discord channel IDs.

### 4. Deploy

```bash
GCP_PROJECT_ID=YOUR_PROJECT_ID bash deploy/deploy.sh
```

To redeploy after code changes, just run step 4 again.

---

## Troubleshooting

### Check if the bot is running

Look for the bot online in Discord. If it's offline, check the logs first.

### View logs

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=opportunities-agent" --project=YOUR_PROJECT_ID --limit=50 --format="table(timestamp,textPayload)"
```

### Check the health endpoint (requires auth)

```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" YOUR_CLOUD_RUN_URL/health
```

Should return `{"status":"ok"}`. A 403 without the auth header is expected — the service is not publicly accessible.

### Check Cloud Run service status

```bash
gcloud run services describe opportunities-agent --region=us-central1 --project=YOUR_PROJECT_ID
```

Look at `status.conditions` — `Ready: True` means it's healthy.

### Check Firestore data

Go to [console.cloud.google.com](https://console.cloud.google.com) → Firestore → `posted_jobs` collection. Each document is a posted job keyed by a hash of its URL.

### Bot connected but pipeline not running

- Confirm `SCHEDULE_HOUR`, `SCHEDULE_MINUTE`, and `SCHEDULE_TIMEZONE` in `deploy/env-vars.txt` are correct
- Check logs around 7pm Central for pipeline output
- To trigger a manual run, use the `/add-job` slash command in Discord

### Redeploying after a crash

Cloud Run automatically restarts the container on failure. If it keeps crashing, check the logs for the error and redeploy after fixing:

```bash
GCP_PROJECT_ID=YOUR_PROJECT_ID bash deploy/deploy.sh
```

---

## How classification works

Each job goes through two stages:

1. **Keyword filter** (`classifier/keyword_filter.py`) — fast regex matching assigns `job_type` (internship/full-time) and `category`. No API cost.

2. **Claude classifier** (`classifier/claude_classifier.py`) — only called if keywords were ambiguous. Uses `claude-haiku-4-5` to classify the remaining jobs.

Both stages always produce a result — `programs` is the fallback category if nothing else matches.

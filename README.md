# Opportunities Agent

A bot that automatically finds internship, full-time, and scholarship postings from across the web and posts them to Discord — so you don't have to manually check job boards every day.

Every day, it:

1. **Scans** several job boards and curated GitHub lists for new postings
2. **Sorts** each one into the right category (internship vs. full-time vs. scholarship, and by field — CS/engineering, business, consulting, healthcare, etc.)
3. **Posts** new, never-before-seen opportunities to the matching Discord channel
4. **Skips duplicates** — it remembers what's already been posted, so you won't see the same listing twice

## Using it in Discord

If this bot is running in your server, there are a few slash commands available:

| Command | What it does |
|---------|--------------|
| `/subscribe` | Pick channels you care about and get a DM whenever a new job is posted there |
| `/unsubscribe` | Stop getting those DMs |
| `/add-job` | Manually share a job posting with a channel yourself |

## Where the postings come from

- [underclassmen-opportunities](https://github.com/Jose-Gael-Cruz-Lopez/underclassmen-opportunities) (GitHub)
- [SimplifyJobs Summer2027-Internships](https://github.com/SimplifyJobs/Summer2027-Internships) (GitHub)
- [intern-list.com](https://www.intern-list.com/)
- [newgrad-jobs.com](https://www.newgrad-jobs.com/)

## How it decides where to post

Postings are sorted into channels for **Internships** and **Full-Time** roles, each split by field:

```
#cs-engineering-tech
#business-finance-banking
#consulting
#humanities-healthcare-medicine
#programs
```

Scholarships go to their own `#scholarships` channel. Sorting is done with a quick keyword check first, and anything ambiguous gets a second look from Claude (Anthropic's AI model) to make the right call.

## Under the hood

This is a free/low-cost, fully automated pipeline — no server to maintain. It runs on a daily schedule using GitHub Actions, keeps track of what's already been posted with a small database, and uses a Cloudflare Worker to handle the Discord slash commands.

If you want to run, deploy, or modify this project yourself, the full engineering reference — setup instructions, environment variables, deployment steps, and internals — lives in **[docs/TECHNICAL.md](docs/TECHNICAL.md)**.

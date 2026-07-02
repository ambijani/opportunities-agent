"""
One-time script to register slash commands with Discord's API.
Run this after deploying the Cloudflare Worker (replaces bot.tree.sync()).

Usage:
    DISCORD_BOT_TOKEN=... DISCORD_APPLICATION_ID=... python scripts/register_commands.py
"""
import json
import os
import sys

import requests

TOKEN  = os.environ.get("DISCORD_BOT_TOKEN", "")
APP_ID = os.environ.get("DISCORD_APPLICATION_ID", "")

if not TOKEN or not APP_ID:
    print("DISCORD_BOT_TOKEN and DISCORD_APPLICATION_ID are required.")
    sys.exit(1)

COMMANDS = [
    {
        "name": "subscribe",
        "description": "Choose which channels to get DMs for when a curated opportunity is posted",
        "default_member_permissions": None,
        "dm_permission": False,
    },
    {
        "name": "unsubscribe",
        "description": "Stop receiving DMs for manually curated opportunities",
        "default_member_permissions": None,
        "dm_permission": False,
    },
    {
        "name": "add-job",
        "description": "Manually add an opportunity and post it immediately",
        "default_member_permissions": None,
        "dm_permission": False,
    },
]

url = f"https://discord.com/api/v10/applications/{APP_ID}/commands"
headers = {"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json"}

resp = requests.put(url, headers=headers, data=json.dumps(COMMANDS))

if resp.ok:
    registered = resp.json()
    print(f"Registered {len(registered)} commands:")
    for cmd in registered:
        print(f"  /{cmd['name']} — {cmd['id']}")
else:
    print(f"Failed: HTTP {resp.status_code}")
    print(resp.text)
    sys.exit(1)

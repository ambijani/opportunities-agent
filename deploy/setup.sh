#!/bin/bash
# Run once on a fresh GCP e2-micro VM (Ubuntu 22.04) to set up the bot.
set -euo pipefail

APP_DIR="/opt/opportunities-agent"
SERVICE_NAME="opportunities-agent"
REPO_URL="https://github.com/ambijani/opportunities-agent"

# ── System deps ───────────────────────────────────────────────────────────────
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv git

# ── Clone repo ────────────────────────────────────────────────────────────────
sudo mkdir -p "$APP_DIR"
sudo chown "$USER":"$USER" "$APP_DIR"

if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" pull
else
    git clone "$REPO_URL" "$APP_DIR"
fi

# ── Python env ────────────────────────────────────────────────────────────────
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

# ── Playwright browsers ───────────────────────────────────────────────────────
sudo apt-get install -y -qq \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libxkbcommon0 libatspi2.0-0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2

"$APP_DIR/.venv/bin/playwright" install chromium

# ── Data directory ────────────────────────────────────────────────────────────
mkdir -p "$APP_DIR/data" "$APP_DIR/reports"

# ── .env ──────────────────────────────────────────────────────────────────────
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    echo ""
    echo ">>> Fill in $APP_DIR/.env before starting the service."
fi

# ── systemd service ───────────────────────────────────────────────────────────
sudo cp "$APP_DIR/deploy/$SERVICE_NAME.service" "/etc/systemd/system/$SERVICE_NAME.service"
sudo sed -i "s|__USER__|$USER|g" "/etc/systemd/system/$SERVICE_NAME.service"
sudo sed -i "s|__APP_DIR__|$APP_DIR|g" "/etc/systemd/system/$SERVICE_NAME.service"

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

echo ""
echo "Setup complete. Next steps:"
echo "  1. Edit $APP_DIR/.env with your tokens"
echo "  2. sudo systemctl start $SERVICE_NAME"
echo "  3. sudo journalctl -u $SERVICE_NAME -f   # tail logs"

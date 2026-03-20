# Thermal Printer Telegram Bot

A Telegram bot that lets approved friends send text and images to be printed on a Bluetooth thermal printer. Built for Raspberry Pi.

## Features

- Text and image printing via Telegram
- User allowlist with admin controls
- Persistent message queue (SQLite) — no messages lost on restart
- Automatic retry with configurable backoff
- Health check and metrics endpoint
- Runs in Docker with `restart: always` for high uptime

## Quick Start

### Prerequisites
- Raspberry Pi with Bluetooth
- Docker installed (`curl -fsSL https://get.docker.com | sh`)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- Your Telegram user ID (get it from [@userinfobot](https://t.me/userinfobot))
- Your printer's BLE MAC address

### Setup

```bash
git clone https://github.com/<your-username>/thermal-printer-telegram-bot.git
cd thermal-printer-telegram-bot
cp .env.example .env
# Edit .env with your bot token, user ID, printer address
docker compose up -d
```

### Admin Commands

| Command | Description |
|---------|-------------|
| `/status` | Printer status and queue info |
| `/flush` | Print all queued messages now |
| `/queue` | View pending messages |
| `/history [n]` | Show recent prints |
| `/allow <user_id>` | Add user to allowlist |
| `/remove <user_id>` | Remove user |
| `/allowlist` | Show allowed users |
| `/pause` / `/resume` | Pause/resume auto-printing |

### Monitoring

- Health check: `http://<rpi-ip>:8000/health`
- Metrics: `http://<rpi-ip>:8000/metrics`
- Logs: `docker compose logs -f`

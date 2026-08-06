# iposcan

Daily scanner for Indian Mainboard IPOs. Alerts on Telegram when an open IPO
has Total subscription ≥3x, an implied GMP listing gain ≥10%, and (where
determinable) 3 consecutive years of profit growth.

## Setup

1. **Create a Telegram bot:** message [@BotFather](https://t.me/BotFather) on
   Telegram, run `/newbot`, and save the token it gives you.
2. **Get your chat ID:** message your new bot once, then visit
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and read `chat.id` from
   the response.
3. **Add GitHub Actions secrets** (repo Settings → Secrets and variables →
   Actions): `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
4. The workflow in `.github/workflows/scan.yml` runs daily at 6:00 PM IST. It
   can also be triggered manually via the Actions tab ("Run workflow").

## Local development

```bash
uv sync
uv run pytest tests/ -v
uv run ruff check .
```

To run the scanner locally (requires the two env vars above):

```bash
TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... uv run python -m iposcan.main
```

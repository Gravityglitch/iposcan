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
4. The workflow in `.github/workflows/scan.yml` runs daily at 6:00 PM IST,
   alerts on new IPOs that pass all three criteria, and dedupes via
   `state/alerted_ipos.json`. It can also be triggered manually via the
   Actions tab ("Run workflow").
5. The workflow in `.github/workflows/report.yml` runs daily at 8:00 AM UTC
   and reports on *every* currently open Mainboard IPO (pass or fail, no
   dedup) as a GitHub Actions job summary. If the same two secrets are set,
   it also sends the report to Telegram — this is optional; the workflow
   runs fine without them.

## Local development

```bash
uv sync
uv run pytest tests/ -v
uv run ruff check .
```

Both `main.py` and `report.py` load credentials from a local `.env` file
(via `python-dotenv`) if present, so you don't have to export the env vars
by hand:

```bash
cp .env.example .env   # then fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
uv run python -m iposcan.main     # alert-on-pass, with dedup
uv run python -m iposcan.report   # report on all open Mainboard IPOs
```

`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` are required for `main.py` but
optional for `report.py` — omit them (leave `.env` blank or unset) to only
print the report / write it to `$GITHUB_STEP_SUMMARY`.

# IPO Scanner — Design

## Purpose

A daily automated scan of currently-open Indian Mainboard IPOs that pushes a
Telegram alert when an IPO meets three simple criteria: strong oversubscription,
a positive grey market premium, and (where determinable) a track record of
growing profit. The goal is a low-maintenance personal signal, not a full
research platform — the scanner narrows the field; the user still makes the
final call.

## Scope

- Mainboard IPOs only (SME excluded — SME subscription multiples run so high
  routinely that a 3x bar is meaningless, and SME financials are even less
  reliably available).
- Only IPOs currently in their open bidding window on the day the scan runs.
- One alert per IPO, sent the first day it crosses the threshold (not
  re-sent daily while it stays above threshold).

## Criteria

| Criterion | Source | Threshold | Notes |
|---|---|---|---|
| Oversubscription | `ipowatch.in` subscription table (QIB / NII / Retail / Shareholder / Total) | **Total ≥ 3x** triggers the alert | Full breakdown by category is always included in the notification so the user can pick which lane (QIB/HNI/Retail/Shareholder) to apply from, even though only Total drives the go/no-go decision |
| GMP (Grey Market Premium) | `ipowatch.in` GMP table | Estimated listing price ≥ **10% above issue price** | Shown as both ₹ and % in the alert |
| Growing profit | Best-effort scrape, primary target Chittorgarh's per-IPO page (financials table); fallback to alternate sources (e.g. Groww/Equitymaster IPO pages) if that fails | PAT grew in **each of the last 3 reported years** | Non-blocking: if the scrape fails or data is incomplete, the field is marked `Unknown` and the alert still fires (flagged "⚠️ verify profit trend manually") rather than being suppressed |

**Update (confirmed during plan research):** the earlier 403s were specific
to the design-research fetch tool's request signature, not a general block —
both `chittorgarh.com` and `ipowatch.in` return normal HTML to a plain HTTP
GET with a standard browser `User-Agent` header. Chittorgarh's per-IPO page
has a clean "Company Financials (Restated)" table with a "Profit After Tax"
row across the last 3 reported periods, keyed off company name via
Chittorgarh's own IPO dashboard listing. Financials scraping is expected to
work directly, not just as a best-effort fallback — `Unknown` remains the
graceful degradation path (e.g. name-matching failure between sources) but
should be the exception rather than the norm.

## Architecture

Python script run on a schedule via GitHub Actions (chosen over a Vercel Cron
+ hosted dashboard, which would add an unneeded deploy target, and over local
Mac cron, which silently stops working when the machine is asleep/off).

```
iposcan/
├── src/iposcan/
│   ├── sources/
│   │   ├── subscription.py   # scrape ipowatch.in subscription table
│   │   ├── gmp.py            # scrape ipowatch.in GMP table
│   │   └── financials.py     # best-effort scrape, returns Unknown on failure
│   ├── criteria.py           # pure filter logic: parsed data -> pass/fail + reasons
│   ├── state.py              # tracks which IPOs were already alerted (dedup)
│   ├── notify.py             # Telegram bot push
│   └── main.py               # orchestrates: fetch -> filter -> dedup -> notify -> save state
├── tests/
│   ├── fixtures/              # saved HTML snapshots for scraper parsing tests
│   └── test_*.py
├── state/alerted_ipos.json    # committed state, prevents repeat alerts for same IPO
├── .github/workflows/scan.yml # daily cron
└── pyproject.toml
```

Env/dependency management via `uv`, formatting/linting via `ruff`, type hints
throughout, tests via `pytest` — per standing project conventions.

## Data Flow & Scheduling

**Schedule:** Daily at 6:00 PM IST (12:30 UTC) — `30 12 * * *`. This is after
NSE/BSE subscription data stops updating for the day (~5 PM IST), so the
day's numbers are final rather than a partial snapshot. Non-trading days
simply yield no open IPOs; no special-casing needed.

**Per run:**
1. Fetch the list of currently-open Mainboard IPOs (derived from the
   subscription table — anything listed there is open).
2. For each: scrape subscription breakdown, GMP, and attempt financials.
3. Evaluate against criteria — pass/fail + reasons + full breakdown.
4. For IPOs that pass: check `state/alerted_ipos.json`; skip if already
   alerted for this IPO.
5. Send a Telegram message per newly-passing IPO (name, Total + full
   category breakdown, GMP ₹/%, profit trend or "Unknown").
6. Update and commit `state/alerted_ipos.json` with newly-alerted IPOs.

Dedup is per-IPO (alert once, the first day it crosses), not per-run, so an
IPO that stays above threshold for the rest of its bidding window doesn't
re-alert daily.

## Error Handling & Testing (brief)

Scraping failures for a given data point degrade to `Unknown`/skip rather
than crashing the run; persistent failures are visible in the GitHub Actions
run logs. Tests cover the pure filter logic (`criteria.py`) and scraper
parsing against saved HTML fixtures (avoiding flaky live-network tests), per
`pytest` project conventions.

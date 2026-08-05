# IPO Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python script that runs daily via GitHub Actions, scrapes IPO subscription/GMP data from ipowatch.in and financials from chittorgarh.com, filters currently-open Mainboard IPOs against three criteria, and sends a Telegram alert for new matches.

**Architecture:** Each data source gets its own module with a `fetch_*` (network I/O) and `parse_*` (pure, fixture-tested) function pair. A `criteria` module evaluates parsed data against thresholds. A `state` module dedups alerts across runs via a committed JSON file. A `notify` module formats and sends Telegram messages. `main.py` orchestrates the pipeline.

**Tech Stack:** Python 3.11+, `uv` (env/deps), `ruff` (lint/format), `pytest` (tests), `requests` + `beautifulsoup4` (HTTP/parsing), GitHub Actions (scheduling).

## Global Constraints

- Total subscription ≥ 3x triggers the alert (per spec); full QIB/NII/Retail/Total breakdown always included.
- GMP implies ≥ 10% listing gain triggers the alert.
- Profit growth (PAT increasing across all 3 of the last 3 reported periods) is evaluated but **never blocks** an alert — unknown/missing financials are shown as "verify manually", not suppressed.
- Mainboard IPOs only, only while in their open bidding window.
- One alert per IPO ever (dedup via `state/alerted_ipos.json`, committed back to the repo by the workflow).
- Daily schedule: `30 12 * * *` (6:00 PM IST).
- All HTTP requests use a standard browser `User-Agent` header (confirmed required for chittorgarh.com; harmless for ipowatch.in).

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/iposcan/__init__.py`
- Create: `src/iposcan/sources/__init__.py`
- Create: `.gitignore`
- Create: `state/alerted_ipos.json`

**Interfaces:**
- Produces: package `iposcan` importable via `uv run python -c "import iposcan"`; `state/alerted_ipos.json` as the initial empty dedup store other tasks read/write.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "iposcan"
version = "0.1.0"
description = "Daily scanner for oversubscribed, high-GMP, profit-growing Indian Mainboard IPOs"
requires-python = ">=3.11"
dependencies = [
    "requests>=2.32",
    "beautifulsoup4>=4.12",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "ruff>=0.6",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/iposcan"]
```

- [ ] **Step 2: Create empty package files**

`src/iposcan/__init__.py`:
```python
"""Daily Indian Mainboard IPO scanner."""
```

`src/iposcan/sources/__init__.py`:
```python
"""Data source modules: subscription, GMP, and financials scrapers."""
```

- [ ] **Step 3: Create `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
```

- [ ] **Step 4: Create initial state file**

`state/alerted_ipos.json`:
```json
{
  "alerted": []
}
```

- [ ] **Step 5: Sync environment and verify**

Run: `uv sync`
Expected: creates `.venv/` and `uv.lock`, no errors.

Run: `uv run python -c "import iposcan; print('ok')"`
Expected: `ok`

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/iposcan/__init__.py src/iposcan/sources/__init__.py .gitignore state/alerted_ipos.json uv.lock
git commit -m "chore: scaffold project with uv, ruff, pytest"
```

---

## Task 2: HTML Parsing Utilities

**Files:**
- Create: `src/iposcan/html_utils.py`
- Test: `tests/test_html_utils.py`

**Interfaces:**
- Produces: `find_table_by_header_keywords(soup: BeautifulSoup, keywords: list[str]) -> Tag | None`, `parse_number(text: str) -> float` — used by every source module in Tasks 3-5.

- [ ] **Step 1: Write the failing tests**

`tests/test_html_utils.py`:
```python
from bs4 import BeautifulSoup

from iposcan.html_utils import find_table_by_header_keywords, parse_number


def test_find_table_by_header_keywords_matches_thead():
    html = """
    <table>
      <thead><tr><th>IPO</th><th>QIB (X)</th><th>Total (X)</th></tr></thead>
      <tbody><tr><td>Foo</td><td>1.0</td><td>2.0</td></tr></tbody>
    </table>
    """
    soup = BeautifulSoup(html, "html.parser")
    table = find_table_by_header_keywords(soup, ["IPO", "QIB", "Total"])
    assert table is not None
    assert table.find("td").get_text(strip=True) == "Foo"


def test_find_table_by_header_keywords_matches_bare_row():
    html = """
    <table>
      <tr><td>IPO Name</td><td>IPO GMP*</td><td>Status</td></tr>
      <tr><td>Bar</td><td>10</td><td>Open</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, "html.parser")
    table = find_table_by_header_keywords(soup, ["IPO Name", "GMP", "Status"])
    assert table is not None


def test_find_table_by_header_keywords_returns_none_when_absent():
    soup = BeautifulSoup("<table><tr><td>Unrelated</td></tr></table>", "html.parser")
    assert find_table_by_header_keywords(soup, ["QIB", "NII"]) is None


def test_parse_number_plain():
    assert parse_number("3.23") == 3.23


def test_parse_number_with_currency_and_commas():
    assert parse_number("₹1,168.88") == 1168.88


def test_parse_number_dash_is_zero():
    assert parse_number("₹-") == 0.0
    assert parse_number("-") == 0.0
    assert parse_number("") == 0.0


def test_parse_number_strips_trailing_parenthetical():
    assert parse_number("₹1,126 (29.28%)") == 1126.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_html_utils.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'iposcan.html_utils'`

- [ ] **Step 3: Implement `html_utils.py`**

```python
"""Shared HTML parsing helpers used by all source modules."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup
from bs4.element import Tag

_TRAILING_PARENS_RE = re.compile(r"\s*\([^)]*\)\s*$")


def find_table_by_header_keywords(soup: BeautifulSoup, keywords: list[str]) -> Tag | None:
    """Return the first <table> whose first row contains all keywords (case-insensitive).

    Works whether the header row is a <thead><th> row or a bare first <tr> of
    <td> cells (both patterns are used across the sites this scrapes).
    """
    for table in soup.find_all("table"):
        first_row = table.find("tr")
        if first_row is None:
            continue
        header_text = " ".join(
            cell.get_text(strip=True) for cell in first_row.find_all(["th", "td"])
        ).lower()
        if all(keyword.lower() in header_text for keyword in keywords):
            return table
    return None


def parse_number(text: str) -> float:
    """Parse a table cell like '₹1,168.88', '3.23', '₹-', or '₹1,126 (29.28%)' into a float.

    Dashes/blanks (common for "not yet available") parse to 0.0. A trailing
    parenthetical, e.g. a percentage annotation, is stripped before parsing.
    """
    cleaned = _TRAILING_PARENS_RE.sub("", text.strip())
    cleaned = cleaned.replace("₹", "").replace(",", "").strip()
    if cleaned in ("", "-", "—"):
        return 0.0
    return float(cleaned)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_html_utils.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/iposcan/html_utils.py tests/test_html_utils.py
git commit -m "feat: add shared HTML parsing utilities"
```

---

## Task 3: Subscription Source

**Files:**
- Create: `src/iposcan/sources/subscription.py`
- Create: `tests/fixtures/subscription.html`
- Test: `tests/test_subscription.py`

**Interfaces:**
- Consumes: `find_table_by_header_keywords`, `parse_number` from `iposcan.html_utils` (Task 2).
- Produces: `SubscriptionRow` dataclass (`ipo_name: str`, `ipo_type: str`, `closing_date: str`, `qib: float`, `nii: float`, `retail: float`, `total: float`), `fetch_subscription_html() -> str`, `parse_subscription_table(html: str) -> list[SubscriptionRow]` — consumed by `main.py` (Task 9).

- [ ] **Step 1: Create fixture**

`tests/fixtures/subscription.html`:
```html
<html><body>
<table id="tablepress-10" class="tablepress tablepress-id-10 tablepress-responsive">
<thead>
<tr><th>IPO</th><th>Type</th><th>Closing Date</th><th>QIB  (X)</th><th>NII  (X)</th><th>Retail  (X)</th><th>Total (X)</th><th>Last Updated</th></tr>
</thead>
<tbody>
<tr><td>Ardee Industries</td><td>Mainboard</td><td>August 7, 2026</td><td>1.13</td><td>5.58</td><td>3.42</td><td>3.23</td><td>17:49</td></tr>
<tr><td>Fusion Klassroom</td><td>SME</td><td>August 4, 2026</td><td>1.00</td><td>1.47</td><td>1.80</td><td>1.50</td><td>17:41</td></tr>
<tr><td>Milky Mist Dairy Food</td><td>Mainboard</td><td>August 13, 2026</td><td>0.50</td><td>0.80</td><td>1.10</td><td>0.90</td><td>15:57</td></tr>
</tbody>
</table>
</body></html>
```

- [ ] **Step 2: Write the failing test**

`tests/test_subscription.py`:
```python
from pathlib import Path
from unittest.mock import patch

from iposcan.sources.subscription import (
    SUBSCRIPTION_URL,
    fetch_subscription_html,
    parse_subscription_table,
)

FIXTURE = Path(__file__).parent / "fixtures" / "subscription.html"


def test_parse_subscription_table_parses_all_rows():
    html = FIXTURE.read_text()
    rows = parse_subscription_table(html)
    assert len(rows) == 3
    ardee = rows[0]
    assert ardee.ipo_name == "Ardee Industries"
    assert ardee.ipo_type == "Mainboard"
    assert ardee.closing_date == "August 7, 2026"
    assert ardee.qib == 1.13
    assert ardee.nii == 5.58
    assert ardee.retail == 3.42
    assert ardee.total == 3.23


def test_parse_subscription_table_raises_when_table_missing():
    import pytest

    from iposcan.sources.subscription import parse_subscription_table as parse_fn

    with pytest.raises(ValueError, match="subscription table not found"):
        parse_fn("<html><body>no table here</body></html>")


def test_fetch_subscription_html_requests_correct_url_and_headers():
    with patch("iposcan.sources.subscription.requests.get") as mock_get:
        mock_get.return_value.text = "<html></html>"
        mock_get.return_value.raise_for_status.return_value = None
        result = fetch_subscription_html()
        assert result == "<html></html>"
        called_url = mock_get.call_args.args[0]
        called_headers = mock_get.call_args.kwargs["headers"]
        assert called_url == SUBSCRIPTION_URL
        assert "Mozilla" in called_headers["User-Agent"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_subscription.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'iposcan.sources.subscription'`

- [ ] **Step 4: Implement `subscription.py`**

```python
"""Fetch and parse Mainboard/SME IPO subscription data from ipowatch.in."""
from __future__ import annotations

from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from iposcan.html_utils import find_table_by_header_keywords, parse_number

SUBSCRIPTION_URL = "https://ipowatch.in/ipo-subscription-status-today/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
REQUEST_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class SubscriptionRow:
    ipo_name: str
    ipo_type: str
    closing_date: str
    qib: float
    nii: float
    retail: float
    total: float


def fetch_subscription_html() -> str:
    response = requests.get(
        SUBSCRIPTION_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.text


def parse_subscription_table(html: str) -> list[SubscriptionRow]:
    soup = BeautifulSoup(html, "html.parser")
    table = find_table_by_header_keywords(soup, ["IPO", "QIB", "NII", "Retail", "Total"])
    if table is None:
        raise ValueError("subscription table not found on page")

    rows: list[SubscriptionRow] = []
    for tr in table.find_all("tr")[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 7:
            continue
        rows.append(
            SubscriptionRow(
                ipo_name=cells[0],
                ipo_type=cells[1],
                closing_date=cells[2],
                qib=parse_number(cells[3]),
                nii=parse_number(cells[4]),
                retail=parse_number(cells[5]),
                total=parse_number(cells[6]),
            )
        )
    return rows
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_subscription.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/iposcan/sources/subscription.py tests/test_subscription.py tests/fixtures/subscription.html
git commit -m "feat: add subscription data source"
```

---

## Task 4: GMP Source

**Files:**
- Create: `src/iposcan/sources/gmp.py`
- Create: `tests/fixtures/gmp.html`
- Test: `tests/test_gmp.py`

**Interfaces:**
- Consumes: `find_table_by_header_keywords`, `parse_number` from `iposcan.html_utils` (Task 2).
- Produces: `GmpRow` dataclass (`ipo_name: str`, `gmp_rupees: float`, `price_band: str`, `listing_gain_pct: float`, `date_range: str`, `ipo_type: str`, `status: str`), `fetch_gmp_html() -> str`, `parse_gmp_table(html: str) -> list[GmpRow]`, `filter_open_mainboard(rows: list[GmpRow]) -> list[GmpRow]` — consumed by `main.py` (Task 9).

- [ ] **Step 1: Create fixture**

`tests/fixtures/gmp.html`:
```html
<html><body>
<figure class="wp-block-table">
<table>
<tr><td>IPO Name</td><td>IPO GMP*</td><td>Trend</td><td>Price Band</td><td>Est. Listing</td><td>Date</td><td>Type</td><td>Status</td><td>Last Updated</td></tr>
<tr><td>Ardee Industries</td><td>₹13</td><td>🔴</td><td>₹53</td><td>₹66 (24.53%)</td><td>5-7 August</td><td>Mainboard</td><td>Open</td><td>5 Aug, 15:57</td></tr>
<tr><td>Aegeus Technologies</td><td>₹0</td><td>🟡</td><td>₹105</td><td>₹- (0.00%)</td><td>4-6 August</td><td>BSE SME</td><td>Open</td><td>5 Aug, 15:57</td></tr>
<tr><td>Dhoot Transmission</td><td>₹255</td><td>🟢</td><td>₹871</td><td>₹1,126 (29.28%)</td><td>10-12 August</td><td>Mainboard</td><td>Upcoming</td><td>5 Aug, 15:57</td></tr>
<tr><td>Milky Mist Dairy Food</td><td>₹5</td><td>🟢</td><td>₹450</td><td>₹461 (2.44%)</td><td>11-13 August</td><td>Mainboard</td><td>Open</td><td>5 Aug, 15:57</td></tr>
</table>
</figure>
</body></html>
```

- [ ] **Step 2: Write the failing test**

`tests/test_gmp.py`:
```python
from pathlib import Path
from unittest.mock import patch

from iposcan.sources.gmp import (
    GMP_URL,
    fetch_gmp_html,
    filter_open_mainboard,
    parse_gmp_table,
)

FIXTURE = Path(__file__).parent / "fixtures" / "gmp.html"


def test_parse_gmp_table_parses_all_rows():
    html = FIXTURE.read_text()
    rows = parse_gmp_table(html)
    assert len(rows) == 4
    ardee = rows[0]
    assert ardee.ipo_name == "Ardee Industries"
    assert ardee.gmp_rupees == 13.0
    assert ardee.price_band == "₹53"
    assert ardee.listing_gain_pct == 24.53
    assert ardee.ipo_type == "Mainboard"
    assert ardee.status == "Open"


def test_parse_gmp_table_handles_zero_percent():
    html = FIXTURE.read_text()
    rows = parse_gmp_table(html)
    aegeus = next(r for r in rows if r.ipo_name == "Aegeus Technologies")
    assert aegeus.listing_gain_pct == 0.0


def test_filter_open_mainboard_excludes_sme_and_non_open():
    html = FIXTURE.read_text()
    rows = parse_gmp_table(html)
    filtered = filter_open_mainboard(rows)
    names = {r.ipo_name for r in filtered}
    assert names == {"Ardee Industries", "Milky Mist Dairy Food"}


def test_fetch_gmp_html_requests_correct_url():
    with patch("iposcan.sources.gmp.requests.get") as mock_get:
        mock_get.return_value.text = "<html></html>"
        mock_get.return_value.raise_for_status.return_value = None
        result = fetch_gmp_html()
        assert result == "<html></html>"
        assert mock_get.call_args.args[0] == GMP_URL
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_gmp.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'iposcan.sources.gmp'`

- [ ] **Step 4: Implement `gmp.py`**

```python
"""Fetch and parse IPO grey market premium (GMP) data from ipowatch.in."""
from __future__ import annotations

import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from iposcan.html_utils import find_table_by_header_keywords, parse_number

GMP_URL = "https://ipowatch.in/ipo-grey-market-premium-latest-ipo-gmp/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
REQUEST_TIMEOUT_SECONDS = 30

_PCT_RE = re.compile(r"\(([-\d.]+)%\)")


@dataclass(frozen=True)
class GmpRow:
    ipo_name: str
    gmp_rupees: float
    price_band: str
    listing_gain_pct: float
    date_range: str
    ipo_type: str
    status: str


def fetch_gmp_html() -> str:
    response = requests.get(
        GMP_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.text


def _parse_listing_gain_pct(text: str) -> float:
    match = _PCT_RE.search(text)
    return float(match.group(1)) if match else 0.0


def parse_gmp_table(html: str) -> list[GmpRow]:
    soup = BeautifulSoup(html, "html.parser")
    table = find_table_by_header_keywords(soup, ["IPO Name", "GMP", "Status"])
    if table is None:
        raise ValueError("GMP table not found on page")

    rows: list[GmpRow] = []
    for tr in table.find_all("tr")[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 8:
            continue
        rows.append(
            GmpRow(
                ipo_name=cells[0],
                gmp_rupees=parse_number(cells[1]),
                price_band=cells[3],
                listing_gain_pct=_parse_listing_gain_pct(cells[4]),
                date_range=cells[5],
                ipo_type=cells[6],
                status=cells[7],
            )
        )
    return rows


def filter_open_mainboard(rows: list[GmpRow]) -> list[GmpRow]:
    return [r for r in rows if r.ipo_type == "Mainboard" and r.status == "Open"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_gmp.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/iposcan/sources/gmp.py tests/test_gmp.py tests/fixtures/gmp.html
git commit -m "feat: add GMP data source"
```

---

## Task 5: Financials Source

**Files:**
- Create: `src/iposcan/sources/financials.py`
- Create: `tests/fixtures/chittorgarh_dashboard.html`
- Create: `tests/fixtures/chittorgarh_financials_growing.html`
- Create: `tests/fixtures/chittorgarh_financials_declining.html`
- Create: `tests/fixtures/chittorgarh_financials_missing.html`
- Test: `tests/test_financials.py`

**Interfaces:**
- Consumes: `find_table_by_header_keywords`, `parse_number` from `iposcan.html_utils` (Task 2).
- Produces: `FinancialsResult` dataclass (`available: bool`, `profit_after_tax: list[float] | None`, newest period first), `fetch_dashboard_html() -> str`, `parse_dashboard_links(html: str) -> dict[str, str]`, `fetch_financials_html(path: str) -> str`, `parse_financials(html: str) -> FinancialsResult`, `normalize_company_name(name: str) -> str`, `find_detail_path(company_name: str, links: dict[str, str]) -> str | None`, `get_financials_for(company_name: str, links: dict[str, str]) -> FinancialsResult` — consumed by `main.py` (Task 9).

- [ ] **Step 1: Create fixtures**

`tests/fixtures/chittorgarh_dashboard.html`:
```html
<html><body>
<table>
<thead><tr><th>Company</th><th>Issue Date</th></tr></thead>
<tbody>
<tr><td><a href="/ipo/ardee-industries-ipo/2860/">Ardee Industries</a></td><td>5-Aug-2026</td></tr>
<tr><td><a href="/ipo/milky-mist-dairy-food-ipo/2541/">Milky Mist Dairy Food</a></td><td>11-Aug-2026</td></tr>
</tbody>
</table>
</body></html>
```

`tests/fixtures/chittorgarh_financials_growing.html`:
```html
<html><body>
<h2>Company Financials (Restated)</h2>
<table class="table text-nowrap striped my-0 table-hover">
<tr><td>Period Ended</td><td>31 Mar 2026</td><td>31 Mar 2025</td><td>31 Mar 2024</td></tr>
<tr><td>Assets</td><td>363.33</td><td>262.06</td><td>196.12</td></tr>
<tr><td>Total Income</td><td>1,168.88</td><td>743.53</td><td>463.39</td></tr>
<tr><td>Profit After Tax</td><td>84.68</td><td>33.27</td><td>8.95</td></tr>
<tr><td>EBITDA</td><td>147.08</td><td>65.93</td><td>28.06</td></tr>
</table>
</body></html>
```

`tests/fixtures/chittorgarh_financials_declining.html`:
```html
<html><body>
<h2>Company Financials (Restated)</h2>
<table class="table text-nowrap striped my-0 table-hover">
<tr><td>Period Ended</td><td>31 Mar 2026</td><td>31 Mar 2025</td><td>31 Mar 2024</td></tr>
<tr><td>Profit After Tax</td><td>5.00</td><td>10.00</td><td>20.00</td></tr>
</table>
</body></html>
```

`tests/fixtures/chittorgarh_financials_missing.html`:
```html
<html><body>
<h2>About the Company</h2>
<p>No financials section on this page.</p>
</body></html>
```

- [ ] **Step 2: Write the failing test**

`tests/test_financials.py`:
```python
from pathlib import Path
from unittest.mock import patch

from iposcan.sources.financials import (
    DASHBOARD_URL,
    fetch_dashboard_html,
    fetch_financials_html,
    find_detail_path,
    get_financials_for,
    normalize_company_name,
    parse_dashboard_links,
    parse_financials,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_dashboard_links_maps_name_to_path():
    html = (FIXTURES / "chittorgarh_dashboard.html").read_text()
    links = parse_dashboard_links(html)
    assert links["Ardee Industries"] == "/ipo/ardee-industries-ipo/2860/"
    assert links["Milky Mist Dairy Food"] == "/ipo/milky-mist-dairy-food-ipo/2541/"


def test_parse_financials_growing_profit():
    html = (FIXTURES / "chittorgarh_financials_growing.html").read_text()
    result = parse_financials(html)
    assert result.available is True
    assert result.profit_after_tax == [84.68, 33.27, 8.95]


def test_parse_financials_declining_profit():
    html = (FIXTURES / "chittorgarh_financials_declining.html").read_text()
    result = parse_financials(html)
    assert result.available is True
    assert result.profit_after_tax == [5.00, 10.00, 20.00]


def test_parse_financials_missing_section():
    html = (FIXTURES / "chittorgarh_financials_missing.html").read_text()
    result = parse_financials(html)
    assert result.available is False
    assert result.profit_after_tax is None


def test_normalize_company_name_strips_suffixes_and_punctuation():
    assert normalize_company_name("Ardee Industries Limited") == "ardee industries"
    assert normalize_company_name("Ardee Industries Ltd.") == "ardee industries"
    assert normalize_company_name("Ardee Industries") == "ardee industries"


def test_find_detail_path_exact_match():
    links = {"Ardee Industries": "/ipo/ardee-industries-ipo/2860/"}
    assert find_detail_path("Ardee Industries", links) == "/ipo/ardee-industries-ipo/2860/"


def test_find_detail_path_fuzzy_match():
    links = {"Milky Mist Dairy Food": "/ipo/milky-mist-dairy-food-ipo/2541/"}
    assert find_detail_path("Milky Mist", links) == "/ipo/milky-mist-dairy-food-ipo/2541/"


def test_find_detail_path_no_match_returns_none():
    links = {"Ardee Industries": "/ipo/ardee-industries-ipo/2860/"}
    assert find_detail_path("Totally Unrelated Co", links) is None


def test_get_financials_for_unknown_company_returns_unavailable():
    result = get_financials_for("No Such Company", {})
    assert result.available is False
    assert result.profit_after_tax is None


def test_get_financials_for_fetch_failure_returns_unavailable():
    links = {"Ardee Industries": "/ipo/ardee-industries-ipo/2860/"}
    with patch(
        "iposcan.sources.financials.fetch_financials_html",
        side_effect=RuntimeError("network error"),
    ):
        result = get_financials_for("Ardee Industries", links)
        assert result.available is False
        assert result.profit_after_tax is None


def test_fetch_dashboard_html_requests_correct_url():
    with patch("iposcan.sources.financials.requests.get") as mock_get:
        mock_get.return_value.text = "<html></html>"
        mock_get.return_value.raise_for_status.return_value = None
        result = fetch_dashboard_html()
        assert result == "<html></html>"
        assert mock_get.call_args.args[0] == DASHBOARD_URL


def test_fetch_financials_html_builds_full_url():
    with patch("iposcan.sources.financials.requests.get") as mock_get:
        mock_get.return_value.text = "<html></html>"
        mock_get.return_value.raise_for_status.return_value = None
        fetch_financials_html("/ipo/ardee-industries-ipo/2860/")
        called_url = mock_get.call_args.args[0]
        assert called_url == "https://www.chittorgarh.com/ipo/ardee-industries-ipo/2860/"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_financials.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'iposcan.sources.financials'`

- [ ] **Step 4: Implement `financials.py`**

```python
"""Fetch and parse pre-IPO company financials from chittorgarh.com.

Chittorgarh does not expose a stable IPO-name-to-URL mapping, so this module
first scrapes the dashboard listing to build a name -> detail-page-path map,
then fetches the matched detail page's "Company Financials (Restated)" table.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from iposcan.html_utils import find_table_by_header_keywords, parse_number

DASHBOARD_URL = "https://www.chittorgarh.com/ipo/ipo_dashboard.asp"
DETAIL_BASE_URL = "https://www.chittorgarh.com"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
REQUEST_TIMEOUT_SECONDS = 30

_SUFFIXES = (" limited", " ltd.", " ltd", " ipo")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class FinancialsResult:
    available: bool
    profit_after_tax: list[float] | None  # newest period first


def fetch_dashboard_html() -> str:
    response = requests.get(
        DASHBOARD_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.text


def fetch_financials_html(path: str) -> str:
    response = requests.get(
        f"{DETAIL_BASE_URL}{path}",
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.text


def parse_dashboard_links(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    table = find_table_by_header_keywords(soup, ["Company", "Issue Date"])
    if table is None:
        return {}

    links: dict[str, str] = {}
    for anchor in table.find_all("a", href=True):
        href = anchor["href"]
        name = anchor.get_text(strip=True)
        if href.startswith("/ipo/") and name:
            links[name] = href
    return links


def parse_financials(html: str) -> FinancialsResult:
    soup = BeautifulSoup(html, "html.parser")
    heading = next(
        (h for h in soup.find_all(["h2", "h3"]) if "financ" in h.get_text(strip=True).lower()),
        None,
    )
    if heading is None:
        return FinancialsResult(available=False, profit_after_tax=None)

    table = heading.find_next("table")
    if table is None:
        return FinancialsResult(available=False, profit_after_tax=None)

    pat_cells: list[str] | None = None
    for tr in table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if cells and cells[0].strip().lower() == "profit after tax":
            pat_cells = cells[1:]
            break

    if not pat_cells:
        return FinancialsResult(available=False, profit_after_tax=None)

    try:
        values = [parse_number(v) for v in pat_cells]
    except ValueError:
        return FinancialsResult(available=False, profit_after_tax=None)

    return FinancialsResult(available=True, profit_after_tax=values)


def normalize_company_name(name: str) -> str:
    text = name.lower()
    for suffix in _SUFFIXES:
        text = text.replace(suffix, "")
    return _NON_ALNUM_RE.sub(" ", text).strip()


def find_detail_path(company_name: str, links: dict[str, str]) -> str | None:
    target = normalize_company_name(company_name)

    for name, path in links.items():
        if normalize_company_name(name) == target:
            return path

    for name, path in links.items():
        normalized = normalize_company_name(name)
        if target in normalized or normalized in target:
            return path

    return None


def get_financials_for(company_name: str, links: dict[str, str]) -> FinancialsResult:
    path = find_detail_path(company_name, links)
    if path is None:
        return FinancialsResult(available=False, profit_after_tax=None)

    try:
        html = fetch_financials_html(path)
    except Exception:
        return FinancialsResult(available=False, profit_after_tax=None)

    return parse_financials(html)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_financials.py -v`
Expected: 12 passed

- [ ] **Step 6: Commit**

```bash
git add src/iposcan/sources/financials.py tests/test_financials.py tests/fixtures/chittorgarh_dashboard.html tests/fixtures/chittorgarh_financials_growing.html tests/fixtures/chittorgarh_financials_declining.html tests/fixtures/chittorgarh_financials_missing.html
git commit -m "feat: add financials data source"
```

---

## Task 6: Criteria Evaluation

**Files:**
- Create: `src/iposcan/criteria.py`
- Test: `tests/test_criteria.py`

**Interfaces:**
- Consumes: `SubscriptionRow` (Task 3), `GmpRow` (Task 4), `FinancialsResult` (Task 5).
- Produces: `IpoEvaluation` dataclass (`ipo_name: str`, `qib: float`, `nii: float`, `retail: float`, `total: float`, `gmp_rupees: float`, `listing_gain_pct: float`, `profit_growing: bool | None`, `passes: bool`, `reasons: list[str]`), `is_profit_growing(pat_by_period: list[float] | None) -> bool | None`, `evaluate(subscription: SubscriptionRow, gmp: GmpRow, financials: FinancialsResult) -> IpoEvaluation` — consumed by `main.py` (Task 9) and `notify.py` (Task 8).

- [ ] **Step 1: Write the failing test**

`tests/test_criteria.py`:
```python
from iposcan.criteria import IpoEvaluation, evaluate, is_profit_growing
from iposcan.sources.financials import FinancialsResult
from iposcan.sources.gmp import GmpRow
from iposcan.sources.subscription import SubscriptionRow


def _sub(total: float) -> SubscriptionRow:
    return SubscriptionRow(
        ipo_name="Ardee Industries",
        ipo_type="Mainboard",
        closing_date="August 7, 2026",
        qib=1.13,
        nii=5.58,
        retail=3.42,
        total=total,
    )


def _gmp(listing_gain_pct: float) -> GmpRow:
    return GmpRow(
        ipo_name="Ardee Industries",
        gmp_rupees=13.0,
        price_band="₹53",
        listing_gain_pct=listing_gain_pct,
        date_range="5-7 August",
        ipo_type="Mainboard",
        status="Open",
    )


def test_is_profit_growing_true_when_strictly_increasing():
    assert is_profit_growing([84.68, 33.27, 8.95]) is True


def test_is_profit_growing_false_when_not_strictly_increasing():
    assert is_profit_growing([5.0, 10.0, 20.0]) is False


def test_is_profit_growing_none_when_missing():
    assert is_profit_growing(None) is None
    assert is_profit_growing([1.0, 2.0]) is None


def test_evaluate_passes_when_subscription_and_gmp_both_meet_threshold():
    result = evaluate(_sub(total=3.23), _gmp(24.53), FinancialsResult(True, [84.68, 33.27, 8.95]))
    assert result.passes is True
    assert result.profit_growing is True
    assert result.reasons == []


def test_evaluate_passes_even_when_financials_unknown():
    result = evaluate(_sub(total=3.23), _gmp(24.53), FinancialsResult(False, None))
    assert result.passes is True
    assert result.profit_growing is None
    assert "verify manually" in result.reasons[0].lower()


def test_evaluate_fails_when_subscription_below_threshold():
    result = evaluate(_sub(total=2.9), _gmp(24.53), FinancialsResult(True, [84.68, 33.27, 8.95]))
    assert result.passes is False
    assert any("subscription" in r.lower() for r in result.reasons)


def test_evaluate_fails_when_gmp_below_threshold():
    result = evaluate(_sub(total=3.23), _gmp(9.9), FinancialsResult(True, [84.68, 33.27, 8.95]))
    assert result.passes is False
    assert any("listing gain" in r.lower() for r in result.reasons)


def test_evaluate_carries_through_breakdown_fields():
    result = evaluate(_sub(total=3.23), _gmp(24.53), FinancialsResult(False, None))
    assert isinstance(result, IpoEvaluation)
    assert result.ipo_name == "Ardee Industries"
    assert result.qib == 1.13
    assert result.nii == 5.58
    assert result.retail == 3.42
    assert result.total == 3.23
    assert result.gmp_rupees == 13.0
    assert result.listing_gain_pct == 24.53
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_criteria.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'iposcan.criteria'`

- [ ] **Step 3: Implement `criteria.py`**

```python
"""Evaluate parsed IPO data against the scanner's go/no-go criteria."""
from __future__ import annotations

from dataclasses import dataclass, field

from iposcan.sources.financials import FinancialsResult
from iposcan.sources.gmp import GmpRow
from iposcan.sources.subscription import SubscriptionRow

MIN_TOTAL_SUBSCRIPTION = 3.0
MIN_LISTING_GAIN_PCT = 10.0
REQUIRED_PROFIT_PERIODS = 3


@dataclass(frozen=True)
class IpoEvaluation:
    ipo_name: str
    qib: float
    nii: float
    retail: float
    total: float
    gmp_rupees: float
    listing_gain_pct: float
    profit_growing: bool | None
    passes: bool
    reasons: list[str] = field(default_factory=list)


def is_profit_growing(pat_by_period: list[float] | None) -> bool | None:
    """True/False if 3 periods of PAT are available (newest first), else None (unknown)."""
    if not pat_by_period or len(pat_by_period) < REQUIRED_PROFIT_PERIODS:
        return None
    newest, middle, oldest = pat_by_period[0], pat_by_period[1], pat_by_period[2]
    return newest > middle > oldest


def evaluate(
    subscription: SubscriptionRow,
    gmp: GmpRow,
    financials: FinancialsResult,
) -> IpoEvaluation:
    reasons: list[str] = []

    subscription_ok = subscription.total >= MIN_TOTAL_SUBSCRIPTION
    if not subscription_ok:
        reasons.append(
            f"Total subscription {subscription.total}x below {MIN_TOTAL_SUBSCRIPTION}x"
        )

    gmp_ok = gmp.listing_gain_pct >= MIN_LISTING_GAIN_PCT
    if not gmp_ok:
        reasons.append(
            f"Listing gain {gmp.listing_gain_pct}% below {MIN_LISTING_GAIN_PCT}%"
        )

    pat = financials.profit_after_tax if financials.available else None
    profit_growing = is_profit_growing(pat)
    if profit_growing is False:
        reasons.append("Profit not growing across last 3 reported periods")
    elif profit_growing is None:
        reasons.append("Profit trend unknown - verify manually")

    return IpoEvaluation(
        ipo_name=subscription.ipo_name,
        qib=subscription.qib,
        nii=subscription.nii,
        retail=subscription.retail,
        total=subscription.total,
        gmp_rupees=gmp.gmp_rupees,
        listing_gain_pct=gmp.listing_gain_pct,
        profit_growing=profit_growing,
        passes=subscription_ok and gmp_ok,
        reasons=reasons,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_criteria.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/iposcan/criteria.py tests/test_criteria.py
git commit -m "feat: add criteria evaluation logic"
```

---

## Task 7: State (Dedup) Store

**Files:**
- Create: `src/iposcan/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Produces: `load_alerted(path: Path) -> set[str]`, `save_alerted(path: Path, alerted: set[str]) -> None` — consumed by `main.py` (Task 9).

- [ ] **Step 1: Write the failing test**

`tests/test_state.py`:
```python
import json
from pathlib import Path

from iposcan.state import load_alerted, save_alerted


def test_load_alerted_returns_empty_set_when_file_missing(tmp_path: Path):
    assert load_alerted(tmp_path / "missing.json") == set()


def test_load_alerted_reads_existing_names(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"alerted": ["Ardee Industries", "Milky Mist"]}))
    assert load_alerted(path) == {"Ardee Industries", "Milky Mist"}


def test_save_alerted_writes_sorted_json(tmp_path: Path):
    path = tmp_path / "nested" / "state.json"
    save_alerted(path, {"Zeta Corp", "Ardee Industries"})
    data = json.loads(path.read_text())
    assert data == {"alerted": ["Ardee Industries", "Zeta Corp"]}


def test_round_trip_through_load_and_save(tmp_path: Path):
    path = tmp_path / "state.json"
    save_alerted(path, {"Foo", "Bar"})
    assert load_alerted(path) == {"Foo", "Bar"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'iposcan.state'`

- [ ] **Step 3: Implement `state.py`**

```python
"""Tracks which IPOs have already triggered an alert, to avoid re-alerting."""
from __future__ import annotations

import json
from pathlib import Path


def load_alerted(path: Path) -> set[str]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text())
    return set(data.get("alerted", []))


def save_alerted(path: Path, alerted: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"alerted": sorted(alerted)}, indent=2) + "\n")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_state.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/iposcan/state.py tests/test_state.py
git commit -m "feat: add alert dedup state store"
```

---

## Task 8: Telegram Notifier

**Files:**
- Create: `src/iposcan/notify.py`
- Test: `tests/test_notify.py`

**Interfaces:**
- Consumes: `IpoEvaluation` (Task 6).
- Produces: `format_alert(evaluation: IpoEvaluation) -> str`, `send_telegram_message(token: str, chat_id: str, text: str) -> None` — consumed by `main.py` (Task 9).

- [ ] **Step 1: Write the failing test**

`tests/test_notify.py`:
```python
from unittest.mock import patch

from iposcan.criteria import IpoEvaluation
from iposcan.notify import TELEGRAM_API_URL, format_alert, send_telegram_message


def _evaluation(profit_growing: bool | None) -> IpoEvaluation:
    return IpoEvaluation(
        ipo_name="Ardee Industries",
        qib=1.13,
        nii=5.58,
        retail=3.42,
        total=3.23,
        gmp_rupees=13.0,
        listing_gain_pct=24.53,
        profit_growing=profit_growing,
        passes=True,
        reasons=[],
    )


def test_format_alert_includes_name_and_breakdown():
    text = format_alert(_evaluation(True))
    assert "Ardee Industries" in text
    assert "QIB 1.13x" in text
    assert "NII 5.58x" in text
    assert "Retail 3.42x" in text
    assert "Total 3.23x" in text
    assert "24.53%" in text
    assert "Growing" in text


def test_format_alert_shows_unknown_profit_trend():
    text = format_alert(_evaluation(None))
    assert "verify manually" in text.lower()


def test_format_alert_shows_declining_profit_trend():
    text = format_alert(_evaluation(False))
    assert "not growing" in text.lower()


def test_send_telegram_message_posts_to_correct_url():
    with patch("iposcan.notify.requests.post") as mock_post:
        mock_post.return_value.raise_for_status.return_value = None
        send_telegram_message("TOKEN123", "CHAT456", "hello")
        called_url = mock_post.call_args.args[0]
        called_data = mock_post.call_args.kwargs["data"]
        assert called_url == TELEGRAM_API_URL.format(token="TOKEN123")
        assert called_data == {"chat_id": "CHAT456", "text": "hello"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_notify.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'iposcan.notify'`

- [ ] **Step 3: Implement `notify.py`**

```python
"""Format and send Telegram alerts for IPOs that pass the criteria."""
from __future__ import annotations

import requests

from iposcan.criteria import IpoEvaluation

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
REQUEST_TIMEOUT_SECONDS = 30

_PROFIT_LABELS: dict[bool | None, str] = {
    True: "📈 Growing (3yr)",
    False: "📉 Not growing",
    None: "⚠️ Unknown - verify manually",
}


def format_alert(evaluation: IpoEvaluation) -> str:
    return (
        f"🎯 IPO Alert: {evaluation.ipo_name}\n\n"
        f"Subscription — QIB {evaluation.qib}x | NII {evaluation.nii}x | "
        f"Retail {evaluation.retail}x | Total {evaluation.total}x\n"
        f"GMP: ₹{evaluation.gmp_rupees} (~{evaluation.listing_gain_pct}% listing gain)\n"
        f"Profit trend: {_PROFIT_LABELS[evaluation.profit_growing]}"
    )


def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    url = TELEGRAM_API_URL.format(token=token)
    response = requests.post(
        url,
        data={"chat_id": chat_id, "text": text},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_notify.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/iposcan/notify.py tests/test_notify.py
git commit -m "feat: add Telegram notifier"
```

---

## Task 9: Main Orchestrator, GitHub Actions Workflow & README

**Files:**
- Create: `src/iposcan/main.py`
- Test: `tests/test_main.py`
- Create: `.github/workflows/scan.yml`
- Create: `README.md`

**Interfaces:**
- Consumes: everything from Tasks 3-8.
- Produces: `run() -> None`, the entry point invoked by the GitHub Actions workflow via `uv run python -m iposcan.main`.

- [ ] **Step 1: Write the failing test**

`tests/test_main.py`:
```python
from unittest.mock import patch

from iposcan.main import run
from iposcan.sources.financials import FinancialsResult
from iposcan.sources.gmp import GmpRow
from iposcan.sources.subscription import SubscriptionRow

SUB_ROW = SubscriptionRow(
    ipo_name="Ardee Industries",
    ipo_type="Mainboard",
    closing_date="August 7, 2026",
    qib=1.13,
    nii=5.58,
    retail=3.42,
    total=3.23,
)
GMP_ROW = GmpRow(
    ipo_name="Ardee Industries",
    gmp_rupees=13.0,
    price_band="₹53",
    listing_gain_pct=24.53,
    date_range="5-7 August",
    ipo_type="Mainboard",
    status="Open",
)


@patch("iposcan.main.notify.send_telegram_message")
@patch("iposcan.main.financials.get_financials_for")
@patch("iposcan.main.financials.parse_dashboard_links", return_value={})
@patch("iposcan.main.financials.fetch_dashboard_html", return_value="<html></html>")
@patch("iposcan.main.gmp.filter_open_mainboard", return_value=[GMP_ROW])
@patch("iposcan.main.gmp.parse_gmp_table", return_value=[GMP_ROW])
@patch("iposcan.main.gmp.fetch_gmp_html", return_value="<html></html>")
@patch("iposcan.main.subscription.parse_subscription_table", return_value=[SUB_ROW])
@patch("iposcan.main.subscription.fetch_subscription_html", return_value="<html></html>")
@patch("iposcan.main.state.load_alerted", return_value=set())
@patch("iposcan.main.state.save_alerted")
def test_run_sends_alert_and_saves_state_for_new_pass(
    mock_save_alerted,
    mock_load_alerted,
    mock_fetch_sub,
    mock_parse_sub,
    mock_fetch_gmp,
    mock_parse_gmp,
    mock_filter_gmp,
    mock_fetch_dashboard,
    mock_parse_links,
    mock_get_financials,
    mock_send,
    monkeypatch,
):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CHAT")
    mock_get_financials.return_value = FinancialsResult(True, [84.68, 33.27, 8.95])

    run()

    mock_send.assert_called_once()
    sent_text = mock_send.call_args.args[2]
    assert "Ardee Industries" in sent_text
    mock_save_alerted.assert_called_once()
    saved_names = mock_save_alerted.call_args.args[1]
    assert saved_names == {"Ardee Industries"}


@patch("iposcan.main.notify.send_telegram_message")
@patch("iposcan.main.financials.get_financials_for")
@patch("iposcan.main.financials.parse_dashboard_links", return_value={})
@patch("iposcan.main.financials.fetch_dashboard_html", return_value="<html></html>")
@patch("iposcan.main.gmp.filter_open_mainboard", return_value=[GMP_ROW])
@patch("iposcan.main.gmp.parse_gmp_table", return_value=[GMP_ROW])
@patch("iposcan.main.gmp.fetch_gmp_html", return_value="<html></html>")
@patch("iposcan.main.subscription.parse_subscription_table", return_value=[SUB_ROW])
@patch("iposcan.main.subscription.fetch_subscription_html", return_value="<html></html>")
@patch("iposcan.main.state.load_alerted", return_value={"Ardee Industries"})
@patch("iposcan.main.state.save_alerted")
def test_run_skips_already_alerted_ipo(
    mock_save_alerted,
    mock_load_alerted,
    mock_fetch_sub,
    mock_parse_sub,
    mock_fetch_gmp,
    mock_parse_gmp,
    mock_filter_gmp,
    mock_fetch_dashboard,
    mock_parse_links,
    mock_get_financials,
    mock_send,
    monkeypatch,
):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CHAT")

    run()

    mock_send.assert_not_called()
    mock_save_alerted.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'iposcan.main'`

- [ ] **Step 3: Implement `main.py`**

```python
"""Daily orchestration: fetch, evaluate, dedup, and alert."""
from __future__ import annotations

import os
from pathlib import Path

from iposcan import criteria, notify, state
from iposcan.sources import financials, gmp, subscription

STATE_PATH = Path("state/alerted_ipos.json")


def run() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    sub_rows = subscription.parse_subscription_table(subscription.fetch_subscription_html())
    sub_by_name = {row.ipo_name: row for row in sub_rows}

    gmp_rows = gmp.parse_gmp_table(gmp.fetch_gmp_html())
    open_mainboard = gmp.filter_open_mainboard(gmp_rows)

    dashboard_links = financials.parse_dashboard_links(financials.fetch_dashboard_html())

    alerted = state.load_alerted(STATE_PATH)
    newly_alerted: set[str] = set()

    for gmp_row in open_mainboard:
        if gmp_row.ipo_name in alerted:
            continue

        sub_row = sub_by_name.get(gmp_row.ipo_name)
        if sub_row is None:
            continue

        fin_result = financials.get_financials_for(gmp_row.ipo_name, dashboard_links)
        evaluation = criteria.evaluate(sub_row, gmp_row, fin_result)

        if evaluation.passes:
            notify.send_telegram_message(token, chat_id, notify.format_alert(evaluation))
            newly_alerted.add(gmp_row.ipo_name)

    if newly_alerted:
        state.save_alerted(STATE_PATH, alerted | newly_alerted)


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_main.py -v`
Expected: 2 passed

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: all tests across every module pass (≈35 total).

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 6: Create the GitHub Actions workflow**

`.github/workflows/scan.yml`:
```yaml
name: Daily IPO Scan

on:
  schedule:
    - cron: "30 12 * * *"
  workflow_dispatch: {}

permissions:
  contents: write

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Install dependencies
        run: uv sync --frozen

      - name: Run scanner
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: uv run python -m iposcan.main

      - name: Commit updated state
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add state/alerted_ipos.json
          git diff --staged --quiet || git commit -m "chore: update alerted IPOs state [skip ci]"
          git push
```

- [ ] **Step 7: Create the README**

`README.md`:
```markdown
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
```

- [ ] **Step 8: Commit**

```bash
git add src/iposcan/main.py tests/test_main.py .github/workflows/scan.yml README.md
git commit -m "feat: wire orchestrator, GitHub Actions workflow, and README"
```

---

## Self-Review Notes

- **Spec coverage:** oversubscription filter (Task 6), GMP filter (Task 6), non-blocking profit growth (Tasks 5-6), full QIB/NII/Retail/Total breakdown in alerts (Task 8), Mainboard-only + open-window scope (Task 4's `filter_open_mainboard`), daily schedule + state dedup (Task 9), Telegram delivery (Task 8) — all covered.
- **Type consistency:** `SubscriptionRow`, `GmpRow`, `FinancialsResult`, `IpoEvaluation` field names/types verified identical across every task that constructs or consumes them.
- **No placeholders:** every step has runnable code, real fixture content (based on actual verified page structure), and exact commands with expected output.

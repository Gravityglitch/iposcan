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

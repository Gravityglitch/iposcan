"""Fetch and parse IPO grey market premium (GMP) data from ipowatch.in."""
from __future__ import annotations

import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from iposcan.html_utils import parse_number

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


def _find_table_after_heading(soup: BeautifulSoup, heading_text: str) -> Tag | None:
    heading = next(
        (h for h in soup.find_all(["h2", "h3"]) if h.get_text(strip=True) == heading_text),
        None,
    )
    return heading.find_next("table") if heading is not None else None


def _parse_table_rows(table: Tag, ipo_type: str) -> list[GmpRow]:
    rows: list[GmpRow] = []
    for tr in table.find_all("tr")[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 7:
            continue
        try:
            rows.append(
                GmpRow(
                    ipo_name=cells[0],
                    gmp_rupees=parse_number(cells[1]),
                    price_band=cells[3],
                    listing_gain_pct=_parse_listing_gain_pct(cells[4]),
                    date_range=cells[5],
                    ipo_type=ipo_type,
                    status=cells[6],
                )
            )
        except ValueError:
            continue
    return rows


def parse_gmp_table(html: str) -> list[GmpRow]:
    """Parse the separate Mainboard and SME GMP tables into one combined list.

    ipowatch.in publishes these as two distinct tables (each under their own
    heading) rather than one table with a Mainboard/SME column, so the
    ipo_type has to be attached from which table a row came from.
    """
    soup = BeautifulSoup(html, "html.parser")

    mainboard_table = _find_table_after_heading(soup, "Mainboard IPO GMP")
    sme_table = _find_table_after_heading(soup, "SME IPO GMP")
    if mainboard_table is None and sme_table is None:
        raise ValueError("GMP tables not found on page")

    rows: list[GmpRow] = []
    if mainboard_table is not None:
        rows += _parse_table_rows(mainboard_table, "Mainboard")
    if sme_table is not None:
        rows += _parse_table_rows(sme_table, "SME")
    return rows


def filter_open_mainboard(rows: list[GmpRow]) -> list[GmpRow]:
    return [r for r in rows if r.ipo_type == "Mainboard" and r.status == "Open"]

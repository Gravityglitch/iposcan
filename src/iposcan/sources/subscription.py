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
        try:
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
        except ValueError:
            continue
    return rows

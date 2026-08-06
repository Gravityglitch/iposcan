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

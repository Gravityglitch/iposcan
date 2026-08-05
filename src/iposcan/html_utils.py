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

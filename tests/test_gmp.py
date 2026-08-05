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

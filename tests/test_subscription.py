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

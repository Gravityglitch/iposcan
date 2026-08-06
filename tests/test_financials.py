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

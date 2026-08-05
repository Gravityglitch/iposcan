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

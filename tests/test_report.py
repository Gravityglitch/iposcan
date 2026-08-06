from unittest.mock import patch

from iposcan.criteria import evaluate
from iposcan.report import (
    IpoReportRow,
    format_report,
    format_telegram_report,
    gather_active_mainboard_ipos,
    run,
    send_report_to_telegram,
)
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


@patch("iposcan.report.financials.get_financials_for")
@patch("iposcan.report.financials.parse_dashboard_links", return_value={})
@patch("iposcan.report.financials.fetch_dashboard_html", return_value="<html></html>")
@patch("iposcan.report.gmp.filter_open_mainboard", return_value=[GMP_ROW])
@patch("iposcan.report.gmp.parse_gmp_table", return_value=[GMP_ROW])
@patch("iposcan.report.gmp.fetch_gmp_html", return_value="<html></html>")
@patch("iposcan.report.subscription.parse_subscription_table", return_value=[SUB_ROW])
@patch("iposcan.report.subscription.fetch_subscription_html", return_value="<html></html>")
def test_gather_active_mainboard_ipos_evaluates_each_open_ipo(
    mock_fetch_sub,
    mock_parse_sub,
    mock_fetch_gmp,
    mock_parse_gmp,
    mock_filter_gmp,
    mock_fetch_dashboard,
    mock_parse_links,
    mock_get_financials,
):
    mock_get_financials.return_value = FinancialsResult(True, [84.68, 33.27, 8.95])

    rows = gather_active_mainboard_ipos()

    assert len(rows) == 1
    assert rows[0].evaluation.ipo_name == "Ardee Industries"
    assert rows[0].evaluation.passes is True


@patch("iposcan.report.financials.get_financials_for")
@patch("iposcan.report.financials.parse_dashboard_links", return_value={})
@patch("iposcan.report.financials.fetch_dashboard_html", return_value="<html></html>")
@patch("iposcan.report.gmp.filter_open_mainboard", return_value=[GMP_ROW])
@patch("iposcan.report.gmp.parse_gmp_table", return_value=[GMP_ROW])
@patch("iposcan.report.gmp.fetch_gmp_html", return_value="<html></html>")
@patch("iposcan.report.subscription.parse_subscription_table", return_value=[])
@patch("iposcan.report.subscription.fetch_subscription_html", return_value="<html></html>")
def test_gather_skips_ipo_missing_from_subscription_table(
    mock_fetch_sub,
    mock_parse_sub,
    mock_fetch_gmp,
    mock_parse_gmp,
    mock_filter_gmp,
    mock_fetch_dashboard,
    mock_parse_links,
    mock_get_financials,
):
    rows = gather_active_mainboard_ipos()
    assert rows == []
    mock_get_financials.assert_not_called()


def test_format_report_empty_list():
    report = format_report([])
    assert "No open Mainboard IPOs found" in report


def test_format_report_includes_ipo_row():
    fin = FinancialsResult(
        True,
        [84.68, 33.27, 8.95],
        total_income=[1168.88, 743.53, 463.39],
        period_ended=["31 Mar 2026", "31 Mar 2025", "31 Mar 2024"],
    )
    row = IpoReportRow(evaluation=evaluate(SUB_ROW, GMP_ROW, fin), financials=fin)
    report = format_report([row])

    assert "Ardee Industries" in report
    assert "3.23x" in report
    assert "24.53%" in report
    assert "✅" in report
    assert "| 31 Mar 2026 | ₹84.68 | ₹1168.88 |" in report


def test_format_telegram_report_empty_list():
    assert format_telegram_report([]) == "No open Mainboard IPOs found."


def test_format_telegram_report_includes_each_ipo():
    fin = FinancialsResult(True, [84.68, 33.27, 8.95])
    row = IpoReportRow(evaluation=evaluate(SUB_ROW, GMP_ROW, fin), financials=fin)

    text = format_telegram_report([row])

    assert "1 active Mainboard IPO" in text
    assert "Ardee Industries" in text
    assert "QIB: 1.13x" in text
    assert "84.68" in text


@patch("iposcan.report.notify.send_telegram_message")
def test_send_report_to_telegram_posts_formatted_text(mock_send):
    fin = FinancialsResult(True, [84.68, 33.27, 8.95])
    row = IpoReportRow(evaluation=evaluate(SUB_ROW, GMP_ROW, fin), financials=fin)

    send_report_to_telegram("TOKEN", "CHAT", [row])

    mock_send.assert_called_once_with(
        "TOKEN", "CHAT", format_telegram_report([row]), parse_mode="Markdown"
    )


@patch("iposcan.report.load_dotenv")
@patch("iposcan.report.gather_active_mainboard_ipos")
def test_run_writes_to_github_step_summary(
    mock_gather, mock_load_dotenv, tmp_path, monkeypatch, capsys
):
    fin = FinancialsResult(True, [84.68, 33.27, 8.95])
    row = IpoReportRow(evaluation=evaluate(SUB_ROW, GMP_ROW, fin), financials=fin)
    mock_gather.return_value = [row]

    summary_file = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    run()

    assert "Ardee Industries" in summary_file.read_text()
    assert "Ardee Industries" in capsys.readouterr().out


@patch("iposcan.report.send_report_to_telegram")
@patch("iposcan.report.load_dotenv")
@patch("iposcan.report.gather_active_mainboard_ipos")
def test_run_skips_telegram_when_credentials_missing(
    mock_gather, mock_load_dotenv, mock_send_report, tmp_path, monkeypatch
):
    fin = FinancialsResult(True, [84.68, 33.27, 8.95])
    row = IpoReportRow(evaluation=evaluate(SUB_ROW, GMP_ROW, fin), financials=fin)
    mock_gather.return_value = [row]
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    run()

    mock_send_report.assert_not_called()


@patch("iposcan.report.send_report_to_telegram")
@patch("iposcan.report.load_dotenv")
@patch("iposcan.report.gather_active_mainboard_ipos")
def test_run_sends_telegram_when_credentials_present(
    mock_gather, mock_load_dotenv, mock_send_report, tmp_path, monkeypatch
):
    fin = FinancialsResult(True, [84.68, 33.27, 8.95])
    rows = [IpoReportRow(evaluation=evaluate(SUB_ROW, GMP_ROW, fin), financials=fin)]
    mock_gather.return_value = rows
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CHAT")

    run()

    mock_send_report.assert_called_once_with("TOKEN", "CHAT", rows)

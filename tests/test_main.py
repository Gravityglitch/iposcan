from unittest.mock import patch

from iposcan.main import run
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


@patch("iposcan.main.notify.send_telegram_message")
@patch("iposcan.main.financials.get_financials_for")
@patch("iposcan.main.financials.parse_dashboard_links", return_value={})
@patch("iposcan.main.financials.fetch_dashboard_html", return_value="<html></html>")
@patch("iposcan.main.gmp.filter_open_mainboard", return_value=[GMP_ROW])
@patch("iposcan.main.gmp.parse_gmp_table", return_value=[GMP_ROW])
@patch("iposcan.main.gmp.fetch_gmp_html", return_value="<html></html>")
@patch("iposcan.main.subscription.parse_subscription_table", return_value=[SUB_ROW])
@patch("iposcan.main.subscription.fetch_subscription_html", return_value="<html></html>")
@patch("iposcan.main.state.load_alerted", return_value=set())
@patch("iposcan.main.state.save_alerted")
def test_run_sends_alert_and_saves_state_for_new_pass(
    mock_save_alerted,
    mock_load_alerted,
    mock_fetch_sub,
    mock_parse_sub,
    mock_fetch_gmp,
    mock_parse_gmp,
    mock_filter_gmp,
    mock_fetch_dashboard,
    mock_parse_links,
    mock_get_financials,
    mock_send,
    monkeypatch,
):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CHAT")
    mock_get_financials.return_value = FinancialsResult(True, [84.68, 33.27, 8.95])

    run()

    mock_send.assert_called_once()
    sent_text = mock_send.call_args.args[2]
    assert "Ardee Industries" in sent_text
    mock_save_alerted.assert_called_once()
    saved_names = mock_save_alerted.call_args.args[1]
    assert saved_names == {"Ardee Industries"}


@patch("iposcan.main.notify.send_telegram_message")
@patch("iposcan.main.financials.get_financials_for")
@patch("iposcan.main.financials.parse_dashboard_links", return_value={})
@patch("iposcan.main.financials.fetch_dashboard_html", return_value="<html></html>")
@patch("iposcan.main.gmp.filter_open_mainboard", return_value=[GMP_ROW])
@patch("iposcan.main.gmp.parse_gmp_table", return_value=[GMP_ROW])
@patch("iposcan.main.gmp.fetch_gmp_html", return_value="<html></html>")
@patch("iposcan.main.subscription.parse_subscription_table", return_value=[SUB_ROW])
@patch("iposcan.main.subscription.fetch_subscription_html", return_value="<html></html>")
@patch("iposcan.main.state.load_alerted", return_value={"Ardee Industries"})
@patch("iposcan.main.state.save_alerted")
def test_run_skips_already_alerted_ipo(
    mock_save_alerted,
    mock_load_alerted,
    mock_fetch_sub,
    mock_parse_sub,
    mock_fetch_gmp,
    mock_parse_gmp,
    mock_filter_gmp,
    mock_fetch_dashboard,
    mock_parse_links,
    mock_get_financials,
    mock_send,
    monkeypatch,
):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CHAT")

    run()

    mock_send.assert_not_called()
    mock_save_alerted.assert_not_called()

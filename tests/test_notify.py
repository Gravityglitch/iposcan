from unittest.mock import patch

from iposcan.criteria import IpoEvaluation
from iposcan.notify import TELEGRAM_API_URL, format_alert, send_telegram_message


def _evaluation(profit_growing: bool | None) -> IpoEvaluation:
    return IpoEvaluation(
        ipo_name="Ardee Industries",
        qib=1.13,
        nii=5.58,
        retail=3.42,
        total=3.23,
        gmp_rupees=13.0,
        listing_gain_pct=24.53,
        profit_growing=profit_growing,
        passes=True,
        reasons=[],
    )


def test_format_alert_includes_name_and_breakdown():
    text = format_alert(_evaluation(True))
    assert "Ardee Industries" in text
    assert "QIB 1.13x" in text
    assert "NII 5.58x" in text
    assert "Retail 3.42x" in text
    assert "Total 3.23x" in text
    assert "24.53%" in text
    assert "Growing" in text


def test_format_alert_shows_unknown_profit_trend():
    text = format_alert(_evaluation(None))
    assert "verify manually" in text.lower()


def test_format_alert_shows_declining_profit_trend():
    text = format_alert(_evaluation(False))
    assert "not growing" in text.lower()


def test_send_telegram_message_posts_to_correct_url():
    with patch("iposcan.notify.requests.post") as mock_post:
        mock_post.return_value.raise_for_status.return_value = None
        send_telegram_message("TOKEN123", "CHAT456", "hello")
        called_url = mock_post.call_args.args[0]
        called_data = mock_post.call_args.kwargs["data"]
        assert called_url == TELEGRAM_API_URL.format(token="TOKEN123")
        assert called_data == {"chat_id": "CHAT456", "text": "hello"}


def test_send_telegram_message_includes_parse_mode_when_given():
    with patch("iposcan.notify.requests.post") as mock_post:
        mock_post.return_value.raise_for_status.return_value = None
        send_telegram_message("TOKEN123", "CHAT456", "hello", parse_mode="Markdown")
        called_data = mock_post.call_args.kwargs["data"]
        assert called_data == {"chat_id": "CHAT456", "text": "hello", "parse_mode": "Markdown"}

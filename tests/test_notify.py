from unittest.mock import patch

from iposcan.criteria import IpoEvaluation
from iposcan.notify import TELEGRAM_API_URL, format_alert, send_telegram_message


def _evaluation(profit_growing: bool | None, passes: bool = True) -> IpoEvaluation:
    return IpoEvaluation(
        ipo_name="Ardee Industries",
        qib=1.13,
        nii=5.58,
        retail=3.42,
        total=3.23,
        gmp_rupees=13.0,
        listing_gain_pct=24.53,
        profit_growing=profit_growing,
        passes=passes,
        reasons=[],
    )


def test_format_alert_says_yes_when_passes():
    text = format_alert(_evaluation(True, passes=True))
    assert text == "Ardee Industries: Yes, invest in this IPO"


def test_format_alert_says_no_when_fails():
    text = format_alert(_evaluation(True, passes=False))
    assert text == "Ardee Industries: No, invest in this IPO"


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

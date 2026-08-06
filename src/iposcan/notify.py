"""Format and send Telegram alerts for IPOs that pass the criteria."""
from __future__ import annotations

import requests

from iposcan.criteria import IpoEvaluation

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
REQUEST_TIMEOUT_SECONDS = 30


def format_alert(evaluation: IpoEvaluation) -> str:
    verdict = "Yes" if evaluation.passes else "No"
    return f"{evaluation.ipo_name}: {verdict}, invest in this IPO"


def send_telegram_message(
    token: str, chat_id: str, text: str, parse_mode: str | None = None
) -> None:
    url = TELEGRAM_API_URL.format(token=token)
    data = {"chat_id": chat_id, "text": text}
    if parse_mode:
        data["parse_mode"] = parse_mode
    response = requests.post(url, data=data, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()

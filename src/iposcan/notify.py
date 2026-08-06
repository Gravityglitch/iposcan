"""Format and send Telegram alerts for IPOs that pass the criteria."""
from __future__ import annotations

import requests

from iposcan.criteria import IpoEvaluation

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
REQUEST_TIMEOUT_SECONDS = 30

_PROFIT_LABELS: dict[bool | None, str] = {
    True: "📈 Growing (3yr)",
    False: "📉 Not growing",
    None: "⚠️ Unknown - verify manually",
}


def format_alert(evaluation: IpoEvaluation) -> str:
    return (
        f"🎯 IPO Alert: {evaluation.ipo_name}\n\n"
        f"Subscription — QIB {evaluation.qib}x | NII {evaluation.nii}x | "
        f"Retail {evaluation.retail}x | Total {evaluation.total}x\n"
        f"GMP: ₹{evaluation.gmp_rupees} (~{evaluation.listing_gain_pct}% listing gain)\n"
        f"Profit trend: {_PROFIT_LABELS[evaluation.profit_growing]}"
    )


def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    url = TELEGRAM_API_URL.format(token=token)
    response = requests.post(
        url,
        data={"chat_id": chat_id, "text": text},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

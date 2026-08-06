"""Daily orchestration: fetch, evaluate, dedup, and alert."""
from __future__ import annotations

import os
from pathlib import Path

from iposcan import criteria, notify, state
from iposcan.sources import financials, gmp, subscription

STATE_PATH = Path("state/alerted_ipos.json")


def run() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    sub_rows = subscription.parse_subscription_table(subscription.fetch_subscription_html())
    sub_by_name = {row.ipo_name: row for row in sub_rows}

    gmp_rows = gmp.parse_gmp_table(gmp.fetch_gmp_html())
    open_mainboard = gmp.filter_open_mainboard(gmp_rows)

    dashboard_links = financials.parse_dashboard_links(financials.fetch_dashboard_html())

    alerted = state.load_alerted(STATE_PATH)
    newly_alerted: set[str] = set()

    for gmp_row in open_mainboard:
        if gmp_row.ipo_name in alerted:
            continue

        sub_row = sub_by_name.get(gmp_row.ipo_name)
        if sub_row is None:
            continue

        fin_result = financials.get_financials_for(gmp_row.ipo_name, dashboard_links)
        evaluation = criteria.evaluate(sub_row, gmp_row, fin_result)

        if evaluation.passes:
            notify.send_telegram_message(token, chat_id, notify.format_alert(evaluation))
            newly_alerted.add(gmp_row.ipo_name)

    if newly_alerted:
        state.save_alerted(STATE_PATH, alerted | newly_alerted)


if __name__ == "__main__":
    run()

"""Fetch and report on all currently open Mainboard IPOs (no dedup).

Telegram delivery is optional: if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are
both set, the report is also sent to that chat. Unlike main.py, every open
Mainboard IPO is reported regardless of whether it passes the criteria, and
there is no dedup against previously reported IPOs.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from iposcan import criteria, notify
from iposcan.criteria import IpoEvaluation
from iposcan.sources import financials, gmp, subscription
from iposcan.sources.financials import FinancialsResult


@dataclass(frozen=True)
class IpoReportRow:
    evaluation: IpoEvaluation
    financials: FinancialsResult


def gather_active_mainboard_ipos() -> list[IpoReportRow]:
    sub_rows = subscription.parse_subscription_table(subscription.fetch_subscription_html())
    sub_by_name = {row.ipo_name: row for row in sub_rows}

    gmp_rows = gmp.parse_gmp_table(gmp.fetch_gmp_html())
    open_mainboard = gmp.filter_open_mainboard(gmp_rows)

    dashboard_links = financials.parse_dashboard_links(financials.fetch_dashboard_html())

    rows: list[IpoReportRow] = []
    for gmp_row in open_mainboard:
        sub_row = sub_by_name.get(gmp_row.ipo_name)
        if sub_row is None:
            continue

        fin_result = financials.get_financials_for(gmp_row.ipo_name, dashboard_links)
        evaluation = criteria.evaluate(sub_row, gmp_row, fin_result)
        rows.append(IpoReportRow(evaluation=evaluation, financials=fin_result))

    return rows


def _financials_rows(fin: FinancialsResult) -> list[tuple[str, float, float | None]]:
    if not fin.available or not fin.profit_after_tax:
        return []

    periods = fin.period_ended or [f"Period {i + 1}" for i in range(len(fin.profit_after_tax))]
    revenues = fin.total_income or [None] * len(fin.profit_after_tax)
    return list(zip(periods, fin.profit_after_tax, revenues, strict=False))


def format_report(rows: list[IpoReportRow]) -> str:
    if not rows:
        return "## Active Mainboard IPOs\n\nNo open Mainboard IPOs found.\n"

    lines = [
        "## Active Mainboard IPOs",
        "",
        "| IPO | QIB | NII | Retail | Total | GMP | Listing Gain | Meets Criteria |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        e = row.evaluation
        lines.append(
            f"| {e.ipo_name} | {e.qib}x | {e.nii}x | {e.retail}x | {e.total}x | "
            f"₹{e.gmp_rupees} | {e.listing_gain_pct}% | {'✅' if e.passes else '❌'} |"
        )

    lines += ["", "### Financials (₹ Cr)"]
    for row in rows:
        fin_rows = _financials_rows(row.financials)
        lines.append(f"\n**{row.evaluation.ipo_name}**")
        if not fin_rows:
            lines.append("Financials unavailable - verify manually")
            continue
        lines.append("| Period Ended | Profit After Tax | Revenue |")
        lines.append("|---|---|---|")
        for period, profit, revenue in fin_rows:
            revenue_str = f"₹{revenue}" if revenue is not None else "n/a"
            lines.append(f"| {period} | ₹{profit} | {revenue_str} |")

    return "\n".join(lines) + "\n"


def _financials_table(fin_rows: list[tuple[str, float, float | None]]) -> str:
    if not fin_rows:
        return "Unavailable - verify manually"

    header = ("Period", "Profit", "Revenue")
    table_rows = [
        (period, f"{profit}", f"{revenue}" if revenue is not None else "n/a")
        for period, profit, revenue in fin_rows
    ]
    widths = [
        max(len(header[i]), *(len(r[i]) for r in table_rows)) for i in range(len(header))
    ]

    def _format_row(cells: tuple[str, str, str]) -> str:
        return "  ".join(cell.ljust(width) for cell, width in zip(cells, widths, strict=False))

    lines = [_format_row(header), _format_row("-" * w for w in widths)]
    lines += [_format_row(r) for r in table_rows]
    return "```\n" + "\n".join(lines) + "\n```"


def format_telegram_report(rows: list[IpoReportRow]) -> str:
    if not rows:
        return "No open Mainboard IPOs found."

    blocks = []
    for row in rows:
        e = row.evaluation
        financials_block = _financials_table(_financials_rows(row.financials))

        blocks.append(
            f"🎯 {e.ipo_name}\n"
            f"{'✅ Meets criteria' if e.passes else '❌ Does not meet criteria'}\n\n"
            f"📊 Subscription\n"
            f"  QIB: {e.qib}x\n"
            f"  NII: {e.nii}x\n"
            f"  Retail: {e.retail}x\n"
            f"  Total: {e.total}x\n\n"
            f"💰 GMP: ₹{e.gmp_rupees}  (~{e.listing_gain_pct}% listing gain)\n\n"
            f"📈 Financials (₹ Cr)\n{financials_block}"
        )

    header = f"📋 {len(rows)} active Mainboard IPO(s)\n\n"
    return header + "\n\n━━━━━━━━━━━━━━━\n\n".join(blocks)


def send_report_to_telegram(token: str, chat_id: str, rows: list[IpoReportRow]) -> None:
    notify.send_telegram_message(
        token, chat_id, format_telegram_report(rows), parse_mode="Markdown"
    )


def run() -> None:
    load_dotenv()

    rows = gather_active_mainboard_ipos()
    report = format_report(rows)
    print(report)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(report)

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        send_report_to_telegram(token, chat_id, rows)


if __name__ == "__main__":
    run()

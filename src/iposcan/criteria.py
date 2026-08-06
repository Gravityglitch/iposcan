"""Evaluate parsed IPO data against the scanner's go/no-go criteria."""
from __future__ import annotations

from dataclasses import dataclass, field

from iposcan.sources.financials import FinancialsResult
from iposcan.sources.gmp import GmpRow
from iposcan.sources.subscription import SubscriptionRow

MIN_TOTAL_SUBSCRIPTION = 3.0
MIN_LISTING_GAIN_PCT = 10.0
REQUIRED_PROFIT_PERIODS = 3


@dataclass(frozen=True)
class IpoEvaluation:
    ipo_name: str
    qib: float
    nii: float
    retail: float
    total: float
    gmp_rupees: float
    listing_gain_pct: float
    profit_growing: bool | None
    passes: bool
    reasons: list[str] = field(default_factory=list)


def is_profit_growing(pat_by_period: list[float] | None) -> bool | None:
    """True/False if 3 periods of PAT are available (newest first), else None (unknown)."""
    if not pat_by_period or len(pat_by_period) < REQUIRED_PROFIT_PERIODS:
        return None
    newest, middle, oldest = pat_by_period[0], pat_by_period[1], pat_by_period[2]
    return newest > middle > oldest


def evaluate(
    subscription: SubscriptionRow,
    gmp: GmpRow,
    financials: FinancialsResult,
) -> IpoEvaluation:
    reasons: list[str] = []

    subscription_ok = subscription.total >= MIN_TOTAL_SUBSCRIPTION
    if not subscription_ok:
        reasons.append(
            f"Total subscription {subscription.total}x below {MIN_TOTAL_SUBSCRIPTION}x"
        )

    gmp_ok = gmp.listing_gain_pct >= MIN_LISTING_GAIN_PCT
    if not gmp_ok:
        reasons.append(
            f"Listing gain {gmp.listing_gain_pct}% below {MIN_LISTING_GAIN_PCT}%"
        )

    pat = financials.profit_after_tax if financials.available else None
    profit_growing = is_profit_growing(pat)
    if profit_growing is False:
        reasons.append("Profit not growing across last 3 reported periods")
    elif profit_growing is None:
        reasons.append("Profit trend unknown - verify manually")

    return IpoEvaluation(
        ipo_name=subscription.ipo_name,
        qib=subscription.qib,
        nii=subscription.nii,
        retail=subscription.retail,
        total=subscription.total,
        gmp_rupees=gmp.gmp_rupees,
        listing_gain_pct=gmp.listing_gain_pct,
        profit_growing=profit_growing,
        passes=subscription_ok and gmp_ok,
        reasons=reasons,
    )

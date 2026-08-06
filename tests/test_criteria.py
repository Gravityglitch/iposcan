from iposcan.criteria import IpoEvaluation, evaluate, is_profit_growing
from iposcan.sources.financials import FinancialsResult
from iposcan.sources.gmp import GmpRow
from iposcan.sources.subscription import SubscriptionRow


def _sub(total: float) -> SubscriptionRow:
    return SubscriptionRow(
        ipo_name="Ardee Industries",
        ipo_type="Mainboard",
        closing_date="August 7, 2026",
        qib=1.13,
        nii=5.58,
        retail=3.42,
        total=total,
    )


def _gmp(listing_gain_pct: float) -> GmpRow:
    return GmpRow(
        ipo_name="Ardee Industries",
        gmp_rupees=13.0,
        price_band="₹53",
        listing_gain_pct=listing_gain_pct,
        date_range="5-7 August",
        ipo_type="Mainboard",
        status="Open",
    )


def test_is_profit_growing_true_when_strictly_increasing():
    assert is_profit_growing([84.68, 33.27, 8.95]) is True


def test_is_profit_growing_false_when_not_strictly_increasing():
    assert is_profit_growing([5.0, 10.0, 20.0]) is False


def test_is_profit_growing_none_when_missing():
    assert is_profit_growing(None) is None
    assert is_profit_growing([1.0, 2.0]) is None


def test_evaluate_passes_when_subscription_and_gmp_both_meet_threshold():
    result = evaluate(_sub(total=3.23), _gmp(24.53), FinancialsResult(True, [84.68, 33.27, 8.95]))
    assert result.passes is True
    assert result.profit_growing is True
    assert result.reasons == []


def test_evaluate_passes_even_when_financials_unknown():
    result = evaluate(_sub(total=3.23), _gmp(24.53), FinancialsResult(False, None))
    assert result.passes is True
    assert result.profit_growing is None
    assert "verify manually" in result.reasons[0].lower()


def test_evaluate_fails_when_subscription_below_threshold():
    result = evaluate(_sub(total=2.9), _gmp(24.53), FinancialsResult(True, [84.68, 33.27, 8.95]))
    assert result.passes is False
    assert any("subscription" in r.lower() for r in result.reasons)


def test_evaluate_fails_when_gmp_below_threshold():
    result = evaluate(_sub(total=3.23), _gmp(9.9), FinancialsResult(True, [84.68, 33.27, 8.95]))
    assert result.passes is False
    assert any("listing gain" in r.lower() for r in result.reasons)


def test_evaluate_carries_through_breakdown_fields():
    result = evaluate(_sub(total=3.23), _gmp(24.53), FinancialsResult(False, None))
    assert isinstance(result, IpoEvaluation)
    assert result.ipo_name == "Ardee Industries"
    assert result.qib == 1.13
    assert result.nii == 5.58
    assert result.retail == 3.42
    assert result.total == 3.23
    assert result.gmp_rupees == 13.0
    assert result.listing_gain_pct == 24.53

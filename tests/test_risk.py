import pytest
from agent.models import DealRecord
from agent.risk import score_risk


def _deal(**kwargs) -> DealRecord:
    defaults = dict(
        deal_id="TEST-001",
        customer="TestCo",
        segment="enterprise",
        arr=100000,
        list_price=120000,
        discount_pct=16.7,
        contract_months=24,
        custom_terms=[],
        strategic_context="",
        sales_rep="",
        close_date="",
        deal_stage="",
    )
    defaults.update(kwargs)
    return DealRecord(**defaults)


class TestDiscountDimension:
    def test_low(self):
        r = score_risk(_deal(discount_pct=10.0))
        assert r.discount.score == "LOW"

    def test_medium(self):
        r = score_risk(_deal(discount_pct=20.0))
        assert r.discount.score == "MEDIUM"

    def test_high(self):
        r = score_risk(_deal(discount_pct=35.0))
        assert r.discount.score == "HIGH"

    def test_critical(self):
        r = score_risk(_deal(discount_pct=45.0))
        assert r.discount.score == "CRITICAL"
        assert any("CRITICAL" in f for f in r.raised_flags)


class TestContractTermDimension:
    def test_low_24_months(self):
        r = score_risk(_deal(contract_months=24))
        assert r.contract_term.score == "LOW"

    def test_medium_12_months(self):
        r = score_risk(_deal(contract_months=12))
        assert r.contract_term.score == "MEDIUM"

    def test_high_below_12(self):
        r = score_risk(_deal(contract_months=6))
        assert r.contract_term.score == "HIGH"
        assert any("SHORT-TERM" in f for f in r.raised_flags)


class TestNonStandardFlagsDimension:
    def test_zero_flags(self):
        r = score_risk(_deal(custom_terms=[]))
        assert r.non_standard_flags.score == "LOW"

    def test_one_flag(self):
        r = score_risk(_deal(custom_terms=["net-60"]))
        assert r.non_standard_flags.score == "MEDIUM"

    def test_two_flags(self):
        r = score_risk(_deal(custom_terms=["net-60", "audit-rights"]))
        assert r.non_standard_flags.score == "MEDIUM"

    def test_three_flags_triggers_high(self):
        r = score_risk(_deal(custom_terms=["net-60", "MFN", "MSA-deviation"]))
        assert r.non_standard_flags.score == "HIGH"
        assert any("FULL REVIEW" in f for f in r.raised_flags)


class TestPricingComplianceDimension:
    def test_low_when_no_below_floor(self):
        r = score_risk(_deal(custom_terms=["net-60"]))
        assert r.pricing_compliance.score == "LOW"

    def test_critical_when_below_floor(self):
        r = score_risk(_deal(custom_terms=["below-floor"]))
        assert r.pricing_compliance.score == "CRITICAL"
        assert any("floor" in f.lower() for f in r.raised_flags)


class TestFinanceTermsDimension:
    def test_low_no_finance_terms(self):
        r = score_risk(_deal(custom_terms=[]))
        assert r.finance_terms.score == "LOW"

    def test_medium_one_finance_term(self):
        r = score_risk(_deal(custom_terms=["net-60"]))
        assert r.finance_terms.score == "MEDIUM"

    def test_critical_multiple_finance_terms(self):
        r = score_risk(_deal(custom_terms=["net-90", "milestone-billing"]))
        assert r.finance_terms.score == "CRITICAL"
        assert any("FINANCE ESCALATION" in f for f in r.raised_flags)


class TestLegalDimension:
    def test_low_no_legal_terms(self):
        r = score_risk(_deal(custom_terms=[]))
        assert r.legal_contractual.score == "LOW"

    def test_medium_sla_deviation(self):
        r = score_risk(_deal(custom_terms=["SLA-deviation"]))
        assert r.legal_contractual.score == "MEDIUM"

    def test_high_msa_deviation(self):
        r = score_risk(_deal(custom_terms=["MSA-deviation"]))
        assert r.legal_contractual.score == "HIGH"
        assert any("LEGAL APPROVAL" in f for f in r.raised_flags)

    def test_critical_material_msa(self):
        r = score_risk(_deal(custom_terms=["material-msa"]))
        assert r.legal_contractual.score == "CRITICAL"


class TestCompositeAndNumericScore:
    def test_composite_is_max_dimension(self):
        r = score_risk(_deal(discount_pct=45.0))  # CRITICAL discount
        assert r.composite == "CRITICAL"

    def test_numeric_score_zero_for_clean_deal(self):
        r = score_risk(_deal(discount_pct=5.0, contract_months=24, custom_terms=[]))
        assert r.numeric_score == 0

    def test_numeric_score_increases_with_risk(self):
        clean = score_risk(_deal(discount_pct=5.0, contract_months=24, custom_terms=[]))
        risky = score_risk(_deal(discount_pct=35.0, contract_months=6, custom_terms=["net-90", "MSA-deviation"]))
        assert risky.numeric_score > clean.numeric_score

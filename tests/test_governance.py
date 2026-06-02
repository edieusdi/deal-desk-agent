import pytest
from agent.models import DealRecord
from agent.governance import run_governance


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


class TestApprovalTiers:
    def test_standard_tier(self):
        g = run_governance(_deal(arr=100000, list_price=100000, discount_pct=0))
        assert g.approval_tier == "Standard"
        assert not g.is_blocked

    def test_standard_tier_at_boundary(self):
        g = run_governance(_deal(arr=85000, list_price=100000, discount_pct=15.0))
        assert g.approval_tier == "Standard"

    def test_mid_tier(self):
        g = run_governance(_deal(arr=83000, list_price=100000, discount_pct=17.0))
        assert g.approval_tier == "Mid-Tier"
        assert not g.is_blocked

    def test_executive_tier(self):
        g = run_governance(_deal(arr=70000, list_price=100000, discount_pct=30.0))
        assert g.approval_tier == "Executive"
        assert not g.is_blocked

    def test_strategic_tier_is_blocked(self):
        g = run_governance(_deal(arr=55000, list_price=100000, discount_pct=45.0))
        assert g.approval_tier == "Strategic"
        assert g.is_blocked


class TestCommercialMetrics:
    def test_acv_and_tcv(self):
        g = run_governance(_deal(arr=250000, list_price=300000, discount_pct=16.7, contract_months=24))
        assert g.acv_list == 300000
        assert g.acv_discounted == 250000
        assert g.tcv_list == pytest.approx(600000)
        assert g.tcv_discounted == pytest.approx(500000)
        assert g.discount_value_dollars == pytest.approx(100000)

    def test_no_discount(self):
        g = run_governance(_deal(arr=100000, list_price=100000, discount_pct=0, contract_months=12))
        assert g.discount_value_dollars == pytest.approx(0)
        assert g.tcv_list == pytest.approx(g.tcv_discounted)


class TestFunctionalApprovals:
    def test_finance_trigger(self):
        g = run_governance(_deal(custom_terms=["net-60"]))
        assert any("Finance" in a for a in g.functional_approvals)

    def test_legal_trigger(self):
        g = run_governance(_deal(custom_terms=["MSA-deviation"]))
        assert any("Legal" in a for a in g.functional_approvals)

    def test_government_trigger(self):
        g = run_governance(_deal(custom_terms=["government"]))
        assert any("Government" in a or "Legal/Compliance" in a for a in g.functional_approvals)

    def test_below_floor_blocks_deal(self):
        g = run_governance(_deal(custom_terms=["below-floor"]))
        assert g.is_blocked
        assert any("Pricing" in a for a in g.functional_approvals)

    def test_no_custom_terms_no_functional_approvals(self):
        g = run_governance(_deal(custom_terms=[]))
        assert g.functional_approvals == []

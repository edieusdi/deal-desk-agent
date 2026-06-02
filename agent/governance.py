from .models import DealRecord, GovernanceResult

# Approval tier thresholds (discount %)
TIER_STANDARD_MAX = 15.0
TIER_MID_MAX = 25.0
TIER_EXECUTIVE_MAX = 40.0

# Placeholder approver contacts — replace with real names/emails
APPROVERS = {
    "Standard": "Auto-approved — no approval required",
    "Mid-Tier": "deal-desk-manager@company.com",
    "Executive": "vp-sales@company.com",
    "Strategic": "c-suite@company.com — DEAL BLOCKED pending sign-off",
}

# Terms that trigger Finance Director approval regardless of discount tier
FINANCE_TRIGGER_TERMS = {"net-60", "net-90", "net-120", "milestone-billing", "quarterly-billing", "multi-year-prepay"}

# Terms that trigger Legal Counsel approval regardless of discount tier
LEGAL_TRIGGER_TERMS = {"msa-deviation", "sla-deviation", "mfn", "liability-cap-deviation", "ip-indemnification", "material-msa"}

# Terms that trigger Channel team approval
CHANNEL_TRIGGER_TERMS = {"channel-partner", "reseller", "distributor"}

# Government deals trigger Legal/Compliance
GOVERNMENT_TRIGGER_TERMS = {"government", "gov", "public-sector"}


def run_governance(deal: DealRecord) -> GovernanceResult:
    acv_list = deal.list_price
    acv_discounted = deal.arr
    arr = deal.arr
    tcv_list = deal.list_price * deal.contract_months / 12
    tcv_discounted = deal.arr * deal.contract_months / 12
    discount_value_dollars = tcv_list - tcv_discounted

    # Approval tier from discount depth
    d = deal.discount_pct
    if d <= TIER_STANDARD_MAX:
        tier = "Standard"
    elif d <= TIER_MID_MAX:
        tier = "Mid-Tier"
    elif d <= TIER_EXECUTIVE_MAX:
        tier = "Executive"
    else:
        tier = "Strategic"

    terms_lower = {t.lower() for t in deal.custom_terms}
    is_blocked = tier == "Strategic" or "below-floor" in terms_lower

    functional_approvals: list[str] = []
    if terms_lower & FINANCE_TRIGGER_TERMS:
        triggered = sorted(terms_lower & FINANCE_TRIGGER_TERMS)
        functional_approvals.append(f"Finance Director — non-standard payment terms: {', '.join(triggered)}")
    if terms_lower & LEGAL_TRIGGER_TERMS:
        triggered = sorted(terms_lower & LEGAL_TRIGGER_TERMS)
        functional_approvals.append(f"Legal Counsel — contract deviations: {', '.join(triggered)}")
    if terms_lower & CHANNEL_TRIGGER_TERMS:
        functional_approvals.append("Channel Manager — channel partner structure")
    if terms_lower & GOVERNMENT_TRIGGER_TERMS:
        functional_approvals.append("Legal/Compliance — government customer")
    if "below-floor" in terms_lower:
        functional_approvals.append("Pricing team — pricing below approved floor — DEAL BLOCKED")

    return GovernanceResult(
        deal_id=deal.deal_id,
        acv_list=acv_list,
        acv_discounted=acv_discounted,
        arr=arr,
        tcv_list=tcv_list,
        tcv_discounted=tcv_discounted,
        discount_value_dollars=discount_value_dollars,
        discount_pct=deal.discount_pct,
        approval_tier=tier,
        is_blocked=is_blocked,
        primary_approver=APPROVERS[tier],
        functional_approvals=functional_approvals,
    )

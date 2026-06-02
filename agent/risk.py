from .models import DealRecord, RiskDimension, RiskScore

# Terms classified by risk dimension
_FINANCE_TERMS = {"net-60", "net-90", "net-120", "milestone-billing", "quarterly-billing", "multi-year-prepay", "upfront-discount"}
_LEGAL_TERMS = {"msa-deviation", "sla-deviation", "mfn", "liability-cap-deviation", "ip-indemnification", "material-msa", "audit-rights"}
_GENERAL_NONSTANDARD = {"free-months", "bundled-discount", "co-term", "channel-partner", "government", "reseller"}


def score_risk(deal: DealRecord) -> RiskScore:
    terms_lower = {t.lower() for t in deal.custom_terms}
    raised_flags: list[str] = []

    # ── 1. Discount depth ─────────────────────────────────────────────────────
    d = deal.discount_pct
    if d <= 15.0:
        discount_dim = RiskDimension("Discount", "LOW", f"{d:.1f}% — within standard policy")
    elif d <= 25.0:
        discount_dim = RiskDimension("Discount", "MEDIUM", f"{d:.1f}% — requires Deal Desk Manager approval")
        raised_flags.append(f"DISCOUNT {d:.1f}% — Mid-Tier approval required")
    elif d <= 40.0:
        discount_dim = RiskDimension("Discount", "HIGH", f"{d:.1f}% — HIGH PRIORITY: VP Sales approval required")
        raised_flags.append(f"HIGH PRIORITY — DISCOUNT {d:.1f}%: VP Sales approval required")
    else:
        discount_dim = RiskDimension("Discount", "CRITICAL", f"{d:.1f}% — BLOCKED: above 40% ceiling, C-Suite sign-off required")
        raised_flags.append(f"CRITICAL — DISCOUNT {d:.1f}%: deal blocked, C-Suite required")

    # ── 2. Contract term ──────────────────────────────────────────────────────
    m = deal.contract_months
    if m >= 24:
        term_dim = RiskDimension("Contract Term", "LOW", f"{m}-month term — long-term commitment")
    elif m >= 12:
        term_dim = RiskDimension("Contract Term", "MEDIUM", f"{m}-month term — standard but not long-term")
    else:
        term_dim = RiskDimension("Contract Term", "HIGH", f"{m}-month term — SHORT-TERM RISK: below 12 months")
        raised_flags.append(f"SHORT-TERM RISK — {m}-month contract below 12-month threshold")

    # ── 3. Non-standard flags (count of all custom_terms) ─────────────────────
    n = len(deal.custom_terms)
    if n == 0:
        flags_dim = RiskDimension("Non-Standard Flags", "LOW", "No non-standard terms")
    elif n <= 2:
        flags_dim = RiskDimension("Non-Standard Flags", "MEDIUM", f"{n} non-standard term(s): {', '.join(deal.custom_terms)}")
    else:
        flags_dim = RiskDimension("Non-Standard Flags", "HIGH", f"{n} flags — full review required: {', '.join(deal.custom_terms)}")
        raised_flags.append(f"FULL REVIEW — {n} non-standard terms flagged: {', '.join(deal.custom_terms)}")

    # ── 4. Pricing compliance ─────────────────────────────────────────────────
    if "below-floor" in terms_lower:
        pricing_dim = RiskDimension("Pricing Compliance", "CRITICAL", "BLOCKED — pricing below approved floor")
        raised_flags.append("CRITICAL — pricing below approved floor: deal blocked")
    else:
        pricing_dim = RiskDimension("Pricing Compliance", "LOW", "All pricing at or above floor")

    # ── 5. Finance terms ──────────────────────────────────────────────────────
    finance_hits = terms_lower & _FINANCE_TERMS
    if not finance_hits:
        finance_dim = RiskDimension("Finance Terms", "LOW", "Standard billing — no finance deviations")
    elif len(finance_hits) == 1:
        finance_dim = RiskDimension("Finance Terms", "MEDIUM", f"One non-standard payment term: {', '.join(finance_hits)}")
    else:
        finance_dim = RiskDimension("Finance Terms", "CRITICAL", f"Multiple finance deviations — Finance escalation required: {', '.join(sorted(finance_hits))}")
        raised_flags.append(f"FINANCE ESCALATION — multiple deviations: {', '.join(sorted(finance_hits))}")

    # ── 6. Legal / contractual ────────────────────────────────────────────────
    legal_hits = terms_lower & _LEGAL_TERMS
    msa_hits = {t for t in legal_hits if "msa" in t}
    sla_hits = {t for t in legal_hits if "sla" in t}
    other_legal = legal_hits - msa_hits - sla_hits

    if not legal_hits:
        legal_dim = RiskDimension("Legal/Contractual", "LOW", "No legal deviations")
    elif msa_hits and any("material" in t for t in msa_hits):
        legal_dim = RiskDimension("Legal/Contractual", "CRITICAL", f"Material MSA changes — Legal countersign required: {', '.join(sorted(msa_hits))}")
        raised_flags.append(f"LEGAL COUNTERSIGN — material MSA changes: {', '.join(sorted(msa_hits))}")
    elif msa_hits:
        legal_dim = RiskDimension("Legal/Contractual", "HIGH", f"MSA deviation — Legal approval required: {', '.join(sorted(msa_hits))}")
        raised_flags.append(f"LEGAL APPROVAL — MSA deviation: {', '.join(sorted(msa_hits))}")
    elif sla_hits:
        legal_dim = RiskDimension("Legal/Contractual", "MEDIUM", f"Minor SLA deviation: {', '.join(sorted(sla_hits))}")
    else:
        legal_dim = RiskDimension("Legal/Contractual", "MEDIUM", f"Non-standard legal terms: {', '.join(sorted(other_legal))}")

    return RiskScore(
        discount=discount_dim,
        contract_term=term_dim,
        non_standard_flags=flags_dim,
        pricing_compliance=pricing_dim,
        finance_terms=finance_dim,
        legal_contractual=legal_dim,
        raised_flags=raised_flags,
    )

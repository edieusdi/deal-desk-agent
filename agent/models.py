from dataclasses import dataclass, field


@dataclass
class DealRecord:
    deal_id: str
    customer: str
    segment: str  # enterprise | mid-market | smb
    arr: float    # discounted annual recurring revenue
    list_price: float  # undiscounted annual price
    discount_pct: float
    contract_months: int
    custom_terms: list[str] = field(default_factory=list)
    strategic_context: str = ""
    sales_rep: str = ""
    close_date: str = ""
    deal_stage: str = ""


@dataclass
class GovernanceResult:
    deal_id: str
    acv_list: float           # ACV at list price (= list_price)
    acv_discounted: float     # ACV after discount (= arr)
    arr: float
    tcv_list: float           # total contract value at list price
    tcv_discounted: float     # total contract value at discounted price
    discount_value_dollars: float  # total discount given over contract life
    discount_pct: float
    approval_tier: str        # Standard | Mid-Tier | Executive | Strategic
    is_blocked: bool          # True if Strategic tier or pricing below floor
    primary_approver: str
    functional_approvals: list[str] = field(default_factory=list)


SCORE_LEVELS = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
SCORE_LABELS = {0: "LOW", 1: "MEDIUM", 2: "HIGH", 3: "CRITICAL"}


@dataclass
class RiskDimension:
    name: str
    score: str   # LOW | MEDIUM | HIGH | CRITICAL
    detail: str

    @property
    def level(self) -> int:
        return SCORE_LEVELS[self.score]


@dataclass
class RiskScore:
    discount: RiskDimension
    contract_term: RiskDimension
    non_standard_flags: RiskDimension
    pricing_compliance: RiskDimension
    finance_terms: RiskDimension
    legal_contractual: RiskDimension
    raised_flags: list[str] = field(default_factory=list)

    @property
    def composite(self) -> str:
        return SCORE_LABELS[max(d.level for d in self.dimensions)]

    @property
    def numeric_score(self) -> int:
        """Weighted 0–100 score. Discount and pricing compliance carry more weight."""
        weights = {
            "discount": 3.0,
            "pricing_compliance": 2.5,
            "legal_contractual": 2.0,
            "finance_terms": 1.5,
            "contract_term": 1.0,
            "non_standard_flags": 1.0,
        }
        total_weight = sum(weights.values())
        weighted_sum = (
            weights["discount"] * self.discount.level
            + weights["pricing_compliance"] * self.pricing_compliance.level
            + weights["legal_contractual"] * self.legal_contractual.level
            + weights["finance_terms"] * self.finance_terms.level
            + weights["contract_term"] * self.contract_term.level
            + weights["non_standard_flags"] * self.non_standard_flags.level
        )
        return round(weighted_sum / (total_weight * 3) * 100)

    @property
    def dimensions(self) -> list[RiskDimension]:
        return [
            self.discount,
            self.contract_term,
            self.non_standard_flags,
            self.pricing_compliance,
            self.finance_terms,
            self.legal_contractual,
        ]


@dataclass
class AIEvaluation:
    narrative: str
    recommended_action: str  # Approve | Escalate | Negotiate | Block
    risk_observations: str
    provider: str = "claude"


@dataclass
class DealResult:
    deal: DealRecord
    governance: GovernanceResult
    risk: RiskScore
    ai_eval: AIEvaluation

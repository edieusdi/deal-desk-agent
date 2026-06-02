import os
import re
import anthropic
from .models import DealRecord, GovernanceResult, RiskScore, AIEvaluation

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MAX_FREE_TEXT = 500  # chars — caps strategic_context and similar fields


def _sanitize(text: str) -> str:
    """Strip control characters and truncate free-text fields before they enter the prompt."""
    cleaned = _CONTROL_RE.sub("", text)
    if len(cleaned) > _MAX_FREE_TEXT:
        cleaned = cleaned[:_MAX_FREE_TEXT] + " [truncated]"
    return cleaned

_client: anthropic.Anthropic | None = None

SYSTEM_PROMPT = """You are a senior Deal Desk analyst at a SaaS company. You evaluate commercial deals for risk, discount exposure, and governance compliance.

You receive structured deal data, governance metrics, and a risk barometer — all computed deterministically. Your role is to layer in qualitative judgment: flag anything the automated scoring might miss, assess the strategic context, and deliver a clear recommendation.

Rules:
- Be direct and concise. Sales managers need actionable guidance, not lengthy analysis.
- Use the strategic context if provided — it carries weight even if unquantifiable.
- Your recommended_action must be one of: Approve, Escalate, Negotiate, Block.
  - Approve: deal is clean, within policy, no concerns.
  - Escalate: deal needs human review at the indicated tier before proceeding.
  - Negotiate: deal can move forward if specific terms are improved first.
  - Block: deal cannot proceed — governance violation or unacceptable risk.
- narrative: 2–4 sentences covering the overall deal risk profile.
- risk_observations: bullet-point list of specific observations (use \\n• prefix for each). If none, write "No additional observations."
"""

EVAL_TOOL = {
    "name": "submit_evaluation",
    "description": "Submit the structured deal evaluation",
    "input_schema": {
        "type": "object",
        "properties": {
            "narrative": {
                "type": "string",
                "description": "2–4 sentence narrative of the overall risk profile",
            },
            "recommended_action": {
                "type": "string",
                "enum": ["Approve", "Escalate", "Negotiate", "Block"],
                "description": "Clear action directive",
            },
            "risk_observations": {
                "type": "string",
                "description": "Bullet-pointed additional risk observations, or 'No additional observations.'",
            },
        },
        "required": ["narrative", "recommended_action", "risk_observations"],
    },
}


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY is not set")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _build_user_message(deal: DealRecord, gov: GovernanceResult, risk: RiskScore) -> str:
    flags_block = "\n".join(f"  • {f}" for f in risk.raised_flags) if risk.raised_flags else "  None raised"
    func_approvals = "\n".join(f"  • {a}" for a in gov.functional_approvals) if gov.functional_approvals else "  None"
    terms = ", ".join(deal.custom_terms) if deal.custom_terms else "None"

    # User-controlled free-text fields are sanitized and wrapped in XML tags so
    # injected instructions cannot bleed into the structured prompt sections.
    safe_context = _sanitize(deal.strategic_context or "None provided")
    safe_customer = _sanitize(deal.customer)
    safe_rep = _sanitize(deal.sales_rep or "n/a")
    safe_stage = _sanitize(deal.deal_stage or "n/a")

    return f"""<deal_data>
<deal_record>
  Deal ID         : {deal.deal_id}
  Customer        : <customer>{safe_customer}</customer> ({deal.segment})
  Sales Rep       : <sales_rep>{safe_rep}</sales_rep>
  Close Date      : {deal.close_date or 'n/a'}
  Stage           : <stage>{safe_stage}</stage>
  Custom Terms    : {terms}
  Strategic Context: <strategic_context>{safe_context}</strategic_context>
</deal_record>

<commercial_metrics>
  ACV (List)      : ${gov.acv_list:,.0f}
  ACV (Discounted): ${gov.acv_discounted:,.0f}
  ARR             : ${gov.arr:,.0f}
  TCV (List)      : ${gov.tcv_list:,.0f}
  TCV (Discounted): ${gov.tcv_discounted:,.0f}
  Discount        : {gov.discount_pct:.1f}% (${gov.discount_value_dollars:,.0f} given over contract life)
  Contract        : {deal.contract_months} months
</commercial_metrics>

<governance_decision>
  Approval Tier   : {gov.approval_tier}
  Blocked         : {'YES' if gov.is_blocked else 'No'}
  Primary Approver: {gov.primary_approver}
  Functional Approvals:
{func_approvals}
</governance_decision>

<risk_barometer composite="{risk.composite}" score="{risk.numeric_score}/100">
  Discount        : {risk.discount.score} — {risk.discount.detail}
  Contract Term   : {risk.contract_term.score} — {risk.contract_term.detail}
  Non-Std Flags   : {risk.non_standard_flags.score} — {risk.non_standard_flags.detail}
  Pricing Comp.   : {risk.pricing_compliance.score} — {risk.pricing_compliance.detail}
  Finance Terms   : {risk.finance_terms.score} — {risk.finance_terms.detail}
  Legal/Contract  : {risk.legal_contractual.score} — {risk.legal_contractual.detail}
</risk_barometer>

<raised_flags>
{flags_block}
</raised_flags>
</deal_data>
"""


def evaluate_with_claude(deal: DealRecord, gov: GovernanceResult, risk: RiskScore) -> AIEvaluation:
    client = _get_client()
    user_message = _build_user_message(deal, gov, risk)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[EVAL_TOOL],
        tool_choice={"type": "tool", "name": "submit_evaluation"},
        messages=[{"role": "user", "content": user_message}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_evaluation":
            data = block.input
            return AIEvaluation(
                narrative=data["narrative"],
                recommended_action=data["recommended_action"],
                risk_observations=data["risk_observations"],
                provider="claude-sonnet-4-6",
            )

    # Fallback if tool use didn't fire (shouldn't happen with tool_choice forced)
    return AIEvaluation(
        narrative="AI evaluation unavailable.",
        recommended_action="Escalate",
        risk_observations="No additional observations.",
        provider="claude-sonnet-4-6",
    )

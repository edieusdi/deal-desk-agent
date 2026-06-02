import json
import os
import re
import stat
from datetime import datetime
from .models import DealResult


_SEP = "─" * 64
_SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9_-]")


def _safe_filename(deal_id: str) -> str:
    sanitized = _SAFE_ID_RE.sub("_", deal_id.strip())
    if not sanitized:
        raise ValueError(f"deal_id {deal_id!r} produced an empty filename after sanitization")
    return sanitized


def _checked_path(output_dir: str, filename: str) -> str:
    """Return absolute path and assert it stays inside output_dir."""
    base = os.path.realpath(output_dir)
    target = os.path.realpath(os.path.join(base, filename))
    if not target.startswith(base + os.sep) and target != base:
        raise ValueError(f"Path traversal detected — resolved path {target!r} escapes {base!r}")
    return target


def _currency(v: float) -> str:
    return f"${v:,.0f}"


def _manager_brief(result: DealResult) -> str:
    d = result.deal
    g = result.governance
    r = result.risk
    ai = result.ai_eval

    flags_section = ""
    if r.raised_flags:
        flags_section = "\nRISK FLAGS\n"
        for flag in r.raised_flags:
            severity = "CRITICAL" if "CRITICAL" in flag else ("HIGH" if "HIGH" in flag else "MEDIUM")
            flags_section += f"  [{severity}] {flag}\n"
    else:
        flags_section = "\nRISK FLAGS\n  None — deal is within policy\n"

    func_section = ""
    if g.functional_approvals:
        func_section = "\n".join(f"  • {a}" for a in g.functional_approvals)
    else:
        func_section = "  None"

    return f"""
{_SEP}
DEAL BRIEF  ·  {d.deal_id}  ·  {d.customer.upper()}
{_SEP}
DEAL SNAPSHOT
  Customer        : {d.customer} ({d.segment.title()})
  Sales Rep       : {d.sales_rep or 'n/a'}
  ACV (List)      : {_currency(g.acv_list)}
  ACV (Disc.)     : {_currency(g.acv_discounted)}
  Discount        : {g.discount_pct:.1f}%  ({_currency(g.discount_value_dollars)} over contract life)
  Contract        : {d.contract_months} months
  TCV             : {_currency(g.tcv_discounted)}
  Stage           : {d.deal_stage or 'n/a'}  ·  Close: {d.close_date or 'n/a'}
{flags_section}
ROUTING DECISION
  Tier            : {g.approval_tier}
  Blocked         : {'⚠  YES' if g.is_blocked else 'No'}
  Primary Approver: {g.primary_approver}
  Functional Approvals:
{func_section}

RECOMMENDED ACTION  [{ai.recommended_action.upper()}]
  {ai.narrative}
{_SEP}
""".strip()


def _deal_desk_report(result: DealResult) -> str:
    d = result.deal
    g = result.governance
    r = result.risk
    ai = result.ai_eval
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    dims = r.dimensions
    dim_lines = "\n".join(
        f"  {dim.name:<22}: {dim.score:<8}  {dim.detail}" for dim in dims
    )

    flags_block = "\n".join(f"  • {f}" for f in r.raised_flags) if r.raised_flags else "  None raised"
    func_block = "\n".join(f"  • {a}" for a in g.functional_approvals) if g.functional_approvals else "  None"

    terms = ", ".join(d.custom_terms) if d.custom_terms else "None"

    next_steps: list[str] = []
    if g.is_blocked:
        next_steps.append("Deal is BLOCKED. Resolve blocking issue before any further action.")
    if g.approval_tier != "Standard":
        next_steps.append(f"Route to primary approver: {g.primary_approver}")
    for fa in g.functional_approvals:
        next_steps.append(f"Obtain functional approval: {fa}")
    if not next_steps:
        next_steps.append("Auto-approved. Log deal in CRM and proceed.")

    steps_block = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(next_steps))

    return f"""
{'═' * 64}
DEAL DESK REPORT  ·  INTERNAL USE ONLY
{'═' * 64}
Generated    : {now}
Deal ID      : {d.deal_id}
Customer     : {d.customer}  ({d.segment.title()})
Sales Rep    : {d.sales_rep or 'n/a'}
Stage        : {d.deal_stage or 'n/a'}
Close Date   : {d.close_date or 'n/a'}
Strategic    : {d.strategic_context or 'None provided'}

{_SEP}
COMMERCIAL METRICS
{_SEP}
  ACV (List Price)    : {_currency(g.acv_list)}
  ACV (Discounted)    : {_currency(g.acv_discounted)}
  ARR                 : {_currency(g.arr)}
  TCV (List Price)    : {_currency(g.tcv_list)}
  TCV (Discounted)    : {_currency(g.tcv_discounted)}
  Discount %          : {g.discount_pct:.1f}%
  Discount $ (TCV)    : {_currency(g.discount_value_dollars)}
  Contract Length     : {d.contract_months} months
  Custom Terms        : {terms}

{_SEP}
RISK BAROMETER  (composite: {r.composite}  ·  score: {r.numeric_score}/100)
{_SEP}
{dim_lines}

RAISED FLAGS
{flags_block}

{_SEP}
GOVERNANCE DECISION
{_SEP}
  Approval Tier       : {g.approval_tier}
  Blocked             : {'YES — DEAL CANNOT PROCEED' if g.is_blocked else 'No'}
  Primary Approver    : {g.primary_approver}
  Functional Approvals:
{func_block}

{_SEP}
AI EVALUATION  (provider: {ai.provider})
{_SEP}
  Action      : {ai.recommended_action.upper()}

  Narrative:
  {ai.narrative}

  Additional Observations:
  {ai.risk_observations}

{_SEP}
NEXT STEPS
{_SEP}
{steps_block}
{'═' * 64}
""".strip()


def generate_output(result: DealResult, output_dir: str = "output") -> dict:
    os.makedirs(output_dir, exist_ok=True)

    brief = _manager_brief(result)
    report = _deal_desk_report(result)

    safe_id = _safe_filename(result.deal.deal_id)
    brief_path = _checked_path(output_dir, f"{safe_id}_manager_brief.txt")
    report_path = _checked_path(output_dir, f"{safe_id}_deal_desk_report.txt")
    json_path = _checked_path(output_dir, f"{safe_id}.json")

    _PRIVATE = stat.S_IRUSR | stat.S_IWUSR  # 0600

    with open(brief_path, "w") as f:
        f.write(brief)
    os.chmod(brief_path, _PRIVATE)

    with open(report_path, "w") as f:
        f.write(report)
    os.chmod(report_path, _PRIVATE)

    payload = {
        "deal_id": result.deal.deal_id,
        "customer": result.deal.customer,
        "approval_tier": result.governance.approval_tier,
        "is_blocked": result.governance.is_blocked,
        "primary_approver": result.governance.primary_approver,
        "functional_approvals": result.governance.functional_approvals,
        "risk_composite": result.risk.composite,
        "risk_score": result.risk.numeric_score,
        "raised_flags": result.risk.raised_flags,
        "recommended_action": result.ai_eval.recommended_action,
        "commercial": {
            "acv_list": result.governance.acv_list,
            "acv_discounted": result.governance.acv_discounted,
            "arr": result.governance.arr,
            "tcv_list": result.governance.tcv_list,
            "tcv_discounted": result.governance.tcv_discounted,
            "discount_pct": result.governance.discount_pct,
            "discount_value_dollars": result.governance.discount_value_dollars,
            "contract_months": result.deal.contract_months,
        },
        "ai_narrative": result.ai_eval.narrative,
        "ai_risk_observations": result.ai_eval.risk_observations,
    }

    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)
    os.chmod(json_path, _PRIVATE)

    return {"brief": brief, "report": report, "json_path": json_path, "brief_path": brief_path, "report_path": report_path}

#!/usr/bin/env python3
"""
Deal Desk Agent — Streamlit frontend.
Run with: streamlit run app.py
"""
import hashlib
import io
import csv as csv_module
import os

import streamlit as st
from dotenv import load_dotenv

from agent.models import DealRecord, DealResult, AIEvaluation
from agent.governance import run_governance
from agent.risk import score_risk
from agent.output import _manager_brief, _deal_desk_report

load_dotenv()

st.set_page_config(
    page_title="Deal Desk Agent",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Colour maps ────────────────────────────────────────────────────────────
_RISK_COLOR = {
    "LOW": "#22c55e",
    "MEDIUM": "#ca8a04",
    "HIGH": "#ea580c",
    "CRITICAL": "#dc2626",
}
_RISK_TEXT = {"LOW": "white", "MEDIUM": "white", "HIGH": "white", "CRITICAL": "white"}
_RISK_EMOJI = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}

_TIER_COLOR = {
    "Standard": "#16a34a",
    "Mid-Tier": "#ca8a04",
    "Executive": "#ea580c",
    "Strategic": "#dc2626",
}
_TIER_EMOJI = {"Standard": "✅", "Mid-Tier": "📋", "Executive": "🔼", "Strategic": "⛔"}
_ACTION_COLOR = {
    "Approve": "#16a34a",
    "Negotiate": "#ca8a04",
    "Escalate": "#ea580c",
    "Block": "#dc2626",
}

PREDEFINED_TERMS = [
    "net-60", "net-90", "net-120",
    "milestone-billing", "quarterly-billing", "multi-year-prepay",
    "MSA-deviation", "SLA-deviation", "MFN", "audit-rights", "material-MSA",
    "liability-cap-deviation", "IP-indemnification",
    "government", "channel-partner", "free-months", "bundled-discount", "below-floor",
]


# ── Helpers ────────────────────────────────────────────────────────────────
def _dummy_ai() -> AIEvaluation:
    return AIEvaluation(narrative="", recommended_action="—", risk_observations="", provider="none")


def _deal_hash(deal: DealRecord) -> str:
    key = f"{deal.deal_id}|{deal.arr}|{deal.discount_pct}|{deal.contract_months}|{'|'.join(sorted(deal.custom_terms))}"
    return hashlib.md5(key.encode()).hexdigest()[:10]


def _api_key_present() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


# ── UI components ──────────────────────────────────────────────────────────
def risk_bar(name: str, score: str, detail: str) -> None:
    pct = {"LOW": 25, "MEDIUM": 50, "HIGH": 75, "CRITICAL": 100}[score]
    c = _RISK_COLOR[score]
    st.markdown(
        f"""
        <div style="margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">
            <span style="font-size:13px;font-weight:600;color:#374151">{name}</span>
            <span style="background:{c};color:white;padding:1px 8px;border-radius:4px;font-size:11px;font-weight:700">{score}</span>
          </div>
          <div style="background:#e5e7eb;border-radius:4px;height:7px">
            <div style="background:{c};width:{pct}%;height:7px;border-radius:4px"></div>
          </div>
          <div style="font-size:11px;color:#6b7280;margin-top:3px">{detail}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def tier_header(tier: str, is_blocked: bool, approver: str) -> None:
    c = _TIER_COLOR[tier]
    blocked = (
        "&nbsp;<span style='background:#7f1d1d;color:#fecaca;padding:2px 8px;"
        "border-radius:4px;font-size:12px;font-weight:600'>BLOCKED</span>"
        if is_blocked
        else ""
    )
    st.markdown(
        f"""
        <div style="background:{c};border-radius:8px;padding:16px 20px;margin-bottom:16px;color:white">
          <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;opacity:0.8">Approval Tier</div>
          <div style="font-size:26px;font-weight:700;margin:4px 0">{tier}{blocked}</div>
          <div style="font-size:13px;opacity:0.9">→ {approver}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def action_badge(action: str) -> str:
    c = _ACTION_COLOR.get(action, "#6b7280")
    return f'<span style="background:{c};color:white;padding:2px 10px;border-radius:4px;font-weight:700;font-size:13px">{action}</span>'


def deal_form(prefix: str = "") -> DealRecord:
    c1, c2 = st.columns(2)
    with c1:
        deal_id = st.text_input("Deal ID", value="DEAL-001", key=f"{prefix}did")
        customer = st.text_input("Customer", value="Acme Corp", key=f"{prefix}cust")
        segment = st.selectbox("Segment", ["enterprise", "mid-market", "smb"], key=f"{prefix}seg")
    with c2:
        sales_rep = st.text_input("Sales Rep", value="", key=f"{prefix}rep")
        close_date = st.text_input("Close Date", value="2026-09-30", placeholder="YYYY-MM-DD", key=f"{prefix}cd")
        deal_stage = st.selectbox("Stage", ["Prospecting", "Qualification", "Proposal", "Negotiation", "Closed Won"], key=f"{prefix}stage")

    st.markdown("---")
    c3, c4 = st.columns(2)
    with c3:
        list_price = st.number_input(
            "List Price (annual $)", min_value=1_000, max_value=10_000_000,
            value=300_000, step=10_000, key=f"{prefix}lp",
        )
        discount_pct = st.slider(
            "Discount %", min_value=0.0, max_value=60.0,
            value=16.7, step=0.5, key=f"{prefix}disc",
        )
    with c4:
        arr = list_price * (1 - discount_pct / 100)
        st.metric("ARR (calculated)", f"${arr:,.0f}")
        contract_months = st.select_slider(
            "Contract Length",
            options=[1, 3, 6, 9, 12, 18, 24, 36, 48, 60],
            value=24,
            format_func=lambda v: f"{v} months",
            key=f"{prefix}cm",
        )

    st.markdown("---")
    custom_terms = st.multiselect("Non-Standard Terms", options=PREDEFINED_TERMS, key=f"{prefix}terms")
    strategic = st.text_area(
        "Strategic Context",
        placeholder="e.g. Fortune 500 logo, competitive displacement, must-win…",
        height=80,
        key=f"{prefix}ctx",
    )

    return DealRecord(
        deal_id=deal_id.strip() or "DEAL-001",
        customer=customer.strip() or "Unknown",
        segment=segment,
        arr=arr,
        list_price=float(list_price),
        discount_pct=float(discount_pct),
        contract_months=int(contract_months),
        custom_terms=custom_terms,
        strategic_context=strategic,
        sales_rep=sales_rep,
        close_date=close_date,
        deal_stage=deal_stage,
    )


def deal_results(result: DealResult, ai_button_key: str = "ai_btn") -> None:
    g = result.governance
    r = result.risk
    ai = result.ai_eval

    tier_header(g.approval_tier, g.is_blocked, g.primary_approver)

    m1, m2, m3 = st.columns(3)
    m1.metric("Risk Score", f"{r.numeric_score} / 100")
    m2.metric("Composite Risk", f"{_RISK_EMOJI[r.composite]} {r.composite}")
    m3.metric("Flags Raised", len(r.raised_flags))

    st.markdown("##### Risk Barometer")
    for dim in r.dimensions:
        risk_bar(dim.name, dim.score, dim.detail)

    if r.raised_flags:
        with st.expander(f"⚠️  {len(r.raised_flags)} flag(s) raised"):
            for flag in r.raised_flags:
                icon = "🔴" if "CRITICAL" in flag else ("🟠" if "HIGH" in flag or "PRIORITY" in flag else "🟡")
                st.markdown(f"{icon}  {flag}")

    with st.expander("💰  Commercial Metrics"):
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("ACV (List)", f"${g.acv_list:,.0f}")
        mc1.metric("TCV (List)", f"${g.tcv_list:,.0f}")
        mc2.metric("ACV (Discounted)", f"${g.acv_discounted:,.0f}")
        mc2.metric("TCV (Discounted)", f"${g.tcv_discounted:,.0f}")
        mc3.metric("Discount %", f"{g.discount_pct:.1f}%")
        mc3.metric("Discount $ (TCV)", f"${g.discount_value_dollars:,.0f}")

    if g.functional_approvals:
        with st.expander(f"🔗  {len(g.functional_approvals)} functional approval(s) required"):
            for fa in g.functional_approvals:
                st.markdown(f"• {fa}")

    # AI Evaluation
    st.markdown("##### AI Evaluation")
    if ai.provider != "none" and ai.recommended_action != "—":
        st.markdown(
            f"**Action:** {action_badge(ai.recommended_action)} &nbsp; *{ai.provider}*",
            unsafe_allow_html=True,
        )
        st.markdown(f"> {ai.narrative}")
        if ai.risk_observations and "No additional" not in ai.risk_observations and ai.risk_observations != "—":
            with st.expander("Additional observations"):
                st.markdown(ai.risk_observations)
    elif not _api_key_present():
        st.info("Add `ANTHROPIC_API_KEY` to `.env` to enable Claude AI evaluation.")
    else:
        if st.button("🤖  Run AI Evaluation", type="primary", key=ai_button_key):
            with st.spinner("Evaluating with Claude…"):
                try:
                    from agent.evaluator import evaluate_with_claude
                    ev = evaluate_with_claude(result.deal, result.governance, result.risk)
                    st.session_state[f"ai_{_deal_hash(result.deal)}"] = ev
                    st.rerun()
                except Exception as e:
                    st.error(f"AI evaluation failed: {e}")

    # Output documents
    with st.expander("📄  Manager Brief"):
        st.code(_manager_brief(result), language=None)
    with st.expander("📑  Deal Desk Report"):
        st.code(_deal_desk_report(result), language=None)


# ── Page layout ────────────────────────────────────────────────────────────
st.markdown("# 📋 Deal Desk Agent")
st.markdown("*Commercial governance · Risk scoring · Approval routing*")
st.divider()

tab_single, tab_batch = st.tabs(["🔍  Single Deal Analyzer", "📊  Portfolio View (CSV)"])


# ── Tab 1: Single Deal ─────────────────────────────────────────────────────
with tab_single:
    col_form, col_results = st.columns([2, 3], gap="large")

    with col_form:
        st.markdown("#### Deal Input")
        deal = deal_form(prefix="s_")

    with col_results:
        st.markdown("#### Analysis")
        gov = run_governance(deal)
        risk = score_risk(deal)
        dh = _deal_hash(deal)
        ai = st.session_state.get(f"ai_{dh}", _dummy_ai())
        result = DealResult(deal=deal, governance=gov, risk=risk, ai_eval=ai)
        deal_results(result, ai_button_key=f"ai_single_{dh}")


# ── Tab 2: Portfolio View ──────────────────────────────────────────────────
with tab_batch:
    st.markdown("#### Upload Deals CSV")
    uploaded = st.file_uploader("Choose a CSV file", type=["csv"], label_visibility="collapsed")

    if uploaded is None:
        st.info(
            "Upload a CSV to score a full portfolio. Expected columns: "
            "`deal_id, customer, segment, arr, list_price, discount_pct, "
            "contract_months, custom_terms, strategic_context, sales_rep, close_date, deal_stage`  \n"
            "Custom terms should be pipe-separated: `net-60|MSA-deviation`"
        )
        if st.button("Load sample data (deals.csv)"):
            try:
                with open("deals.csv") as f:
                    st.session_state["sample_csv"] = f.read()
                st.rerun()
            except FileNotFoundError:
                st.error("deals.csv not found in working directory.")
    else:
        content = uploaded.read().decode("utf-8")
        st.session_state["sample_csv"] = content

    csv_content = st.session_state.get("sample_csv")

    if csv_content:
        reader = csv_module.DictReader(io.StringIO(csv_content))
        portfolio: list[DealResult] = []
        parse_errors: list[str] = []

        for row in reader:
            try:
                raw_terms = row.get("custom_terms", "").strip()
                terms = [t.strip() for t in raw_terms.split("|") if t.strip()]
                d = DealRecord(
                    deal_id=row["deal_id"].strip(),
                    customer=row["customer"].strip(),
                    segment=row.get("segment", "").strip(),
                    arr=float(row["arr"]),
                    list_price=float(row["list_price"]),
                    discount_pct=float(row["discount_pct"]),
                    contract_months=int(row["contract_months"]),
                    custom_terms=terms,
                    strategic_context=row.get("strategic_context", "").strip(),
                    sales_rep=row.get("sales_rep", "").strip(),
                    close_date=row.get("close_date", "").strip(),
                    deal_stage=row.get("deal_stage", "").strip(),
                )
                g = run_governance(d)
                r = score_risk(d)
                ai = st.session_state.get(f"ai_{_deal_hash(d)}", _dummy_ai())
                portfolio.append(DealResult(deal=d, governance=g, risk=r, ai_eval=ai))
            except Exception as e:
                parse_errors.append(f"Row {row.get('deal_id', '?')}: {e}")

        for err in parse_errors:
            st.warning(err)

        if portfolio:
            # ── Portfolio summary cards ────────────────────────────────────
            st.markdown(f"#### Portfolio Overview — {len(portfolio)} deals")

            tier_counts: dict[str, int] = {}
            for res in portfolio:
                t = res.governance.approval_tier
                tier_counts[t] = tier_counts.get(t, 0) + 1

            s1, s2, s3, s4, s5 = st.columns(5)
            s1.metric("Total Deals", len(portfolio))
            s2.metric("✅ Standard", tier_counts.get("Standard", 0))
            s3.metric("📋 Mid-Tier", tier_counts.get("Mid-Tier", 0))
            s4.metric("🔼 Executive", tier_counts.get("Executive", 0))
            s5.metric("⛔ Strategic / Blocked", tier_counts.get("Strategic", 0))

            total_tcv = sum(r.governance.tcv_discounted for r in portfolio)
            blocked_tcv = sum(r.governance.tcv_discounted for r in portfolio if r.governance.is_blocked)
            avg_disc = sum(r.governance.discount_pct for r in portfolio) / len(portfolio)
            avg_risk = sum(r.risk.numeric_score for r in portfolio) / len(portfolio)

            f1, f2, f3, f4 = st.columns(4)
            f1.metric("Total Pipeline TCV", f"${total_tcv:,.0f}")
            f2.metric("Revenue at Risk (blocked)", f"${blocked_tcv:,.0f}")
            f3.metric("Avg. Discount", f"{avg_disc:.1f}%")
            f4.metric("Avg. Risk Score", f"{avg_risk:.0f} / 100")

            st.divider()

            # ── Portfolio table ────────────────────────────────────────────
            rows = []
            for res in portfolio:
                g = res.governance
                r = res.risk
                rows.append({
                    "Deal ID": res.deal.deal_id,
                    "Customer": res.deal.customer,
                    "Segment": res.deal.segment,
                    "Tier": f"{_TIER_EMOJI[g.approval_tier]} {g.approval_tier}",
                    "Discount %": f"{g.discount_pct:.1f}%",
                    "ACV (disc.)": f"${g.acv_discounted:,.0f}",
                    "TCV (disc.)": f"${g.tcv_discounted:,.0f}",
                    "Risk Score": f"{r.numeric_score}/100",
                    "Composite": f"{_RISK_EMOJI[r.composite]} {r.composite}",
                    "Flags": str(len(r.raised_flags)),
                    "Blocked": "⚠️ YES" if g.is_blocked else "—",
                })

            st.dataframe(rows, use_container_width=True, hide_index=True)

            # ── Deal drill-down ────────────────────────────────────────────
            st.divider()
            st.markdown("#### Deal Detail")
            deal_map = {res.deal.deal_id: res for res in portfolio}
            selected_id = st.selectbox(
                "Select a deal",
                options=list(deal_map.keys()),
                format_func=lambda did: f"{did}  ·  {deal_map[did].deal.customer}  ·  {_TIER_EMOJI[deal_map[did].governance.approval_tier]} {deal_map[did].governance.approval_tier}",
            )
            if selected_id:
                sel = deal_map[selected_id]
                # refresh AI eval from session state in case it was just run
                refreshed_ai = st.session_state.get(f"ai_{_deal_hash(sel.deal)}", sel.ai_eval)
                sel = DealResult(deal=sel.deal, governance=sel.governance, risk=sel.risk, ai_eval=refreshed_ai)
                deal_results(sel, ai_button_key=f"ai_batch_{selected_id}")

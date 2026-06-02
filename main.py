#!/usr/bin/env python3
"""
Deal Desk Agent — CLI entry point.

Usage:
  python main.py --deal deal.json          # single deal from JSON file
  python main.py --csv deals.csv           # batch process from CSV
  python main.py --csv deals.csv --no-ai   # skip Claude evaluation
"""
import argparse
import csv
import json
import os
import sys

from dotenv import load_dotenv

from agent import (
    DealRecord,
    evaluate_with_claude,
    generate_output,
    run_governance,
    score_risk,
)
from agent.models import AIEvaluation

load_dotenv()

MAX_DEALS_PER_BATCH = 200
MAX_JSON_BYTES = 1 * 1024 * 1024  # 1 MB


def _validate_deal(d: DealRecord) -> None:
    if not d.deal_id.strip():
        raise ValueError("deal_id cannot be empty")
    if not (0.0 <= d.discount_pct <= 100.0):
        raise ValueError(f"discount_pct {d.discount_pct} out of range [0, 100]")
    if d.arr < 0:
        raise ValueError(f"arr {d.arr} cannot be negative")
    if d.list_price <= 0:
        raise ValueError(f"list_price {d.list_price} must be positive")
    if d.contract_months <= 0:
        raise ValueError(f"contract_months {d.contract_months} must be a positive integer")


def _load_deal_from_json(path: str) -> DealRecord:
    if os.path.getsize(path) > MAX_JSON_BYTES:
        raise ValueError(f"Deal file exceeds {MAX_JSON_BYTES // 1024} KB limit")
    with open(path) as f:
        data = json.load(f)
    return DealRecord(
        deal_id=data["deal_id"],
        customer=data["customer"],
        segment=data.get("segment", ""),
        arr=float(data["arr"]),
        list_price=float(data["list_price"]),
        discount_pct=float(data["discount_pct"]),
        contract_months=int(data["contract_months"]),
        custom_terms=data.get("custom_terms", []),
        strategic_context=data.get("strategic_context", ""),
        sales_rep=data.get("sales_rep", ""),
        close_date=data.get("close_date", ""),
        deal_stage=data.get("deal_stage", ""),
    )


def _load_deals_from_csv(path: str) -> list[DealRecord]:
    deals = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_terms = row.get("custom_terms", "").strip()
            terms = [t.strip() for t in raw_terms.split("|") if t.strip()]
            deals.append(
                DealRecord(
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
            )
    return deals


def _no_ai_eval(gov) -> AIEvaluation:
    return AIEvaluation(
        narrative="AI evaluation skipped (--no-ai flag).",
        recommended_action="Escalate",
        risk_observations="No additional observations.",
        provider="none",
    )


def _print_summary(deal: DealRecord, gov, risk, ai_eval) -> None:
    tier_label = {
        "Standard": "L1 — Auto-approved",
        "Mid-Tier": "L2 — Deal Desk Manager approval required",
        "Executive": "L3 — VP Sales approval required",
        "Strategic": "L4 — C-Suite sign-off required  ⚠  BLOCKED",
    }.get(gov.approval_tier, gov.approval_tier)

    flags_summary = "; ".join(risk.raised_flags) if risk.raised_flags else "No flags raised"

    print(f"\n{'─' * 56}")
    print(f"  {deal.deal_id}  ·  {deal.customer}")
    print(f"{'─' * 56}")
    print(f"  Decision   : {tier_label}")
    print(f"  Risk score : {risk.numeric_score} / 100  ({risk.composite})")
    print(f"  Action     : {ai_eval.recommended_action}")
    print(f"  Flags      : {flags_summary}")
    print(f"  Routed to  : {gov.primary_approver}")
    print(f"{'─' * 56}\n")


def process_deal(deal: DealRecord, use_ai: bool, output_dir: str = "output") -> None:
    gov = run_governance(deal)
    risk = score_risk(deal)

    if use_ai:
        ai_eval = evaluate_with_claude(deal, gov, risk)
    else:
        ai_eval = _no_ai_eval(gov)

    from agent.models import DealResult
    result = DealResult(deal=deal, governance=gov, risk=risk, ai_eval=ai_eval)

    paths = generate_output(result, output_dir=output_dir)
    _print_summary(deal, gov, risk, ai_eval)
    print(f"  Manager Brief    → {paths['brief_path']}")
    print(f"  Deal Desk Report → {paths['report_path']}")
    print(f"  JSON             → {paths['json_path']}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deal Desk Agent")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--deal", metavar="FILE", help="Path to a single deal JSON file")
    group.add_argument("--csv", metavar="FILE", help="Path to a CSV file of deals")
    parser.add_argument("--no-ai", action="store_true", help="Skip Claude AI evaluation")
    parser.add_argument("--output-dir", default="output", help="Directory for output files (default: output/)")
    args = parser.parse_args()

    use_ai = not args.no_ai

    if args.deal:
        deal = _load_deal_from_json(args.deal)
        _validate_deal(deal)
        process_deal(deal, use_ai=use_ai, output_dir=args.output_dir)
    else:
        deals = _load_deals_from_csv(args.csv)
        if len(deals) > MAX_DEALS_PER_BATCH:
            print(f"ERROR: CSV contains {len(deals)} deals, max per batch is {MAX_DEALS_PER_BATCH}. Split the file.", file=sys.stderr)
            sys.exit(1)
        print(f"\nProcessing {len(deals)} deal(s) from {args.csv} ...\n")
        for deal in deals:
            try:
                _validate_deal(deal)
                process_deal(deal, use_ai=use_ai, output_dir=args.output_dir)
            except Exception as e:
                print(f"  ERROR processing {deal.deal_id}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()

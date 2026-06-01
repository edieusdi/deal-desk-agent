# Deal Desk Agent

An AI agent that evaluates enterprise deals, scores risk and discount exposure, and routes non-standard deals to the correct approval tier automatically.

---

## Introduction

Deal Desk Agent removes the manual triage step from enterprise deal review. It ingests a deal record, runs it through a configurable scoring model, and either auto-approves it or escalates it to the right person — without a human having to read every line item first.

It is designed to integrate into existing CRM and approval workflows rather than replace them.

---

## Purpose

Enterprise deal desks are bottlenecks. Reps wait days for discount approvals on deals that are straightforward, while genuinely risky deals get approved quickly because reviewers are overloaded.

This agent solves that by:

- **Scoring every deal** on risk factors (deal size, discount depth, customer segment, contract terms) in seconds
- **Auto-approving** deals that fall within policy thresholds, freeing reviewers for edge cases
- **Routing** non-standard deals to the correct approval tier with a structured summary, not a raw deal dump

---

## Architecture

```
                        ┌─────────────┐
Deal Record (JSON) ────▶│    Agent    │
                        └──────┬──────┘
                               │
                    ┌──────────▼──────────┐
                    │       Scorer        │
                    │  (risk + discount)  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │       Router        │
                    └──────────┬──────────┘
                               │
               ┌───────────────┼───────────────┐
               ▼               ▼               ▼
          L1 Auto-approve   L2 Manager     L3 VP / Legal
```

**Agent** — orchestrates the evaluation loop. Calls tools to enrich the deal record (customer history, segment rules) before scoring.

**Scorer** — computes two values: a *risk score* (0–100) based on deal structure, terms, and customer signals, and a *discount exposure score* (% off list vs. floor price). Both feed the routing decision.

**Router** — applies policy rules to map score combinations to approval tiers. Tier definitions are configurable per product line and region.

**Approval Tiers**
- L1 — within policy on both scores → auto-approved, logged
- L2 — moderate risk or discount breach → routed to account's manager with a structured summary
- L3 — high risk or deep discount → escalated to VP or Legal depending on breach type

---

## How to Use

**Prerequisites:** Python 3.11+, an Anthropic API key.

```bash
# Install dependencies
pip install -r requirements.txt

# Set your API key
export ANTHROPIC_API_KEY=sk-...

# Run the agent on a deal record
python main.py --deal deal.json
```

**Input format (`deal.json`):**

```json
{
  "deal_id": "DEAL-1234",
  "customer": "Acme Corp",
  "segment": "enterprise",
  "arr": 250000,
  "list_price": 300000,
  "discount_pct": 16.7,
  "contract_months": 24,
  "custom_terms": ["net-60", "audit-rights"]
}
```

**Output:** The agent prints a routing decision and writes a structured result to `output/DEAL-1234.json`.

```
Decision : L2 — Manager approval required
Risk score: 62 / 100
Reason   : Discount within policy; custom terms (audit-rights) require review
Routed to: jane.doe@company.com
```

For configuration options (tier thresholds, scoring weights, output destinations), see [`config/README.md`](config/README.md).

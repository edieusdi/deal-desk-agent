# Deal Desk Automation Agent

> AI agent that automates the end-to-end deal governance workflow for a SaaS sales organisation — scoring commercial risk, enforcing discount policy, and routing deals to the correct approval tier. Built with Python and the Anthropic / OpenAI API.

---

## Overview

Deal Desk Agent replaces ad-hoc spreadsheet reviews with a consistent, auditable process that enforces commercial standards at scale. When a deal is submitted, the agent ingests the raw deal data, applies discount governance policy, calculates every commercial metric, raises the appropriate risk flags, routes each deal to the correct approval tier, and produces structured, decision-ready output for both the Sales Manager and the Deal Desk team — all in a single run.

Enterprise deal desks are bottlenecks. Reps wait days for discount approvals on deals that are straightforward, while genuinely risky deals get approved quickly because reviewers are overloaded. This agent solves that by scoring every deal in seconds and routing it to the right person with a structured summary — not a raw deal dump.

It is designed to integrate into existing CRM and approval workflows rather than replace them.

---

## Features

- **AI-powered deal evaluation** — Claude or OpenAI scores each deal on risk and discount exposure using configurable weights across six risk dimensions
- **Governance engine** — calculates ACV, ARR, TCV, discounted values, and full discount value; classifies every deal into an approval tier before any output is produced
- **Risk Barometer** — six-dimension scoring model covering discount depth, contract term, non-standard flags, pricing compliance, finance terms, and legal/contractual risk
- **Approval tier routing** — maps score combinations to Standard / Mid-Tier / Executive / Strategic tiers automatically, with the correct named approver
- **Non-standard flag detection** — raises flags for custom payment terms, MFN clauses, bundled discounts, free months, MSA deviations, SLA deviations, and more
- **Dual output format** — produces a one-page Manager Brief and a full internal Deal Desk Report per deal
- **HubSpot CRM integration** — pulls live deal data by Deal ID; no manual data entry
- **Claude + OpenAI provider toggle** — switch AI backends via environment variable
- **Unquantifiable context input** — accepts strategic signals (logo impact, strategic value, competitive pressure) alongside structured deal data

---

## Architecture

The pipeline runs in three layers:

**Layer 1 — Intake.** Deal data is submitted via HubSpot Deal ID or a structured JSON record. Each deal carries the key commercial fields: customer name, ACV, discount, contract term, product, sales rep, close date, and deal stage.

**Layer 2 — Governance Engine.** Every deal is evaluated against the company's discount governance policy. The engine calculates ACV, ARR, TCV, and discounted values, classifies the deal into an approval tier, and raises risk flags where thresholds are breached. No deal advances until governance is fully applied.

**Layer 3 — Output Generation.** With governance complete, the pipeline produces two structured documents per deal — a Manager Brief and a full Deal Desk Report.

```
                        ┌─────────────┐
Deal Record (JSON) ────▶│    Agent    │
                        └──────┬──────┘
                               │
                    ┌──────────▼──────────┐
                    │   Governance Engine  │
                    │  (policy modules +  │
                    │   risk scoring)     │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │       Router        │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼──────────────────────┐
          ▼                    ▼                       ▼
 Standard (0–15%)     Mid-Tier (16–25%)      Executive / Strategic
 Auto-approved        Deal Desk Manager       VP Sales / C-Suite
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| AI Providers | Anthropic API · OpenAI API |
| CRM | HubSpot (free tier) |
| API Framework | FastAPI |
| Testing | pytest |
| Environment | python-dotenv |

---

## Prerequisites

- Python 3.11+
- An Anthropic API key — [console.anthropic.com](https://console.anthropic.com)
- Or an OpenAI API key — [platform.openai.com](https://platform.openai.com)
- A HubSpot account (free) — [hubspot.com](https://hubspot.com)
- A HubSpot private app access token

> **Note:** Claude.ai and ChatGPT subscriptions do not include API access. API access is billed separately by each provider.

---

## Setup

```bash
# 1. Clone the repository
git clone https://github.com/edieusdi/deal-desk-agent.git
cd deal-desk-agent

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and add your API keys (see Environment Variables below)

# 5. Run the agent on a deal record
python main.py --deal deal.json
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```env
# AI Provider — set the one you want to use
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# HubSpot
HUBSPOT_ACCESS_TOKEN=your_hubspot_private_app_token_here
```

**Never commit your `.env` file.** It is already included in `.gitignore`.

---

## Usage

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
Decision  : L2 — Deal Desk Manager approval required
Risk score: 62 / 100
Reason    : Discount within policy; custom terms (audit-rights) require Legal review
Routed to : jane.doe@company.com
```

---

## Approval Tiers

| Tier | Discount Range | Required Approver |
|---|---|---|
| Standard | 0% – 15% | No approval required — auto-approved and logged |
| Mid-Tier | 16% – 25% | Deal Desk Manager |
| Executive | 26% – 40% | VP of Sales |
| Strategic | Above 40% | C-Suite — deal blocked until signed off |

Functional approvals are required in addition to discount-tier approvals. Any deal with non-standard finance terms, MSA/SLA deviations, pricing below floor, channel partner structure, or a government customer triggers an additional approval route regardless of discount level.

---

## Risk Barometer

Every deal is scored across six dimensions. The composite risk rating equals the highest single-dimension score.

| Dimension | LOW | MEDIUM | HIGH | CRITICAL |
|---|---|---|---|---|
| Discount | 0%–15% | 16%–25% | 26%–40% | Above 40% — blocked |
| Contract Term | 24+ months | 12–23 months | Below 12 months — SHORT-TERM RISK | — |
| Non-Standard Flags | 0 flags | 1–2 flags | 3+ flags — full review required | — |
| Pricing Compliance | All SKUs at or above floor | — | — | Any SKU below floor — blocked |
| Finance Terms | Standard billing | One non-standard term | — | Multiple deviations — Finance escalation |
| Legal / Contractual | No deviations | Minor SLA deviation | MSA deviation — Legal approval | Material MSA changes — Legal countersign |

---

## Output Format

Every deal produces two documents:

**Output A — Manager Brief** (audience: Sales Manager, max one page)
- Deal Snapshot — customer, quote number, ACV, discount %, contract term, deal stage, quote expiry
- Risk Flags — flagged items only, each with severity (HIGH / MEDIUM / LOW)
- Recommended Action — one sentence: approve, escalate, or negotiate

**Output B — Deal Desk Report** (audience: Deal Desk team, internal use only)
- Full quote profile and all calculated commercial metrics (ACV, ARR, TCV, discounted values, discount value in dollars)
- All non-standard flags with risk explanation and required reviewer
- Risk Barometer scores across all six dimensions with composite rating
- Confirmed approval tier and all functional approval routes triggered
- Dashboard status and numbered next steps

---

## Key Metrics Tracked

**Commercial terms** — ACV (list and discounted), ARR, TCV (list and discounted), discount percentage, discount value in dollars, contract term, renewal date, booking quarter, sales category (new business / upsell / renewal).

**Risk flags** — HIGH PRIORITY (discount above 25%) and SHORT-TERM RISK (contract term below 12 months). Raised per deal and consolidated into a portfolio-level register.

**Portfolio health** — total pipeline value, total discounted pipeline value, blended discount rate, revenue at risk, deals pending approval by tier, days-to-close for time-sensitive deals.

---

## Running Tests

```bash
pytest
```

---

## Project Status

| Milestone | Status |
|---|---|
| Dev environment setup | ✅ Done |
| GitHub repo created | ✅ Done |
| Anthropic API integration | 🔄 In progress |
| Deal scoring logic | 🔄 In progress |
| HubSpot integration | 📅 Planned |
| OpenAI provider toggle | 📅 Planned |
| FastAPI endpoint | 📅 Planned |
| Test coverage (pytest) | 📅 Planned |
| v1 published | 📅 Planned |

---

## Roadmap

- [ ] Salesforce integration — pull deal records directly from Opportunity fields; write approval tier and risk flags back to the record on completion
- [ ] Automated approval routing — Executive and Strategic tier deals trigger Slack / email workflow to VP or C-suite with deal summary attached
- [ ] Monday.com integration — each processed deal creates or updates an item on the Deal Desk ops board with approval status, risk flags, and ACV
- [ ] RAG layer — feed past deal examples as case studies to improve AI evaluation
- [ ] Streamlit or React UI
- [ ] Contract Intelligence integration (Project 2)

---

## Author

**Edieusdi Ahmad**
[linkedin.com/in/edieusdi](https://linkedin.com/in/edieusdi) · [github.com/edieusdi](https://github.com/edieusdi)

---

## License

MIT

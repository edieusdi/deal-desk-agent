# CLAUDE.md — Deal Desk Agent

This file governs how AI assistants should work on this codebase. Read it before making any changes.

---

## Project purpose

Deal Desk Agent automates commercial deal governance for a SaaS sales organisation. It scores deals on risk, enforces discount policy, routes them to the correct approval tier, and produces structured output for Sales Managers and Deal Desk teams. The goal is to replace ad-hoc spreadsheet review with a consistent, auditable process.

---

## Repository structure

```
deal-desk-agent/
├── agent/
│   ├── models.py       # Core dataclasses: DealRecord, GovernanceResult, RiskScore, AIEvaluation, DealResult
│   ├── governance.py   # Deterministic engine: ACV/ARR/TCV calculations, approval tier routing, functional approvals
│   ├── risk.py         # Six-dimension risk barometer: returns RiskScore with per-dimension detail and numeric 0–100 score
│   ├── evaluator.py    # Claude API integration: forced tool_use, prompt injection protection, system prompt caching
│   ├── output.py       # Generates Manager Brief, Deal Desk Report, and JSON output files
│   └── __init__.py
├── app.py              # Streamlit frontend — Single Deal Analyzer + Portfolio CSV view
├── main.py             # CLI entry point — --deal (JSON), --csv, --no-ai flags
├── deals.csv           # Sample CSV with 7 deals covering all approval tiers and edge cases
├── tests/
│   ├── test_governance.py   # 12 tests: tier routing, commercial metrics, functional approvals
│   └── test_risk.py         # 23 tests: all six dimensions + composite + numeric score
├── output/             # Per-deal output files (gitignored except .gitkeep)
├── requirements.txt
└── .env.example
```

---

## How to run

```bash
# Install dependencies
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Copy and fill in your API key
cp .env.example .env

# Web app (recommended)
streamlit run app.py

# CLI — batch process
python main.py --csv deals.csv

# CLI — single deal
python main.py --deal deal.json

# CLI — skip AI (no API key needed)
python main.py --csv deals.csv --no-ai

# Tests
pytest
```

---

## Architecture — three layers

**Layer 1 — Intake.** `main.py` or `app.py` loads deal records from JSON or CSV and validates inputs (bounds, required fields). No deal progresses without passing validation.

**Layer 2 — Governance Engine (`agent/governance.py` + `agent/risk.py`).** Pure deterministic Python. No external calls. The governance engine calculates all commercial metrics and classifies the deal into an approval tier. The risk engine scores six dimensions and returns a composite rating and numeric score. These run on every request and must remain free of side effects.

**Layer 3 — AI Evaluation (`agent/evaluator.py`).** Claude is called via the Anthropic SDK with a forced `submit_evaluation` tool call. The AI adds qualitative judgment on top of the deterministic output — it does not replace or override the governance engine's decisions. In the CLI, AI evaluation is opt-in via the presence of `ANTHROPIC_API_KEY`. In the Streamlit app, it is triggered by an explicit button press to avoid unnecessary API calls.

**Output (`agent/output.py`).** Two text documents (Manager Brief, Deal Desk Report) and a JSON file are written per deal into `output/`. Files are created with `0600` permissions. File paths are sanitized against path traversal.

---

## Data model — key fields

`DealRecord` is the canonical input. The two financial fields that matter most:
- `list_price` — the undiscounted annual price (ACV at list)
- `arr` — the discounted annual recurring revenue (ACV after discount)
- `discount_pct` — these three must be consistent: `arr ≈ list_price × (1 − discount_pct/100)`

The governance engine derives everything else (TCV, discount value in dollars, approval tier) from these.

---

## Approval tiers

| Tier | Discount range | Approver |
|---|---|---|
| Standard | 0 – 15% | Auto-approved |
| Mid-Tier | 16 – 25% | Deal Desk Manager |
| Executive | 26 – 40% | VP of Sales |
| Strategic | > 40% | C-Suite — deal **blocked** |

Functional approvals (Finance, Legal, Compliance, Channel) are triggered by specific `custom_terms` values regardless of discount tier. See `governance.py` for the full term-to-approver mapping.

---

## Non-standard terms

`custom_terms` is a list of lowercase strings. The risk and governance engines classify terms into three buckets:

- **Finance terms** (`net-60`, `net-90`, `milestone-billing`, etc.) → Finance Director approval
- **Legal terms** (`MSA-deviation`, `SLA-deviation`, `MFN`, `audit-rights`, `material-MSA`, etc.) → Legal Counsel approval
- **Compliance flags** (`government`, `channel-partner`) → Legal/Compliance, Channel Manager
- **`below-floor`** → Pricing team, deal blocked

---

## Security constraints — do not change these without review

1. **Path traversal guard** — `output.py:_safe_filename()` and `_checked_path()` sanitize `deal_id` before it touches the filesystem. Do not remove or bypass these.
2. **Prompt injection protection** — `evaluator.py:_sanitize()` strips control characters and caps free-text fields at 500 chars. User-controlled strings are wrapped in XML tags in the prompt. Do not inline unsanitized user input into the system prompt or remove the XML delimiters.
3. **Input validation** — `main.py:_validate_deal()` enforces bounds on financial fields before any processing. Do not skip this call.
4. **Batch limit** — `MAX_DEALS_PER_BATCH = 200` guards against unbounded API cost on large CSV files. Raise it only with deliberate intent.
5. **Output file permissions** — files are written `0600`. Do not change to world-readable.
6. **Dependency pinning** — `requirements.txt` pins major version upper bounds. Do not widen to `>=` without a reason.

---

## Code conventions

- No comments unless the *why* is non-obvious — the code explains itself through naming.
- No docstrings beyond a single short line where needed.
- No backwards-compatibility shims or dead code — delete cleanly.
- Tests live in `tests/` and use plain `pytest` — no mocking the governance or risk engines, they are pure functions.
- New features that change the approval tier thresholds, risk dimension logic, or output format require updating the corresponding tests before the feature is considered done.

---

## What is not in scope (v1)

- HubSpot or Salesforce integration — planned, not built
- OpenAI provider toggle — planned, not built
- FastAPI endpoint — planned, not built
- Multi-user auth or session management
- Portfolio-level analytics beyond what Streamlit already shows

Do not add these unless explicitly requested.

---

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | For AI eval only | Claude API access |
| `OPENAI_API_KEY` | No | Reserved for future toggle |
| `HUBSPOT_ACCESS_TOKEN` | No | Reserved for future integration |

Never commit `.env`. It is in `.gitignore`.

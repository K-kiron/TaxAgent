# TaxAgent Canada

TaxAgent Canada is a local-first preparation workspace for a bounded 2025 Quebec and federal personal return. The implemented local workflow helps a user collect supported slips and facts, calculate covered federal and Quebec lines, review blockers, and export JSON or a review packet. It does not submit a return, request CRA/Revenu Quebec credentials, or claim filing certification.

The current calculation release is intentionally narrow: a full-year Canadian and Quebec resident, single, no dependants, covered salary/student facts, supported slips, and explicit confirmations for missing information, scholarships/RESP, student-loan interest, moving expenses, tips/other employment income, Schedule B, and additional T1/TP-1 filing screens. Unsupported facts block calculation instead of producing estimated numbers.

For the browser workflow, see [docs/user_guide.md](docs/user_guide.md). For the implemented form and exclusion matrix, see [docs/coverage.md](docs/coverage.md).

## Quickstart

Install the local web extra and start the browser workspace:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install ".[web]"
.\.venv\Scripts\taxagent.exe doctor
.\.venv\Scripts\taxagent.exe start
```

Open:

```text
http://127.0.0.1:8056
```

Useful local commands:

```powershell
.\.venv\Scripts\taxagent.exe doctor
.\.venv\Scripts\taxagent.exe rule-card list
.\.venv\Scripts\taxagent.exe calculate .\taxagent_slips.v1.json --output .\taxagent_calculation_packet.v1.json
.\.venv\Scripts\taxagent.exe profile --user demo --tax-year 2025
```

Modes:

* Local preparation/calculation mode: no submission and no model dependency. It collects explicit inputs, preserves provenance, and produces a line-by-line packet only for supported 2025 Quebec and federal cases.
* Example demo mode: canned examples only. These examples show product behavior and are secondary to the local preparation workspace.
* Live advisory mode: requires an explicit private OpenAI-compatible endpoint and `doctor --live` should pass before use.

### Local profile compatibility

Saved chat profiles are opt-in through `taxagent chat --user ...`. New profile filenames include a short hash of the exact user ID plus a `-tyYYYY` suffix when the tax year is known, so IDs such as `a/b` and `a?b` do not collide and the same user can keep separate years. Existing hashed or sanitized unsuffixed profile files are still read when their embedded user ID and tax year match; new year-specific saves leave those files in place. Calls that omit a tax year keep using the unsuffixed no-year profile path, so pass a tax year for deterministic year-specific reads. A persisted chat session is scoped to one tax year, so start a new `TaxSession` when switching years.

## Festival Demo

The web demo is safe-by-default for public sharing:

* The public URL opens a static scenario demo that does not call the model.
* Private live reasoning is disabled unless `TAXAGENT_DEMO_LIVE_ENABLED=1`.
* Live reasoning requires `X-Demo-Pin` / the UI PIN field and uses only an in-memory session.
* The web demo does not persist `.profiles` data.
* Keep vLLM on `127.0.0.1:8011`; expose only `127.0.0.1:8055` through a tunnel.

See [docs/festival_demo_runbook.md](docs/festival_demo_runbook.md) for the exact run, tunnel, and safety-check commands.

## Motivation

Personal tax filing is often not difficult because of arithmetic. It is difficult because users do not know how to map their real-life situation to the wording used by tax software and government forms.

Examples that motivated this project include:

* Whether a user had basic prescription drug insurance through a group insurance plan.
* How Québec RAMQ coverage, PR status, and Schedule K premium exemptions interact.
* Whether tuition carryforward amounts reduce tax payable, create refunds, or are simply carried forward.
* Why different tax software products surface different credits or questions.
* Whether a user should answer “Yes” to a tax shield, insurance, solidarity credit, or living-alone-related question.
* How to avoid overclaiming while still using credits and deductions the user is entitled to.

Most tax software is form-centric. This project explores an agent-centric workflow: the user explains their situation in natural language, the assistant identifies the relevant tax concepts, asks for evidence only when needed, and produces a transparent filing rationale.

## Product Vision

TaxAgent Canada aims to become a personal tax copilot for Canadian residents, with special attention to Québec-specific complexity.

The assistant should help users:

1. Understand what a tax software question actually means.
2. Identify which documents or records are needed.
3. Convert messy life events into tax-relevant facts.
4. Explain likely consequences before the user clicks an answer.
5. Detect inconsistencies across tax software outputs.
6. Provide source-backed reasoning for credits, premiums, deductions, and carryforwards.
7. Produce a concise audit trail showing why a choice was made.

Historical note: the advisory-only product vision is retained as background for the chat assistant. The current local release adds deterministic calculation only within the bounded 2025 Quebec preparation scope, and it still does not file a return, submit forms, or claim professional certification.

## Initial Scope

### Jurisdiction

Initial focus:

* Canada federal personal income tax.
* Québec personal income tax.
* Individual taxpayers with relatively common but confusing situations.

The product should be designed so that other provinces can be added later.

### User Types

Initial target users include:

* Students and recent graduates.
* New permanent residents.
* Interns and early-career workers.
* Québec residents dealing with RAMQ, group insurance, tuition credits, and provincial credits.
* Users comparing outputs across different tax software products.

### Supported Question Types

The assistant should initially handle questions such as:

* “What does this tax software question mean?”
* “Should I answer Yes or No based on my situation?”
* “Which document proves this?”
* “Why did this credit not increase my refund?”
* “Why does one tax software show this credit while another does not?”
* “Can I claim this amount, or should I leave it for CRA/Revenu Québec to adjust?”
* “What risks are there if I answer this incorrectly?”

## Core Design Principles

### 1. Source-grounded reasoning

TaxAgent should not rely on vague tax folklore. When the assistant gives tax-relevant guidance, it should ground the answer in official CRA, Revenu Québec, RAMQ, or tax-slip documentation whenever possible.

### 2. Distinguish facts, assumptions, and uncertainty

The assistant should explicitly separate:

* User-provided facts.
* Inferred facts.
* Missing evidence.
* Legal or procedural uncertainty.
* Recommended next steps.

### 3. Do not overclaim

The assistant should avoid saying “you are definitely eligible” unless the evidence is sufficient. Safer wording is preferred:

* “Based on the information provided, this appears likely.”
* “This depends on whether your employer-provided plan covered prescription drugs.”
* “You should verify this using your pay stub, benefits booklet, T4/RL slips, or insurer portal.”

### 4. Explain tax mechanics, not only answers

For example, tuition carryforward confusion often comes from misunderstanding the difference between:

* A deduction.
* A non-refundable tax credit.
* A refundable credit.
* Tax withheld.
* Tax payable.
* Refund generated by over-withholding.

The assistant should explain these mechanics in plain language.

### 5. Keep a filing rationale

Each recommendation should produce a short rationale that the user can save:

* Question asked by tax software.
* User facts considered.
* Evidence needed or provided.
* Recommended answer.
* Confidence level.
* Source references.
* Remaining risks.

## Example User Flows

These illustrate the product intent. The **testable, canonical** versions of
these flows (with expected behavior, rule-card mapping, and grading) are the
Golden Scenarios in [README_HARNESS.md](README_HARNESS.md) — when the two differ,
the harness doc wins.

### Flow 1: Group Prescription Drug Insurance

User asks:

> Did I have basic prescription drug insurance through a group insurance plan in 2025?

The assistant should:

1. Explain what “basic prescription drug insurance” means in tax context.
2. Ask whether the user had employer, internship, university, spouse, parent, or professional group coverage.
3. Suggest evidence:

   * Pay stubs.
   * Benefits booklet.
   * Employer HR portal.
   * Insurance card.
   * T4/RL slips.
   * RAMQ records.
4. Explain how uncertainty affects Québec Schedule K.
5. Provide a cautious recommendation.

### Flow 2: Québec RAMQ and PR Status

User asks:

> I became a PR mid-year and applied for RAMQ soon after. How should I think about the Québec prescription drug insurance premium?

The assistant should:

1. Build a month-by-month timeline.
2. Identify periods covered by RAMQ, private/group insurance, or possible exemption.
3. Explain that physical card arrival date may differ from eligibility or registration date.
4. Clarify what the tax software field is trying to compute.
5. Warn that the final assessment may be adjusted by Revenu Québec if official records differ.

### Flow 3: Tuition Carryforward

User asks:

> I have over $100,000 of unused tuition credits. Why did my refund not increase by that much?

The assistant should:

1. Explain that tuition credits are generally non-refundable.
2. Distinguish unused amount from cash value.
3. Explain that credits reduce tax payable, not income directly.
4. Show why a low-income internship year may use only part of the credit.
5. Explain that a large refund may come from tax withheld, not from tuition itself.

### Flow 4: Tax Software Comparison

User asks:

> TurboTax shows this question, but Wealthsimple Tax does not. Which one is right?

The assistant should:

1. Identify the underlying tax form or credit.
2. Explain that different software products may use different interview flows.
3. Determine whether the credit is hidden, automatic, conditional, or unsupported.
4. Suggest where to check in the generated forms.
5. Avoid assuming one product is correct without inspecting the forms.

## Proposed Architecture

```text
User
  |
  v
Conversation Interface
  |
  v
Tax Situation Parser
  |
  v
Fact Store + Evidence Tracker
  |
  v
Jurisdiction Router
  |
  +--> Federal Tax Knowledge Base
  +--> Québec Tax Knowledge Base
  +--> RAMQ / Insurance Knowledge Base
  +--> Tuition Credit Knowledge Base
  |
  v
Reasoning Engine
  |
  v
Recommendation + Filing Rationale
```

## Key Components

### Conversation Interface

Handles natural-language tax questions and follow-up clarification.

### Tax Situation Parser

Extracts structured facts:

* Province of residence.
* Immigration or residency timeline.
* Student status.
* Employment periods.
* Insurance coverage.
* Tuition carryforward.
* Tax slips.
* Software being used.
* Relevant tax year.

### Evidence Tracker

Tracks which claims are supported by documents and which are still uncertain.
The canonical field vocabularies (`UserFact.evidence_status` vs
`EvidenceItem.status` — they are different) live in
[README_HARNESS.md](README_HARNESS.md) → Data Models.

Example (a `UserFact`):

```json
{
  "key": "internship_employment_jan_to_jun_2025",
  "value": true,
  "confidence": "medium",
  "evidence_status": "user_reported",
  "notes": "Not yet corroborated by pay stub / T4 / RL-1"
}
```

### Jurisdiction Router

Routes questions to the relevant federal, Québec, RAMQ, or software-specific module.

### Knowledge Base

Stores source-backed tax rules, official references, form explanations, and reusable reasoning templates.

### Reasoning Engine

Combines user facts, source rules, and uncertainty handling to produce a recommendation.

### Filing Rationale Generator

Produces a compact explanation that can be saved by the user.

## Safety and Compliance

TaxAgent should be conservative by default. This is the product-level summary;
the enforceable Must-Do / Must-Not-Do list the harness tests against is the
canonical one in [README_HARNESS.md](README_HARNESS.md) → Safety Rules.

The assistant must:

* Avoid pretending to be a CPA, accountant, lawyer, CRA agent, or Revenu Québec representative.
* Avoid guaranteeing tax outcomes.
* Encourage professional help for high-risk cases.
* Cite official sources when giving rule-specific guidance.
* Distinguish tax software UI advice from legal tax advice.
* Preserve user privacy and avoid collecting unnecessary sensitive information.
* Never submit a return or alter government records without explicit user authorization and appropriate legal review.

## Non-goals for the Initial Version

The initial version should not:

* Automatically file tax returns.
* Replace certified tax professionals.
* Handle corporate tax.
* Handle aggressive tax planning.
* Guarantee refund amounts.
* Optimize for maximum refund without regard to correctness.
* Provide unsupported legal conclusions.
* Store sensitive documents without a privacy model.

## Development Roadmap

This is the **product** roadmap (what capability ships when). The **build order**
for the prototype harness — the concrete implementation milestones an agent works
through — is [README_HARNESS.md](README_HARNESS.md) → Implementation Milestones.
Phase 0–1 here are delivered by Harness Milestones 1–4.

### Phase 0: Research Prototype

* Define initial Québec-focused tax scenarios.
* Build a small set of source-backed reasoning templates.
* Create test conversations from real user pain points.
* Implement structured fact extraction.
* Implement confidence and evidence tracking.

### Phase 1: Tax Q&A Assistant

* Support natural-language explanations of tax software questions.
* Support Québec prescription drug insurance premium reasoning.
* Support tuition carryforward explanation.
* Support basic tax slip interpretation.
* Generate filing rationales.

### Phase 2: Document-aware Assistant

* Allow users to upload tax slips, pay stubs, insurance documents, and software screenshots.
* Extract relevant fields.
* Compare extracted facts against user statements.
* Flag missing or inconsistent evidence.

### Phase 3: Tax Software Copilot

* Guide users through TurboTax, Wealthsimple Tax, UFile, and similar platforms.
* Explain where to find generated forms.
* Compare estimated refund changes.
* Detect likely software interview omissions.

### Phase 4: Filing Workflow Integration

* Generate checklist before submission.
* Generate final rationale summary.
* Add exportable audit log.
* Explore integration with filing software or NETFILE workflows only after legal and compliance review.

## Example Output Format

The exact response contract (the eight parts, the `Recommendation` object they
render from, and how the harness grades them) is defined once in
[README_HARNESS.md](README_HARNESS.md) → Agent Response Contract. It is not
duplicated here to avoid drift.

## Repository Status

The repository now contains a bounded local preparation release for 2025 Quebec and federal returns. The implemented path includes packaged rule cards, a local browser workspace, typed JSON import/export, deterministic line-by-line calculation for the documented supported profile, blocked-result handling for unsupported facts, and CLI packaging checks.

Current limitations remain material: the app does not submit returns, is not CRA/Revenu Quebec certified, does not request government credentials, and blocks outside the documented 2025 Quebec salary/student scope. Historical advisory and product-vision notes are retained as design background; the implemented coverage boundary is [docs/coverage.md](docs/coverage.md).

## Disclaimer

This project is for educational and product research purposes. It does not provide certified tax, legal, accounting, or financial advice. Users should verify important decisions with official government sources or a qualified tax professional.

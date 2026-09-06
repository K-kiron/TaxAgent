# TaxAgent Canada

TaxAgent Canada is a local-first assistant for understanding Canadian personal tax questions, with special attention to Quebec-specific tax software and filing decisions. It helps users ask source-grounded questions, track facts across a conversation, inspect the rule-card knowledge base, and review evidence-aware recommendations.

TaxAgent does not submit returns, request CRA or Revenu Quebec credentials, connect to government accounts, or claim filing certification.

## Current scope

The current development branch provides an advisory command-line assistant and a rule-card knowledge base. It is useful for explaining tax-software questions, preserving a small opt-in profile, and reviewing the sources behind an answer.

It is not certified tax software and does not calculate or file a complete return from slips.

## Quickstart

Create a local environment and install the package:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
```

Ask a question:

```powershell
.\.venv\Scripts\taxagent.exe ask "What does the Quebec prescription drug insurance question mean?" --tax-year 2025 --show-cards
```

Start an opt-in local chat profile:

```powershell
.\.venv\Scripts\taxagent.exe chat --user demo --tax-year 2025
.\.venv\Scripts\taxagent.exe profile --user demo
```

Inspect available rule cards:

```powershell
.\.venv\Scripts\taxagent.exe rule-card list
```

Run the scenario harness:

```powershell
.\.venv\Scripts\taxagent.exe eval
```

## Privacy and local operation

The advisory CLI runs locally. Saved chat profiles are opt-in through `taxagent chat --user ...`; omit `--user` to avoid profile persistence. Local profile files are plaintext, so use a non-sensitive user ID and store the project in a location you trust.

## Documentation

- [README_HARNESS.md](README_HARNESS.md) documents the scenario harness, response contract, and evaluation checks.
- Rule cards live in `knowledge_base/` and contain the source-backed tax concepts used by the advisory assistant.

## Limitations

TaxAgent does not provide certified tax, legal, accounting, or financial advice. It does not guarantee outcomes, replace a qualified professional, or change records in CRA, Revenu Quebec, RAMQ, tax software, or financial accounts. Users should verify important decisions against official sources and their own records before filing.

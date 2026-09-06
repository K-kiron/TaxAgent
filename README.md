# TaxAgent Canada

TaxAgent Canada is a local-first preparation workspace for a bounded 2025 Quebec and federal personal return. It helps a user collect supported slips and facts, calculate covered federal and Quebec lines, review blockers, and export JSON or a calculation packet.

It does not submit a return, request CRA or Revenu Quebec credentials, connect to government accounts, or claim filing certification.

## Current scope

The current calculation release is intentionally narrow. It supports a full-year Canadian and Quebec resident who is single, has no dependants, and has covered salary/student facts with supported slips and explicit confirmations for missing information, scholarships or RESP payments, student-loan interest, moving expenses, tips or other employment income, Schedule B, and additional T1/TP-1 filing screens.

Unsupported facts block calculation instead of producing estimated numbers. The implemented form and exclusion matrix is documented in [docs/coverage.md](docs/coverage.md).

## Quickstart

Install the local web extra and start the browser workspace:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install ".[web]"
.\.venv\Scripts\taxagent.exe doctor
.\.venv\Scripts\taxagent.exe start
```

Open the local app:

```text
http://127.0.0.1:8056
```

## Useful commands

```powershell
.\.venv\Scripts\taxagent.exe doctor
.\.venv\Scripts\taxagent.exe rule-card list
.\.venv\Scripts\taxagent.exe calculate .\taxagent_slips.v1.json --output .\taxagent_calculation_packet.v1.json
.\.venv\Scripts\taxagent.exe profile --user demo --tax-year 2025
```

`taxagent calculate` reads a normalized JSON input file and writes a calculation packet. Completed packets include line values, provenance, source references, and federal/Quebec refund-or-balance fields. Blocked packets include blockers and omit headline refund-or-balance amounts until the missing or unsupported facts are resolved.

## Privacy and local operation

TaxAgent is designed to run locally for the supported preparation workflow. The local preparation/calculation path has no model dependency and does not call CRA, Revenu Quebec, or tax software accounts. Inputs and exported packets are plaintext files, so store them only in a location you trust.

Saved chat profiles are opt-in through `taxagent chat --user ...`. Profile filenames include a short hash of the exact user ID and, when known, a `-tyYYYY` suffix so the same user can keep separate years. Calls that omit a tax year keep using the unsuffixed no-year profile path, so pass a tax year for deterministic year-specific reads.

## Documentation

- [docs/user_guide.md](docs/user_guide.md) explains the browser workflow.
- [docs/coverage.md](docs/coverage.md) lists the supported profile, blockers, and covered 2025 federal/Quebec forms.
- [README_HARNESS.md](README_HARNESS.md) documents the test harness and response contract for maintainers.

## Limitations

TaxAgent is not certified tax software and does not provide certified tax, legal, accounting, or financial advice. It does not file returns, submit forms, optimize for unsupported credits, or replace review by official sources or a qualified tax professional. Users should verify important decisions against CRA, Revenu Quebec, and their own records before filing.

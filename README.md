<p align="center">
  <img src="assets/taxagent-logo.png" alt="TaxAgent Canada logo" width="128">
</p>

<h1 align="center">TaxAgent Canada</h1>

<p align="center">
  Local-first preparation workspace for a bounded 2025 Quebec and federal personal return.
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#what-it-does">What it does</a> ·
  <a href="#privacy">Privacy</a> ·
  <a href="docs/user_guide.md">User guide</a> ·
  <a href="docs/coverage.md">Coverage</a>
</p>

<p align="center">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square">
  <img alt="License: Apache-2.0" src="https://img.shields.io/badge/License-Apache--2.0-blue?style=flat-square">
  <img alt="Localhost app" src="https://img.shields.io/badge/Localhost-127.0.0.1-green?style=flat-square">
</p>

TaxAgent Canada helps a user collect supported slips and facts, calculate covered federal and Quebec return lines, review blockers, and export JSON or a human-readable review packet.

It does not submit a return, request CRA or Revenu Quebec credentials, connect to government accounts, or claim filing certification.

## Quick start

Clone this branch and install the local web extra.

<details open>
<summary>Windows PowerShell</summary>

```powershell
git clone --branch feat/issue-2-2025-tax-returns https://github.com/K-kiron/TaxAgent.git
cd TaxAgent
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install ".[web]"
.\.venv\Scripts\taxagent.exe doctor
.\.venv\Scripts\taxagent.exe start
```

Open `http://127.0.0.1:8056`.

</details>

<details>
<summary>Linux or macOS</summary>

```bash
git clone --branch feat/issue-2-2025-tax-returns https://github.com/K-kiron/TaxAgent.git
cd TaxAgent
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ".[web]"
taxagent doctor
taxagent start
```

Open `http://127.0.0.1:8056`.

</details>

## What it does

| Area | Current support |
| --- | --- |
| Return year | 2025 |
| Jurisdiction | Federal Canada + Quebec |
| Profile | Full-year Canadian and Quebec resident, single, no dependants, age 19 to 64 |
| Income path | Supported salary/student facts with explicit coverage questions |
| Slips | T4, RL-1, T4A, T5, RL-3, T2202, RRSP receipt, RC210, RL-19 supported fields |
| Output | Federal and Quebec line tables, schedules, blockers, warnings, source/provenance details, JSON export, text review packet |
| Filing | Review artifact only; no NETFILE, ReFILE, Revenu Quebec submission, or government-account access |

Unsupported facts block calculation instead of producing estimated numbers. The detailed profile, form-line coverage, and exclusions are in [docs/coverage.md](docs/coverage.md).

## Browser workflow

1. Check whether your situation fits the supported 2025 Quebec profile.
2. Enter supported slips, account-review facts, and required confirmations.
3. Calculate covered federal and Quebec return lines.
4. Review blockers, warnings, T1/TP-1 lines, schedules, and source details.
5. Save editable input JSON or a text review packet.

The browser supports structured JSON import and manual slip entry. A slip row can show a local PDF preview using the browser's built-in viewer, but this release does not extract boxes from PDFs or OCR scanned slips.

## CLI commands

```powershell
.\.venv\Scripts\taxagent.exe doctor
.\.venv\Scripts\taxagent.exe rule-card list
.\.venv\Scripts\taxagent.exe calculate .\taxagent_slips.v1.json --output .\taxagent_calculation_packet.v1.json
.\.venv\Scripts\taxagent.exe profile --user demo --tax-year 2025
```

`taxagent calculate` reads a normalized `TaxReturnInput` JSON file and writes a calculation packet. A complete packet includes line values, provenance, source references, and federal/Quebec refund-or-balance fields. A blocked packet includes blockers and omits headline refund-or-balance amounts until the missing or unsupported facts are resolved.

## Privacy

The local preparation workflow runs on loopback and has no model dependency for calculation. It does not call third-party services or transmit tax data to CRA, Revenu Quebec, or tax software accounts.

The browser keeps data in memory by default. Exported JSON and review packets are plaintext files on your computer, so store them only in a location you trust.

## Documentation

- [User guide](docs/user_guide.md) explains the browser workflow.
- [Coverage matrix](docs/coverage.md) lists supported forms, lines, blockers, and exclusions.

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Disclaimer

TaxAgent Canada is not certified tax software and does not provide certified tax, legal, accounting, or financial advice. Verify important decisions against official sources or a qualified professional before filing.

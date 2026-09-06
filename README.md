<p align="center">
  <img src="assets/taxagent-logo.png" alt="TaxAgent Canada logo" width="128">
</p>

<h1 align="center">TaxAgent Canada</h1>

<p align="center">
  Canada-first tax guidance and local preparation tools, with a careful Quebec focus.
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#documentation">Documentation</a> ·
  <a href="#scope">Scope</a> ·
  <a href="#license">License</a>
</p>

<p align="center">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square">
  <img alt="License: Apache-2.0" src="https://img.shields.io/badge/License-Apache--2.0-blue?style=flat-square">
</p>

TaxAgent Canada is an open-source project for helping individuals understand Canadian and Quebec tax questions, organize evidence, and review preparation outputs carefully.

The default branch is the public landing page. Use one of the source branches below for runnable code.

## Quick start

To try the local 2025 Quebec/federal preparation workspace:

```bash
git clone --branch feat/issue-2-2025-tax-returns https://github.com/K-kiron/TaxAgent.git
cd TaxAgent
```

<details open>
<summary>Windows PowerShell</summary>

```powershell
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
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ".[web]"
taxagent doctor
taxagent start
```

Open `http://127.0.0.1:8056`.

</details>

## Documentation

| Area | Link |
| --- | --- |
| Advisory CLI | [dev branch README](https://github.com/K-kiron/TaxAgent/blob/dev/README.md) |
| Local workspace preview | [feature branch README](https://github.com/K-kiron/TaxAgent/blob/feat/issue-2-2025-tax-returns/README.md) |

## Scope

| Area | Availability |
| --- | --- |
| Advisory CLI | Available on `dev`; uses source-backed rule cards and a configured OpenAI-compatible endpoint. |
| Local workspace preview | Available on `feat/issue-2-2025-tax-returns`; supports a bounded 2025 Quebec/federal preparation workflow. |

TaxAgent Canada is built around conservative tax help:

- explain tax-form and tax-software questions in plain language;
- separate user facts, evidence, uncertainty, and recommendations;
- use source-backed rule cards and transparent rationale where available;
- keep local preparation data under the user's control;
- block unsupported preparation cases instead of estimating beyond implemented coverage.

## Boundaries

TaxAgent Canada does not file returns, submit forms, request government credentials, connect to CRA or Revenu Quebec accounts, or claim filing certification.

It is not certified tax software and does not provide certified tax, legal, accounting, or financial advice. Verify important decisions against official government sources or a qualified professional before filing.

## License

Apache License 2.0. See [LICENSE](LICENSE).

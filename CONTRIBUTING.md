# Contributing to TaxAgent Canada

TaxAgent Canada is a local-first preparation prototype for a bounded Canadian and Quebec tax-preparation workflow. It does not file returns, submit to CRA or Revenu Quebec, request government credentials, or claim certification or authorization.

Please do not upload real tax slips, tax returns, government account screenshots, credentials, prompt logs, or personal tax facts to issues or pull requests. Use the synthetic fixtures in this repository, short redacted examples, or a minimal fake JSON example that reproduces the behavior.

## Useful Local Commands

Create a local environment:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install ".[test,web]"
```

Run the main checks:

```powershell
.\.venv\Scripts\python.exe scripts\release\provision_synthetic_pdf_fixtures.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\taxagent.exe doctor
```

Start the local app:

```powershell
.\.venv\Scripts\taxagent.exe start
```

## Good First Contribution Paths

- Documentation: clarify setup, supported scope, filing handoff limits, or terminology in English or French.
- Translation: add or improve French maintainer/user documentation while preserving the same limits as the English text.
- Testing: add focused tests for synthetic PDF intake, unsupported-case blockers, CLI output guards, or documentation examples.
- Tax-rule validation: compare implemented line behavior against cited CRA or Revenu Quebec public sources and open an issue with the exact source URL and synthetic reproduction.
- CLI ergonomics: improve error messages, command help, or local-file safety checks without adding network submission or account access.

When these issue templates are not yet available on GitHub's default branch, open a generic issue at `https://github.com/K-kiron/TaxAgent/issues/new` and follow the same safety rules above.

## Pull Request Expectations

- Keep changes scoped to one behavior or documentation improvement.
- Add tests for behavior changes and use synthetic data only.
- Preserve explicit blockers for unsupported tax situations instead of estimating silently.
- Do not add telemetry, analytics, tracking pixels, raw request logging, or automated user-data collection.
- Do not describe TaxAgent as certified, authorized, official, production tax software, or a replacement for professional advice.

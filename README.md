<p align="center">
  <img src="assets/taxagent-logo.png" alt="TaxAgent Canada logo" width="128">
</p>

<h1 align="center">TaxAgent Canada</h1>

<p align="center">
  Source-grounded Canadian tax guidance tools with a careful Quebec focus.
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#configure-the-advisory-endpoint">Endpoint config</a> ·
  <a href="#commands">Commands</a> ·
  <a href="#privacy">Privacy</a>
</p>

<p align="center">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square">
  <img alt="License: Apache-2.0" src="https://img.shields.io/badge/License-Apache--2.0-blue?style=flat-square">
  <img alt="CLI" src="https://img.shields.io/badge/Interface-CLI-lightgrey?style=flat-square">
</p>

TaxAgent Canada helps users reason through Canadian and Quebec personal tax questions by combining structured facts, source-backed rule cards, and conservative recommendations.

This branch is an advisory CLI prototype. It does not include the local 2025 calculation browser workspace, does not submit returns, and does not claim filing certification.

## Quick start

<details open>
<summary>Windows PowerShell</summary>

```powershell
git clone --branch dev https://github.com/K-kiron/TaxAgent.git
cd TaxAgent
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

</details>

<details>
<summary>Linux or macOS</summary>

```bash
git clone --branch dev https://github.com/K-kiron/TaxAgent.git
cd TaxAgent
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

</details>

## Configure the advisory endpoint

The advisory commands send prompts and structured context to the OpenAI-compatible endpoint you configure. The default development settings are:

| Variable | Default |
| --- | --- |
| `TAXAGENT_BASE_URL` | `http://127.0.0.1:8011/v1` |
| `TAXAGENT_MODEL` | `qwen` |
| `TAXAGENT_API_KEY` | `EMPTY` |
| `TAXAGENT_OUTPUT_MODE` | `native` |
| `TAXAGENT_TEMPERATURE` | `0` |
| `TAXAGENT_PROFILE_DIR` | `.profiles` inside the checkout |

Set these variables to match an endpoint you are authorized to use. TaxAgent does not provide upstream model access or credentials.

Windows PowerShell:

```powershell
$env:TAXAGENT_BASE_URL = "http://127.0.0.1:8011/v1"
$env:TAXAGENT_MODEL = "qwen"
$env:TAXAGENT_API_KEY = "EMPTY"
```

Linux or macOS:

```bash
export TAXAGENT_BASE_URL="http://127.0.0.1:8011/v1"
export TAXAGENT_MODEL="qwen"
export TAXAGENT_API_KEY="EMPTY"
```

## Commands

```powershell
.\.venv\Scripts\taxagent.exe ask "What does the Quebec prescription drug insurance question mean?" --tax-year 2025 --show-cards
.\.venv\Scripts\taxagent.exe chat --user demo --tax-year 2025
.\.venv\Scripts\taxagent.exe profile --user demo
.\.venv\Scripts\taxagent.exe eval --all
.\.venv\Scripts\taxagent.exe rule-card list --jurisdiction quebec
```

| Command | Purpose |
| --- | --- |
| `ask` | Answer one tax question through the configured advisory endpoint. |
| `chat` | Continue a local session and optionally save a local fact profile. |
| `profile` | Inspect a saved local profile. |
| `eval` | Run the scenario evaluation harness. |
| `rule-card list` | Inspect available source-backed rule cards. |

## Privacy

The CLI runs locally, but advisory prompts and relevant context are sent to the configured endpoint when you use `ask` or `chat`. Use a local endpoint if you want the advisory flow to stay on your machine.

Saved chat profiles are opt-in through `taxagent chat --user ...`. Omit `--user` to avoid profile persistence. Local profile files are plaintext, so use a non-sensitive user ID and store the checkout in a location you trust.

## Related branch

The local 2025 Quebec/federal preparation workspace is available on:

```bash
git clone --branch feat/issue-2-2025-tax-returns https://github.com/K-kiron/TaxAgent.git
```

That branch has its own README and browser quick start.

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Disclaimer

TaxAgent Canada is not certified tax software and does not provide certified tax, legal, accounting, or financial advice. Verify important decisions against official sources or a qualified professional before filing.

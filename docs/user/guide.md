# TaxAgent User Guide

TaxAgent is a local preparation workspace for a bounded Quebec salary/student profile. It helps you collect PDF slips, review extracted values, answer missing facts, calculate covered return lines, and export evidence for review.

It is not certified filing software. It does not submit to CRA or Revenu Quebec, use your government account, ask for CRA or Revenu Quebec credentials, or create filing-ready NETFILE, ReFILE, or NetFile Quebec files.

## 1. Install And Start

Use the development preview on the `dev` branch. The [project documentation](https://k-kiron.github.io/TaxAgent/) includes English and French setup and scope summaries.

Windows PowerShell:

```powershell
git clone --branch dev https://github.com/K-kiron/TaxAgent.git
cd TaxAgent
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install ".[web]"
.\.venv\Scripts\taxagent.exe doctor
.\.venv\Scripts\taxagent.exe start
```

Linux:

```bash
git clone --branch dev https://github.com/K-kiron/TaxAgent.git
cd TaxAgent
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ".[web]"
taxagent doctor
taxagent start
```

Open the [local TaxAgent app](http://127.0.0.1:8056). The server refuses non-localhost binds.

## 2. Collect Your Records

Gather the slips and facts before calculating:

- T4 and RL-1 for Quebec employment.
- T4A and RL-1 box O details for supported scholarships, bursaries, awards, or RESP educational assistance payments.
- T4E if employment insurance income is part of the year.
- T5 and RL-3 for supported interest income.
- T2202 and RL-8 or Quebec tuition receipts for tuition evidence.
- RRSP receipts, contribution period, prior unused contribution amount, contribution totals, and your deduction limit.
- RC210 and RL-19 for supported advance Canada workers benefit and Quebec work-premium amounts.
- Notices of assessment or account records for carryforwards, instalments, student-loan interest, and credit limits.

If a slip is missing, check with the issuer first. [CRA missing-slip guidance](https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/tax-slips/a-copy-your-tax-slips.html) says the CRA cannot provide a slip until the issuer sends it to CRA, and [CRA Auto-fill My Return](https://www.canada.ca/en/services/taxes/income-tax/personal-income-tax/how-file/tax-software/complete-return/auto-fill.html) only uses information CRA has on file at the time of the request. [Revenu Quebec Tax Data Download guidance](https://www.revenuquebec.ca/en/citizens/income-tax-return/filing-your-income-tax-return/filing-your-income-tax-return-online/) says users still have to check that all income is entered correctly.

For each missing slip, write down the issuer name, slip type, expected tax year, why you expected the slip, how you contacted the issuer, whether it appears in CRA or Revenu Quebec records, and what pay stub or statement you would use only if you must estimate before filing.

Official collection links:

- [CRA missing slips](https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/tax-slips/a-copy-your-tax-slips.html)
- [CRA Auto-fill My Return](https://www.canada.ca/en/services/taxes/income-tax/personal-income-tax/how-file/tax-software/complete-return/auto-fill.html)
- [Revenu Quebec My Account](https://www.revenuquebec.ca/en/citizens/my-account-for-individuals/)
- [Revenu Quebec filing online and Tax Data Download](https://www.revenuquebec.ca/en/citizens/income-tax-return/filing-your-income-tax-return/filing-your-income-tax-return-online/)

## 3. Import PDFs

On the PDFs step, drop PDF files into the import area or choose them from your computer. The importer reads local PDFs and creates a 2020-2025 workspace. It can use digital text, AcroForm fields, and bounded local OCR. Every extracted value remains reviewable.

Limits:

- 50 PDFs per batch.
- 25 MB of PDF content per batch.
- 80 pages per PDF.
- OCR budget of 12 pages, 24 million rendered pixels, and about 35 seconds per batch.
- 4 MB limit for restored JSON files and JSON API requests.

Some official forms are permission-encrypted but still readable without a password; the importer tries those with an empty password. PDFs that require a real password are rejected as encrypted because the app has no password prompt. If a PDF is password-required, save or obtain a readable copy and import that copy. Malformed, duplicate, unsupported, too-large, too-many-page, and resource-limited documents appear as file errors or review items.

PDF/OCR runs locally through installed package dependencies, including RapidOCR and ONNX Runtime. It does not use the advisory/model endpoint checked by `taxagent doctor --live`.

## 4. CLI Details

Most users can work through the browser, but the package also includes local CLI checks and JSON calculation.

Windows PowerShell:

```powershell
.\.venv\Scripts\taxagent.exe doctor
.\.venv\Scripts\taxagent.exe doctor --live
.\.venv\Scripts\taxagent.exe start
.\.venv\Scripts\taxagent.exe rule-card list
.\.venv\Scripts\taxagent.exe calculate .\taxagent_2025_qc_input.json --output .\taxagent_2025_qc_result.json
```

Linux:

```bash
taxagent doctor
taxagent doctor --live
taxagent start
taxagent rule-card list
taxagent calculate ./taxagent_2025_qc_input.json --output ./taxagent_2025_qc_result.json
```

`taxagent doctor` checks Python, bundled rule cards, static web assets, the web extra, PDF/OCR dependencies, the local calculation engine, and local profile-storage configuration. `taxagent calculate` accepts a normalized `TaxReturnInput` JSON file and writes a deterministic calculation packet. It returns a non-zero exit code when calculation is blocked.

`doctor --live` is separate from local preparation. It probes the configured advisory/model endpoint for older chat-style advisory features. The local return calculator and PDF intake do not need that endpoint.

## 5. Review Candidates And Years

Open the Years step after importing. The workspace always has buckets for 2020, 2021, 2022, 2023, 2024, and 2025.

Review items can include:

- A missing or unsupported year.
- A missing issuer.
- An ambiguous slip type.
- Low-confidence OCR or conflicting extracted values.
- Duplicate candidates.
- Multiple candidates for an original or amended slip.
- Unsupported boxes or slip branches.
- Tuition evidence conflicts between T2202 and RL-8.

Many clear slip candidates are accepted automatically. Use the review controls only for unresolved, duplicate, amended, unsupported, or unassigned candidates shown in the review queue. You can correct year, issuer, selected fields, or supported metadata when the app allows it, then apply review changes before calculating. For a year with no income slips, select that year and create an explicit no-slip year so the calculator has a deliberate record instead of an empty assumption.

Accepted evidence is stored in JSON with field values, accepted corrections, method, confidence, page number, bounding box when available, and source text. Original PDFs are not embedded.

## 6. Confirm Profile And Facts

TaxAgent currently supports a narrow persona: full-year Canadian and Quebec resident, Quebec province on December 31, single, no dependants, ordinary Quebec salary/student facts, and employment age 19 to 64.

The app blocks ordinary-but-not-yet-covered situations, including self-employment, capital gains, rental income, foreign income or tax, foreign property over $100,000, crypto, pension or benefit income, Indian Act exempt income, disability or caregiver claims, employment expenses, medical expenses, donations, childcare, moving expenses, tips or other employment income outside supported slips, deceased or bankruptcy returns, immigration or emigration in the tax year, Quebec trust returns, separate post-death returns, Quebec enterprise registration fees, QPP disability pension, CPT30 QPP/CPP election branches, non-Quebec employment, and unsupported credit or slip branches.

Answer the Profile and Review steps for the selected year. The app asks only for facts needed to clear blockers for the current supported profile. Unknown required facts block calculation.

When more than one active year shares the same profile facts, use Apply selected profile facts to other active years to copy chosen answers from the selected year. The action adjusts age by year and preserves existing destination answers unless you choose to overwrite them.

Select Calculate ready years once. The app processes active consecutive years in chronological order, carries proposed closing balances forward, and asks you to choose between an assessed opening balance and a proposed prior-year balance when they conflict.

## 7. Calculate And Export

Choose active years, then select Calculate ready years. The app calculates years that are ready and reports blockers for years that still need review.

Save only the files you want to keep:

- Save input JSON: editable single-year input or reviewed batch workspace.
- Save result JSON: calculation result plus workspace context.
- Save review packet: human-readable text summary.

Batch exports are named `taxagent_batch_workspace_reviewed.json`, `taxagent_batch_results.json`, and `taxagent_batch_review_packet.txt`. The current single-year screen exports `taxagent_2025_qc_input.json`, `taxagent_2025_qc_result.json`, and `taxagent_2025_qc_review_packet.txt`.

Saved JSON and review packets are plaintext. They include JSON evidence and accepted values, but not the original PDFs. If you restore JSON later, PDF previews are unavailable until you select the original PDFs again in that browser session.

Reset memory clears the current in-memory workspace, selected PDFs, review choices, and results. It does not delete files you already exported.

## 8. File Separately

Use TaxAgent outputs for review and preparation only. For actual filing, use a certified or authorized filing path that fits your situation.

- [CRA certified tax software and NETFILE information](https://www.canada.ca/en/services/taxes/income-tax/personal-income-tax/how-file/tax-software.html)
- [Revenu Quebec authorized personal income-tax software](https://www.revenuquebec.ca/en/partners/authorized-products/authorized-software/personal-income-tax-return-individuals/)
- [Revenu Quebec online filing guidance](https://www.revenuquebec.ca/en/citizens/income-tax-return/filing-your-income-tax-return/filing-your-income-tax-return-online/)

Do not send TaxAgent JSON or text packets to CRA or Revenu Quebec as filing documents.

# TaxAgent Local Return Workspace

TaxAgent's local workspace is an offline-first preparation tool for the 2025 Quebec salary/student return. Start it with:

```powershell
taxagent start
```

Then open `http://127.0.0.1:8056`. The app runs on loopback, does not call third-party services, does not use a language model for amounts, and does not submit a return to CRA or Revenu Quebec.

## Supported Use

The first supported profile is a 2025 full-year Canadian and Quebec resident, single, with no dependants, and with covered salary/student facts. Employment calculations are supported for ages 19 to 64; age 18 is currently blocked because QPP prorating is not yet covered. The workflow blocks calculation when a required fact is unknown or when the return includes an unsupported situation such as self-employment, capital gains, rental income, foreign income, medical expenses, donations, childcare, disability or caregiver claims, bankruptcy, deceased returns, special QPP/CPP contribution branches, immigration or emigration in 2025, Quebec trust-return filing, separate post-death returns, Quebec enterprise registration fees, or non-Quebec employment.

## Preparing Inputs

Use the Documents step to collect or enter:

- T4 and RL-1 pairs for Quebec employment, with issuer, document reference, box number, entered amount, T4 box 28 exemption indicators, and confirmation.
- T4A and RL-1 box O details when scholarships, bursaries, awards, or RESP educational assistance payments are present. Scholarship awards must reconcile to T4A box 105 and RL-1 box O code RB or RZ-RB by issuer. For part-time awards, enter each program cost pool once and reference that program from the award row. RESP EAP payments must reconcile to T4A box 042 and RL-1 box O code RU or RZ-RU by issuer.
- T5 and RL-3 pairs if supported interest income is present.
- T2202 and Quebec tuition or examination-fee receipts when current tuition is claimed. For T2202, box 24 is total part-time months, box 25 is total full-time months, and box 26 is total eligible tuition fees.
- RRSP receipts, receipt periods, prior unused contributions, period totals, and the deduction limit from the latest notice of assessment when RRSP contributions are claimed.
- RC210 and RL-19 slips if you received advance Canada workers benefit or Quebec work-premium payments.
- CRA and Revenu Quebec account review confirmations for missing issuers, slips, carryforwards, credit limits, instalment payments, drug-insurance months, student-loan interest amounts, scholarship and RESP facts, work-premium facts, Canada workers benefit facts, Quebec and federal student-status questions, Schedule B living-alone eligibility, moving-expense and tips/other-employment-income screening, additional T1/TP-1 filing screens, and solidarity credit facts.

The browser supports structured JSON import and manual entry. Each slip can show a local PDF preview beside the box-entry table, using the browser's built-in PDF viewer. The PDF stays in browser memory, is not sent to the local calculator, and is cleared when you remove the slip, import another JSON file, or reset. The app does not extract PDF slip boxes; transcribe the reviewed boxes yourself and confirm the slip.

## Privacy And Files

The browser keeps data in memory by default. Reset clears the current in-memory state and selected import file. Save/resume is explicit: use **Save input JSON** to export editable inputs, and **Import JSON** to load them later. Exported JSON and review packets are plaintext files on this computer and are not encrypted.

Do not enter SIN, account credentials, exact birthdate, full address, bank details, or any identifier that is not needed for the supported calculation. The local workflow blocks the Schedule D different-address branch instead of collecting address lines.

## Review And Filing

The Quebec work-premium full-time student answer is separate from the federal Canada workers benefit student answer. Revenu Quebec defines it using a term that began during 2025, at least 9 hours a week, and completion of that term: https://www.revenuquebec.ca/en/definitions/full-time-student/

After calculation, review blockers first. A complete result shows federal and Quebec refund or balance headlines in dollars and any preparation warnings beside them. The main T1 and TP-1 tables appear first, followed by collapsible schedules. Line tables show the value, status, official source links, and expandable calculation details supplied by the calculator. Use **Save result JSON** for machine-readable output and **Save review packet (.txt)** for a human-readable handoff.

The exports are not NETFILE, ReFILE, or Revenu Quebec electronic submission files. Federal and Quebec returns are filed separately through certified or authorized filing options.

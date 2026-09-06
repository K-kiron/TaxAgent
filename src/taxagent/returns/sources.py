"""Primary 2025 form sources used by the deterministic return engine."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SourceRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    form_id: str
    tax_year: int
    revision: str
    url: str
    retrieved_on: str = "2026-09-05"


def _source(id: str, title: str, form_id: str, revision: str, url: str) -> SourceRef:
    return SourceRef(
        id=id,
        title=title,
        form_id=form_id,
        tax_year=2025,
        revision=revision,
        url=url,
    )


SOURCES: dict[str, SourceRef] = {
    "cra_2025_5005_r": _source(
        "cra_2025_5005_r",
        "2025 Income Tax and Benefit Return for Quebec residents",
        "5005-R",
        "E (25)",
        "https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/5005-r/5005-r-fill-25e.pdf",
    ),
    "cra_2025_federal_worksheet": _source(
        "cra_2025_federal_worksheet",
        "2025 Federal Worksheet",
        "5000-D1",
        "E (25)",
        "https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/5000-d1/5000-d1-fill-25e.pdf",
    ),
    "cra_2025_schedule_6_qc": _source(
        "cra_2025_schedule_6_qc",
        "2025 Schedule 6 Canada Workers Benefit for Quebec",
        "5005-S6",
        "E (25)",
        "https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/5005-s6/5005-s6-fill-25e.pdf",
    ),
    "cra_2025_schedule_7": _source(
        "cra_2025_schedule_7",
        "2025 RRSP, PRPP and SPP Contributions and Transfers",
        "5000-S7",
        "E (25)",
        "https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/5000-s7/5000-s7-25e.pdf",
    ),
    "cra_2025_schedule_8_qc": _source(
        "cra_2025_schedule_8_qc",
        "2025 Schedule 8 Quebec Pension Plan Contributions",
        "5005-S8",
        "E (25)",
        "https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/5005-s8/5005-s8-fill-25e.pdf",
    ),
    "cra_2025_schedule_11_qc": _source(
        "cra_2025_schedule_11_qc",
        "2025 Schedule 11 Federal Tuition Amount and Canada Training Credit",
        "5005-S11",
        "E (25)",
        "https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/5005-s11/5005-s11-fill-25e.pdf",
    ),
    "cra_2025_schedule_10_qc": _source(
        "cra_2025_schedule_10_qc",
        "2025 Schedule 10 EI and PPIP Premiums",
        "5005-S10",
        "E (25)",
        "https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/5005-s10/5005-s10-fill-25e.pdf",
    ),
    "cra_2025_t2204": _source(
        "cra_2025_t2204",
        "2025 Employee Overpayment of Employment Insurance Premiums",
        "T2204",
        "E (25)",
        "https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2204/t2204-fill-25e.pdf",
    ),
    "cra_2025_line_31900": _source(
        "cra_2025_line_31900",
        "2025 Line 31900 Interest Paid on Student Loans",
        "T1-31900",
        "2025",
        "https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/deductions-credits-expenses/line-31900-interest-paid-on-your-student-loans.html",
    ),
    "cra_2025_p105": _source(
        "cra_2025_p105",
        "2025 Students and Income Tax",
        "P105",
        "2025",
        "https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/p105/p105-students-income-tax.html",
    ),
    "cra_2025_line_13010": _source(
        "cra_2025_line_13010",
        "2025 Line 13010 Scholarships, Fellowships, Bursaries and Awards",
        "T1-13010",
        "2025",
        "https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-13000-other-income/line-13010-scholarships-fellowships-bursaries-artists-project-grants-awards.html",
    ),
    "cra_2025_t4a": _source(
        "cra_2025_t4a",
        "2025 T4A Slip Amount Reporting Instructions",
        "T4A",
        "2025",
        "https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/tax-slips/understand-your-tax-slips/t4-slips/t4a-slip.html",
    ),
    "cra_2025_t691": _source(
        "cra_2025_t691",
        "2025 Alternative Minimum Tax",
        "T691",
        "E (25)",
        "https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t691/t691-fill-25e.pdf",
    ),
    "cra_2025_t2202": _source(
        "cra_2025_t2202",
        "2025 Tuition and Enrolment Certificate",
        "T2202",
        "2025",
        "https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2202/t2202-fill-25e.pdf",
    ),
    "rq_2025_tp1": _source(
        "rq_2025_tp1",
        "2025 Quebec Income Tax Return",
        "TP-1.D-V",
        "2025-12",
        "https://www.revenuquebec.ca/documents/en/formulaires/tp/2025-12/TP-1.D-V(2025-12).pdf",
    ),
    "rq_2025_schedule_b": _source(
        "rq_2025_schedule_b",
        "2025 Schedule B Tax Relief Measures",
        "TP-1.D.B-V",
        "2025-12",
        "https://www.revenuquebec.ca/documents/en/formulaires/tp/2025-12/TP-1.D.B-V(2025-12).pdf",
    ),
    "rq_2025_schedule_m": _source(
        "rq_2025_schedule_m",
        "2025 Schedule M Interest Paid on a Student Loan",
        "TP-1.D.M-V",
        "2025-12",
        "https://www.revenuquebec.ca/documents/en/formulaires/tp/2025-12/TP-1.D.M-V(2025-12).pdf",
    ),
    "rq_2025_line_154_scholarship": _source(
        "rq_2025_line_154_scholarship",
        "2025 TP-1 Line 154 Point 1 Scholarships and Bursaries",
        "TP1-154-01",
        "2025",
        "https://www.revenuquebec.ca/en/citizens/income-tax-return/completing-your-income-tax-return/how-to-complete-your-income-tax-return/line-by-line-help/96-to-164-total-income/line-154/point-1/",
    ),
    "rq_2025_line_154_resp": _source(
        "rq_2025_line_154_resp",
        "2025 TP-1 Line 154 Point 3 RESP Payments",
        "TP1-154-03",
        "2025",
        "https://www.revenuquebec.ca/en/citizens/income-tax-return/completing-your-income-tax-return/how-to-complete-your-income-tax-return/line-by-line-help/96-to-164-total-income/line-154/point-3/",
    ),
    "rq_2025_schedule_f": _source(
        "rq_2025_schedule_f",
        "2025 Schedule F Contribution to the Health Services Fund",
        "TP-1.D.F-V",
        "2025-12",
        "https://www.revenuquebec.ca/documents/en/formulaires/tp/2025-12/TP-1.D.F-V(2025-12).pdf",
    ),
    "rq_2025_line_457": _source(
        "rq_2025_line_457",
        "2025 TP-1 Line 457 QPIP Overpayment",
        "TP1-457",
        "2025",
        "https://www.revenuquebec.ca/en/citizens/income-tax-return/completing-your-income-tax-return/how-to-complete-your-income-tax-return/line-by-line-help/451-to-480-refund-or-balance-due/line-457/",
    ),
    "rq_2025_line_295": _source(
        "rq_2025_line_295",
        "2025 TP-1 Line 295 Deduction for Certain Income",
        "TP1-295",
        "2025",
        "https://www.revenuquebec.ca/en/citizens/income-tax-return/completing-your-income-tax-return/how-to-complete-your-income-tax-return/line-by-line-help/276-to-297-taxable-income/line-295/",
    ),
    "rq_2025_tp1_guide": _source(
        "rq_2025_tp1_guide",
        "2025 Guide to the Quebec Income Tax Return",
        "TP-1.G-V",
        "2025-12",
        "https://www.revenuquebec.ca/documents/en/formulaires/tp/2025-12/TP-1.G-V(2025-12).pdf",
    ),
    "rq_2025_work_charts": _source(
        "rq_2025_work_charts",
        "2025 Quebec Income Tax Return Work Charts",
        "TP-1.D.GR-V",
        "2025-12",
        "https://www.revenuquebec.ca/documents/en/formulaires/tp/2025-12/TP-1.D.GR-V(2025-12).pdf",
    ),
    "rq_2025_schedule_d": _source(
        "rq_2025_schedule_d",
        "2025 Schedule D Solidarity Tax Credit",
        "TP-1.D.D-V",
        "2025-12",
        "https://www.revenuquebec.ca/documents/en/formulaires/tp/2025-12/TP-1.D.D-V(2025-12).pdf",
    ),
    "rq_2025_schedule_k": _source(
        "rq_2025_schedule_k",
        "2025 Schedule K Quebec Prescription Drug Insurance Premium",
        "TP-1.D.K-V",
        "2025-12",
        "https://www.revenuquebec.ca/documents/en/formulaires/tp/2025-12/TP-1.D.K-V(2025-12).pdf",
    ),
    "rq_2025_schedule_p": _source(
        "rq_2025_schedule_p",
        "2025 Schedule P Work Premium Tax Credits",
        "TP-1.D.P-V",
        "2025-12",
        "https://www.revenuquebec.ca/documents/en/formulaires/tp/2025-12/TP-1.D.P-V(2025-12).pdf",
    ),
    "rq_2025_schedule_t": _source(
        "rq_2025_schedule_t",
        "2025 Schedule T Tuition or Examination Fees",
        "TP-1.D.T-V",
        "2025-12",
        "https://www.revenuquebec.ca/documents/en/formulaires/tp/2025-12/TP-1.D.T-V(2025-12).pdf",
    ),
    "rq_2025_schedule_u": _source(
        "rq_2025_schedule_u",
        "2025 Schedule U Quebec Pension Plan Contribution and Deduction",
        "TP-1.D.U-V",
        "2025-12",
        "https://www.revenuquebec.ca/documents/en/formulaires/tp/2025-12/TP-1.D.U-V(2025-12).pdf",
    ),
}

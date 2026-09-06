from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys
from types import SimpleNamespace

from PIL import Image, ImageDraw
import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from taxagent.intake import import_pdf_batch
import taxagent.intake.pdf as pdf_intake

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "pdf"
SYNTHETIC_DIR = FIXTURE_DIR / "synthetic"


def _text_pdf(lines: list[str]) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(612, 792))
    y = 742
    for line in lines:
        pdf.drawString(72, y, line)
        y -= 18
    pdf.save()
    return buffer.getvalue()


def _spatial_pdf(items: list[tuple[float, float, str]]) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(612, 792))
    for x, y, text in items:
        pdf.drawString(x, y, text)
    pdf.save()
    return buffer.getvalue()


def _spatial_pages(pages: list[list[tuple[float, float, str]]]) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(612, 792))
    for page in pages:
        for x, y, text in page:
            pdf.drawString(x, y, text)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _mixed_text_raster_pdf() -> bytes:
    image = Image.new("RGB", (1200, 400), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 50), "Tax year 2024", fill="black")
    draw.text((20, 100), "Employer name Raster Employer", fill="black")
    draw.text((20, 180), "Box 14 Employment income 45,000.00", fill="black")

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(612, 792))
    pdf.drawString(72, 750, "T4 Statement of Remuneration Paid")
    pdf.drawImage(ImageReader(image), 72, 450, width=468, height=180)
    pdf.save()
    return buffer.getvalue()


def _fixture(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


def _combine_pdfs(*pdfs: bytes) -> bytes:
    writer = PdfWriter()
    for pdf in pdfs:
        reader = PdfReader(BytesIO(pdf))
        for page in reader.pages:
            writer.add_page(page)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _synthetic_fixture(folder: str, name: str) -> bytes:
    path = SYNTHETIC_DIR / folder / name
    if not path.exists():
        raise AssertionError(
            "synthetic PDF fixture is unavailable; run "
            "python scripts/release/provision_synthetic_pdf_fixtures.py"
        )
    return path.read_bytes()


def _filled_synthetic_form(name: str, values: dict[str, str]) -> bytes:
    reader = PdfReader(BytesIO(_synthetic_fixture("acroforms", name)))
    if reader.is_encrypted:
        assert reader.decrypt("")
    writer = PdfWriter(clone_from=reader)
    writer.update_page_form_field_values(writer.pages[0], values, auto_regenerate=False)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _empty_user_encrypted_pdf(pdf_bytes: bytes) -> bytes:
    reader = PdfReader(BytesIO(pdf_bytes))
    writer = PdfWriter(clone_from=reader)
    writer.encrypt("", "owner-password")
    output = BytesIO()
    writer.write(output)
    encrypted = output.getvalue()
    assert PdfReader(BytesIO(encrypted)).is_encrypted
    return encrypted


def test_import_pdf_batch_accepts_strongly_anchored_t4_text_pdf():
    pdf_bytes = _fixture("t4_text_2025.pdf")

    result = import_pdf_batch([("example-t4.pdf", pdf_bytes)], enable_ocr=False)

    assert result.documents[0].status == "processed"
    candidate = result.candidates[0]
    assert candidate.slip_type == "T4"
    assert candidate.tax_year == 2025
    assert candidate.issuer_id == "Example Robotics Inc."
    assert candidate.amended_status == "original"
    assert candidate.decision == "accepted_auto"
    assert candidate.fields["14"].value == "45000.00"
    assert candidate.fields["14"].method == "digital_text"
    assert candidate.fields["14"].confidence >= 0.9
    assert candidate.fields["14"].page == 1
    assert candidate.fields["14"].bbox != (0.0, 0.0, 0.0, 0.0)
    assert "Employment income" in candidate.fields["14"].raw_text
    assert candidate.fields["14"].review_required is False


def test_import_pdf_batch_dedupes_exact_pdf_bytes():
    pdf_bytes = _text_pdf(
        [
            "T5 Statement of Investment Income",
            "Tax year 2024",
            "Payer name Example Bank",
            "Box 13 Interest from Canadian sources 123.45",
        ]
    )

    result = import_pdf_batch(
        [("copy-a.pdf", pdf_bytes), ("copy-b-with-different-name.pdf", pdf_bytes)],
        enable_ocr=False,
    )

    assert [document.status for document in result.documents] == ["processed", "duplicate"]
    assert result.candidates[1].decision == "duplicate"
    assert result.candidates[1].review_reasons == ["exact_duplicate"]


def test_import_pdf_batch_flags_conflicting_amended_copy_for_review():
    original = _text_pdf(
        [
            "T4 Statement of Remuneration Paid",
            "Tax year 2023",
            "Employer name Example Robotics Inc.",
            "Original",
            "Box 14 Employment income 45,000.00",
        ]
    )
    amended = _text_pdf(
        [
            "T4 Statement of Remuneration Paid",
            "Tax year 2023",
            "Employer name Example Robotics Inc.",
            "Amended",
            "Box 14 Employment income 47,000.00",
        ]
    )

    result = import_pdf_batch(
        [("original.pdf", original), ("amended.pdf", amended)], enable_ocr=False
    )

    assert [candidate.decision for candidate in result.candidates] == [
        "needs_review",
        "needs_review",
    ]
    assert result.candidates[1].amended_status == "amended"
    assert "conflicting_values_for_same_slip" in result.candidates[0].review_reasons
    assert "conflicting_values_for_same_slip" in result.candidates[1].review_reasons


def test_import_pdf_batch_does_not_conflict_on_non_overlapping_boxes():
    detailed = _fixture("t4_text_2025.pdf")
    partial = _fixture("t4_acroform_2025.pdf")

    result = import_pdf_batch(
        [("detailed.pdf", detailed), ("partial.pdf", partial)], enable_ocr=False
    )

    assert [candidate.decision for candidate in result.candidates] == [
        "accepted_auto",
        "accepted_auto",
    ]


def test_import_pdf_batch_uses_pdf_content_not_filename():
    result = import_pdf_batch(
        [("looks-like-t4-2025.pdf", _text_pdf(["Not a tax slip"]))], enable_ocr=False
    )

    assert result.documents[0].status == "unsupported"
    assert result.candidates == []


def test_import_pdf_batch_bounds_malformed_and_encrypted_pdfs():
    encrypted_source = BytesIO(_text_pdf(["T4 Statement of Remuneration Paid", "Tax year 2025"]))
    reader = PdfReader(encrypted_source)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt("secret")
    encrypted = BytesIO()
    writer.write(encrypted)

    result = import_pdf_batch(
        [("bad.pdf", b"%PDF-not-enough"), ("locked.pdf", encrypted.getvalue())],
        enable_ocr=False,
    )

    assert [document.status for document in result.documents] == ["malformed", "encrypted"]
    assert result.candidates == []


def test_import_pdf_batch_keeps_sensitive_identifiers_out_of_fields():
    pdf_bytes = _text_pdf(
        [
            "T4 Statement of Remuneration Paid",
            "Tax year 2025",
            "Employer name Example Robotics Inc.",
            "SIN 123 456 789",
            "Box 14 Employment income 45,000.00",
        ]
    )

    result = import_pdf_batch([("t4-with-sin.pdf", pdf_bytes)], enable_ocr=False)

    dumped = result.model_dump_json()
    assert "123 456 789" not in dumped
    assert result.candidates[0].fields["14"].value == "45000.00"


def test_import_pdf_batch_keeps_rrsp_receipt_period_distinct_from_printing_year():
    pdf_bytes = _fixture("rrsp_period_2025.pdf")

    result = import_pdf_batch([("rrsp.pdf", pdf_bytes)], enable_ocr=False)

    assert result.candidates[0].slip_type == "RRSP_RECEIPT"
    assert result.candidates[0].tax_year == 2025
    assert result.candidates[0].decision == "accepted_auto"


def test_import_pdf_batch_uses_rrsp_contribution_period_for_reporting_year():
    first_60_days = _text_pdf(
        [
            "RRSP contribution receipt",
            "Institution name Example Bank",
            "Issue date March 4, 2024",
            "Contribution period January 1 to March 3, 2025",
            "Contribution amount 1,500.00",
        ]
    )
    march_to_december = _text_pdf(
        [
            "RRSP contribution receipt",
            "Institution name Example Bank",
            "Issue date March 4, 2024",
            "Contribution period March 2 to December 31, 2025",
            "Contribution amount 2,500.00",
        ]
    )

    result = import_pdf_batch(
        [("first-60-days.pdf", first_60_days), ("march-december.pdf", march_to_december)],
        enable_ocr=False,
    )

    assert result.candidates[0].tax_year == 2024
    assert result.candidates[0].contribution_period == "first_60_days_2025"
    assert "first_60_days_2025" in result.candidates[0].fields["contribution_amount"].raw_text
    assert result.candidates[1].tax_year == 2025
    assert result.candidates[1].contribution_period == "march_to_december_2025"


def test_import_pdf_batch_reads_acroform_fields():
    pdf_bytes = _fixture("t4_acroform_2025.pdf")

    result = import_pdf_batch([("form-t4.pdf", pdf_bytes)], enable_ocr=False)

    candidate = result.candidates[0]
    assert candidate.decision == "accepted_auto"
    assert candidate.issuer_id == "Example Robotics Inc."
    assert candidate.fields["14"].method == "acroform"
    assert candidate.fields["14"].bbox != (0.0, 0.0, 0.0, 0.0)
    assert candidate.fields["14"].value == "45000.00"


def test_import_pdf_batch_reads_scanned_pdf_with_local_rapidocr():
    pdf_bytes = _fixture("t4_scan_2025.pdf")

    result = import_pdf_batch([("scan-t4.pdf", pdf_bytes)])

    assert result.candidates, result.model_dump(mode="json")
    candidate = result.candidates[0]
    assert candidate.slip_type == "T4"
    assert candidate.tax_year == 2025
    assert candidate.decision == "accepted_auto"
    assert candidate.fields["14"].method == "ocr_rapidocr"
    assert candidate.fields["14"].bbox != (0.0, 0.0, 0.0, 0.0)
    assert candidate.fields["14"].value == "45000.00"


def test_import_pdf_batch_reads_french_rl1_text_pdf():
    result = import_pdf_batch([("rl1.pdf", _fixture("rl1_french_2024.pdf"))], enable_ocr=False)

    candidate = result.candidates[0]
    assert candidate.slip_type == "RL-1"
    assert candidate.tax_year == 2024
    assert candidate.issuer_id == "Exemple Quebec Inc."
    assert candidate.fields["A"].value == "45000.00"
    assert candidate.fields["E"].value == "5100.00"


def test_import_pdf_batch_reviews_missing_year_and_unsupported_box():
    pdf_bytes = _text_pdf(
        [
            "T4 Statement of Remuneration Paid",
            "Employer name Example Robotics Inc.",
            "Box 999 Unsupported amount 123.45",
        ]
    )

    result = import_pdf_batch([("unsupported-box.pdf", pdf_bytes)], enable_ocr=False)

    candidate = result.candidates[0]
    assert candidate.decision == "needs_review"
    assert candidate.tax_year is None
    assert candidate.fields["999"].review_required is True
    assert "missing_tax_year" in candidate.review_reasons
    assert "unsupported_box:999" in candidate.review_reasons


def test_import_pdf_batch_preserves_t4_pandemic_and_qpp2_boxes():
    pandemic = _text_pdf(
        [
            "T4 Statement of Remuneration Paid",
            "Tax year 2020",
            "Employer name Example Robotics Inc.",
            "Box 14 Employment income 45,000.00",
            "Box 57 Employment income March 15 to May 9 8,000.00",
            "Box 58 Employment income May 10 to July 4 9,000.00",
            "Box 59 Employment income July 5 to August 29 10,000.00",
            "Box 60 Employment income August 30 to September 26 11,000.00",
        ]
    )
    qpp2 = _text_pdf(
        [
            "T4 Statement of Remuneration Paid",
            "Tax year 2024",
            "Employer name Example Robotics Inc.",
            "Box 14 Employment income 45,000.00",
            "Box 17A Employee second QPP contributions 120.00",
        ]
    )

    result = import_pdf_batch([("pandemic.pdf", pandemic), ("qpp2.pdf", qpp2)], enable_ocr=False)

    field_values = {box: field.value for box, field in result.candidates[0].fields.items()}
    assert field_values.items() >= {
        "57": "8000.00",
        "58": "9000.00",
        "59": "10000.00",
        "60": "11000.00",
    }.items()
    assert result.candidates[1].fields["17A"].value == "120.00"


def test_import_pdf_batch_splits_mixed_scanned_and_text_pages():
    t5 = _text_pdf(
        [
            "T5 Statement of Investment Income",
            "Tax year 2025",
            "Payer name Example Bank",
            "Box 13 Interest from Canadian sources 123.45",
        ]
    )
    mixed = _combine_pdfs(_fixture("t4_scan_2025.pdf"), t5)

    result = import_pdf_batch([("mixed.pdf", mixed)])

    observed = [(candidate.slip_type, candidate.tax_year) for candidate in result.candidates]
    assert observed == [
        ("T4", 2025),
        ("T5", 2025),
    ], result.model_dump(mode="json")
    assert result.candidates[0].fields["14"].method == "ocr_rapidocr"
    assert result.candidates[1].fields["13"].method == "digital_text"


def test_import_pdf_batch_reports_files_beyond_limit():
    first = _fixture("t4_text_2025.pdf")
    second = _fixture("rl1_french_2024.pdf")

    result = import_pdf_batch([("first.pdf", first), ("second.pdf", second)], max_files=1)

    assert [document.status for document in result.documents] == ["processed", "too_many_files"]
    assert len(result.candidates) == 1


def test_import_pdf_batch_does_not_logical_dedupe_without_issuer_identity():
    first = _text_pdf(
        [
            "T4 Statement of Remuneration Paid",
            "Tax year 2025",
            "Copy A",
            "Box 14 Employment income 1,000.00",
        ]
    )
    second = _text_pdf(
        [
            "T4 Statement of Remuneration Paid",
            "Tax year 2025",
            "Copy B",
            "Box 14 Employment income 1,000.00",
        ]
    )

    result = import_pdf_batch([("a.pdf", first), ("b.pdf", second)], enable_ocr=False)

    assert [candidate.decision for candidate in result.candidates] == [
        "needs_review",
        "needs_review",
    ]
    assert all(
        "logical_duplicate" not in " ".join(candidate.review_reasons)
        for candidate in result.candidates
    )


def test_import_pdf_batch_preserves_t4a_pandemic_boxes():
    pdf_bytes = _text_pdf(
        [
            "T4A Statement of Pension Retirement Annuity and Other Income",
            "Tax year 2020",
            "Payer name Example Benefits",
            "Box 197 Canada Emergency Response Benefit 2,000.00",
            "Box 198 Canada Emergency Student Benefit 1,250.00",
        ]
    )

    result = import_pdf_batch([("t4a-pandemic.pdf", pdf_bytes)], enable_ocr=False)

    assert result.candidates[0].slip_type == "T4A"
    assert result.candidates[0].fields["197"].review_required is False
    assert result.candidates[0].fields["198"].value == "1250.00"


def test_import_pdf_batch_recognizes_rl8_student_slip():
    pdf_bytes = _text_pdf(
        [
            "RL-8 Releve 8 Montant pour etudes postsecondaires",
            "Annee d'imposition 2025",
            "Institution name Example College",
            "Case A Montant pour etudes postsecondaires 3 000,00",
        ]
    )

    result = import_pdf_batch([("rl8.pdf", pdf_bytes)], enable_ocr=False)

    assert result.candidates[0].slip_type == "RL-8"
    assert result.candidates[0].fields["A"].review_required is False


def test_import_pdf_batch_preserves_annual_engine_raw_box_codes():
    pdf_bytes = _text_pdf(
        [
            "RL-1 Releve 1 Revenus emploi",
            "Annee d'imposition 2024",
            "Nom de l'employeur Exemple Quebec Inc.",
            "Case B.A Cotisation au RRQ 4,160.00",
            "Case B.B Deuxieme cotisation supplementaire au RRQ 188.00",
            "Case F Cotisation syndicale 25.00",
            "Case 211 Avantage imposable 0.00",
        ]
    )
    t4e = _text_pdf(
        [
            "T4E Statement of Employment Insurance and Other Benefits",
            "Tax year 2022",
            "Payer name Service Canada",
            "Box 14 Total benefits paid 3,000.00",
            "Box 30 Total repayment 400.00",
        ]
    )

    result = import_pdf_batch([("rl1.pdf", pdf_bytes), ("t4e.pdf", t4e)], enable_ocr=False)

    assert result.candidates[0].fields["B.A"].value == "4160.00"
    assert result.candidates[0].fields["B.B"].value == "188.00"
    assert result.candidates[0].fields["F"].value == "25.00"
    assert result.candidates[0].fields["211"].value == "0.00"
    assert result.candidates[1].fields["30"].value == "400.00"


def test_import_pdf_batch_reads_amount_before_source_box_anchor():
    pdf_bytes = _spatial_pdf(
        [
            (72, 750, "T4 Statement of Remuneration Paid"),
            (72, 730, "Tax year 2024"),
            (72, 710, "Employer name Example Robotics Inc."),
            (72, 650, "45,000.00"),
            (250, 650, "Employment income"),
            (500, 650, "14"),
        ]
    )

    result = import_pdf_batch([("synthetic-cell-t4.pdf", pdf_bytes)], enable_ocr=False)

    candidate = result.candidates[0]
    assert candidate.decision == "accepted_auto"
    assert candidate.fields["14"].value == "45000.00"


def test_import_pdf_batch_splits_side_by_side_t4_slips_on_one_page():
    pdf_bytes = _spatial_pdf(
        [
            (40, 750, "T4 Statement of Remuneration Paid"),
            (330, 750, "T4 Statement of Remuneration Paid"),
            (40, 730, "Tax year 2024"),
            (330, 730, "Tax year 2024"),
            (40, 710, "Employer name Employer Alpha"),
            (330, 710, "Employer name Employer Beta"),
            (40, 650, "Box 14 Employment income 10,000.00"),
            (330, 650, "Box 14 Employment income 20,000.00"),
        ]
    )

    result = import_pdf_batch([("two-t4s.pdf", pdf_bytes)], enable_ocr=False)

    observed = [
        (candidate.issuer_id, candidate.fields["14"].value) for candidate in result.candidates
    ]
    assert observed == [
        ("Employer Alpha", "10000.00"),
        ("Employer Beta", "20000.00"),
    ]
    assert [candidate.decision for candidate in result.candidates] == [
        "accepted_auto",
        "accepted_auto",
    ]


def test_import_pdf_batch_keeps_distinct_same_employer_slips_in_one_pdf():
    pdf_bytes = _spatial_pdf(
        [
            (40, 750, "T4 Statement of Remuneration Paid"),
            (330, 750, "T4 Statement of Remuneration Paid"),
            (40, 730, "Tax year 2025"),
            (330, 730, "Tax year 2025"),
            (40, 710, "Employer name Employer Alpha"),
            (330, 710, "Employer name Employer Alpha"),
            (40, 650, "Box 14 Employment income 10,000.00"),
            (330, 650, "Box 14 Employment income 20,000.00"),
        ]
    )

    result = import_pdf_batch([("employees.pdf", pdf_bytes)], enable_ocr=False)

    assert [candidate.decision for candidate in result.candidates] == [
        "accepted_auto",
        "accepted_auto",
    ]
    assert [candidate.fields["14"].value for candidate in result.candidates] == [
        "10000.00",
        "20000.00",
    ]


def test_import_pdf_batch_merges_continuation_page_fields():
    pdf_bytes = _spatial_pages(
        [
            [
                (72, 750, "T4 Statement of Remuneration Paid"),
                (72, 730, "Tax year 2024"),
                (72, 710, "Employer name Example Robotics Inc."),
                (72, 650, "Box 14 Employment income 45,000.00"),
            ],
            [
                (72, 750, "Continuation - other information"),
                (72, 700, "Box 44 Union dues 500.00"),
            ],
        ]
    )

    result = import_pdf_batch([("continued-t4.pdf", pdf_bytes)], enable_ocr=False)

    candidate = result.candidates[0]
    assert candidate.decision == "accepted_auto"
    assert candidate.fields["14"].page == 1
    assert candidate.fields["44"].page == 2
    assert candidate.fields["44"].value == "500.00"


def test_import_pdf_batch_ocr_reads_mixed_text_heading_and_raster_body():
    result = import_pdf_batch([("mixed-heading-scan.pdf", _mixed_text_raster_pdf())])

    assert result.candidates, result.model_dump(mode="json")
    candidate = result.candidates[0]
    assert candidate.decision == "accepted_auto"
    assert candidate.issuer_id == "Raster Employer"
    assert candidate.fields["14"].method == "ocr_rapidocr"
    assert candidate.fields["14"].value == "45000.00"


def test_local_rapidocr_limits_onnx_worker_threads(monkeypatch):
    configured: dict[str, object] = {}

    class FakeRapidOCR:
        def __init__(self, *, params: dict[str, object]):
            configured.update(params)

        def __call__(self, _bitmap: object) -> SimpleNamespace:
            return SimpleNamespace(txts=(), scores=(), boxes=None)

    monkeypatch.setitem(sys.modules, "rapidocr", SimpleNamespace(RapidOCR=FakeRapidOCR))
    monkeypatch.setattr(pdf_intake, "_OCR_ENGINE", None)
    monkeypatch.setattr(pdf_intake.sys, "platform", "linux")

    assert pdf_intake._run_local_ocr(object()) == ([], [], [])
    assert configured == {
        "EngineConfig.onnxruntime.intra_op_num_threads": 1,
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
    }


def test_import_pdf_batch_marks_explicit_unsupported_year():
    pdf_bytes = _text_pdf(
        [
            "T4 Statement of Remuneration Paid",
            "Tax year 2026",
            "Employer name Example Robotics Inc.",
            "Box 14 Employment income 45,000.00",
        ]
    )

    result = import_pdf_batch([("unsupported-2026.pdf", pdf_bytes)], enable_ocr=False)

    candidate = result.candidates[0]
    assert candidate.tax_year == 2026
    assert candidate.decision == "needs_review"
    assert "unsupported_tax_year" in candidate.review_reasons


def test_import_pdf_batch_requires_t4_income_for_auto_accept():
    pdf_bytes = _text_pdf(
        [
            "T4 Statement of Remuneration Paid",
            "Tax year 2024",
            "Employer name Example Robotics Inc.",
            "Box 44 Union dues 500.00",
        ]
    )

    result = import_pdf_batch([("box-44-only-t4.pdf", pdf_bytes)], enable_ocr=False)

    candidate = result.candidates[0]
    assert candidate.decision == "needs_review"
    assert candidate.fields["44"].value == "500.00"
    assert "missing_required_box:14" in candidate.review_reasons


@pytest.mark.parametrize(
    "name",
    [
        "synthetic-t4-2025.pdf",
        "synthetic-t4-2024.pdf",
        "synthetic-t2202-2025.pdf",
        "synthetic-t2202-2024.pdf",
        "synthetic-rl1-2025.pdf",
        "synthetic-rl1-2024.pdf",
        "synthetic-rl8-2022.pdf",
    ],
)
def test_synthetic_permission_encrypted_forms_are_readable(name: str):
    pdf = _empty_user_encrypted_pdf(_synthetic_fixture("acroforms", name))
    result = import_pdf_batch([(name, pdf)], enable_ocr=False)

    assert result.documents[0].status in {"processed", "unsupported"}
    assert result.documents[0].page_count > 0


def test_filled_synthetic_t4_acroform_maps_widgets_and_dedupes_recipient_copy():
    values = {
        "Slip1EmployersName[0]": "EXAMPLE ROBOTICS INC.",
        "Slip1Year[0]": "2025",
        "Slip1Box14[0]": "48000.00",
        "Slip1Box22[0]": "5000.00",
        "Slip1EmployersName[0].2": "EXAMPLE ROBOTICS INC.",
        "Slip1Year[0].2": "2025",
        "Slip1Box14[0].2": "48000.00",
        "Slip1Box22[0].2": "5000.00",
    }
    result = import_pdf_batch(
        [("synthetic-t4.pdf", _filled_synthetic_form("synthetic-t4-2025.pdf", values))],
        enable_ocr=False,
    )

    accepted = [
        candidate for candidate in result.candidates if candidate.decision == "accepted_auto"
    ]
    assert len(accepted) == 1
    candidate = accepted[0]
    assert candidate.issuer_id == "EXAMPLE ROBOTICS INC."
    assert candidate.tax_year == 2025
    assert {box: field.value for box, field in candidate.fields.items()} == {
        "14": "48000.00",
        "22": "5000.00",
    }
    assert all(field.method == "acroform" and field.bbox for field in candidate.fields.values())
    assert len(
        [candidate for candidate in result.candidates if candidate.decision == "duplicate"]
    ) == 1


def test_filled_synthetic_rl1_acroform_maps_widgets_and_issuer():
    pdf = _filled_synthetic_form(
        "synthetic-rl1-2025.pdf",
        {"nom2": "EXAMPLE ROBOTICS INC.", "caseA": "48000.00", "caseE": "5000.00"},
    )
    candidate = import_pdf_batch([("synthetic-rl1.pdf", pdf)], enable_ocr=False).candidates[0]

    assert candidate.decision == "accepted_auto"
    assert candidate.issuer_id == "EXAMPLE ROBOTICS INC."
    assert candidate.tax_year == 2025
    assert candidate.fields["A"].value == "48000.00"
    assert candidate.fields["E"].value == "5000.00"


def test_filled_synthetic_student_forms_map_t2202_and_rl8_fields():
    t2202 = _filled_synthetic_form(
        "synthetic-t2202-2025.pdf",
        {
            "Slip1Year[0]": "2025",
            "Part1_Name_Address[0]": "EXAMPLE COLLEGE",
            "Totals_Box26_row5[0]": "7000.00",
        },
    )
    rl8 = _filled_synthetic_form(
        "synthetic-rl8-2022.pdf",
        {"an": "2025", "nom2": "EXAMPLE COLLEGE", "caseA": "3000.00", "caseB1": "7000.00"},
    )
    result = import_pdf_batch([("t2202.pdf", t2202), ("rl8.pdf", rl8)], enable_ocr=False)
    accepted = [
        candidate for candidate in result.candidates if candidate.decision == "accepted_auto"
    ]

    assert [(candidate.slip_type, candidate.tax_year) for candidate in accepted] == [
        ("T2202", 2025),
        ("RL-8", 2025),
    ]
    assert accepted[0].fields["26"].value == "7000.00"
    assert {box: field.value for box, field in accepted[1].fields.items()} == {
        "A": "3000.00",
        "B": "7000.00",
    }


def test_synthetic_release_text_pdfs_import_expected_slips_and_fields():
    t4 = _synthetic_fixture("generated/release", "release-synthetic-t4-2025.pdf")
    rl1 = _synthetic_fixture("generated/release", "release-synthetic-rl1-2025.pdf")
    result = import_pdf_batch([("t4.pdf", t4), ("rl1.pdf", rl1)])
    accepted = [
        candidate for candidate in result.candidates if candidate.decision == "accepted_auto"
    ]

    assert [(candidate.slip_type, candidate.issuer_id) for candidate in accepted] == [
        ("T4", "EXAMPLE ROBOTICS INC"),
        ("RL-1", "EXAMPLE ROBOTICS INC"),
    ]
    assert accepted[0].fields["14"].value == "50000.00"
    assert accepted[0].fields["22"].value == "6000.00"
    assert accepted[1].fields["A"].value == "50000.00"
    assert accepted[1].fields["E"].value == "5000.00"
    assert all(
        field.bbox and field.page == 1
        for candidate in accepted
        for field in candidate.fields.values()
    )


def test_synthetic_t4_instruction_page_is_not_a_candidate():
    pdf = _synthetic_fixture("acroforms", "synthetic-t4-instructions-2025.pdf")
    result = import_pdf_batch([("t4.pdf", pdf)], enable_ocr=False)

    assert all(candidate.tax_year != 2020 for candidate in result.candidates)
    assert len(result.candidates) <= 2


def test_ocr_deadline_returns_typed_resource_limit_before_rendering():
    result = import_pdf_batch(
        [("scan.pdf", _fixture("t4_scan_2025.pdf"))],
        max_ocr_seconds=0,
    )

    assert result.documents[0].status == "resource_limited"
    assert result.candidates == []


def test_t4a_resp_box_042_preserves_leading_zero():
    pdf = _text_pdf(
        [
            "T4A Statement of Pension Retirement Annuity and Other Income",
            "Tax year 2025",
            "Payer name Example RESP Trust",
            "Box 042 RESP educational assistance payments 2,500.00",
        ]
    )
    candidate = import_pdf_batch([("t4a.pdf", pdf)], enable_ocr=False).candidates[0]

    assert candidate.fields["042"].value == "2500.00"

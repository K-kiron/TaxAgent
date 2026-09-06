"""Bounded local PDF slip extraction."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO
import re
from threading import Lock
from time import monotonic

import pypdfium2
from pypdf import PdfReader

from .execution import DEFAULT_WORKER_MODULE, run_import_one_pdf_worker
from .models import ExtractedField, ImportedDocument, ImportedSlipCandidate, PdfImportBatchResult


PdfInput = bytes | tuple[str, bytes]
_PDF_WORKER_MODULE = DEFAULT_WORKER_MODULE
SUPPORTED_YEARS = set(range(2020, 2026))
SUPPORTED_BOXES = {
    "T4": {
        "14",
        "16",
        "17",
        "17A",
        "18",
        "20",
        "22",
        "24",
        "26",
        "44",
        "46",
        "50",
        "52",
        "55",
        "56",
        "57",
        "58",
        "59",
        "60",
    },
    "T4A": {
        "042",
        "16",
        "18",
        "20",
        "22",
        "48",
        "105",
        "197",
        "198",
        "199",
        "200",
        "201",
        "202",
        "203",
        "204",
    },
    "T4E": {"7", "14", "15", "17", "18", "19", "20", "21", "22", "23", "26", "27", "30"},
    "T5": {"10", "11", "12", "13", "14", "15", "16", "17", "18", "19"},
    "RL-1": {"A", "B", "B.A", "B.B", "C", "D", "E", "F", "G", "H", "I", "J", "O", "211"},
    "RL-3": {"A", "B", "C", "D", "E", "F", "G", "H"},
    "RL-19": {"A", "B", "C", "D", "E"},
    "RC210": {"10", "11"},
    "T2202": {"24", "25", "26", "27"},
    "RL-8": {"A", "B", "C", "D"},
    "RRSP_RECEIPT": {"contribution_amount"},
}
REQUIRED_AUTO_BOXES = {
    "T4": {"14"},
    "T2202": {"26"},
    "RRSP_RECEIPT": {"contribution_amount"},
}
SENSITIVE_LINE = re.compile(r"\b(?:SIN|NAS|social insurance|account number|no de compte)\b", re.I)
YEAR_RE = re.compile(r"\b(20\d{2})\b")
BOX_RE = re.compile(r"\b(?:box|case)\s+([A-Z](?:\.[A-Z])?|\d{1,3}[A-Z]?)\b", re.I)
END_MONEY_RE = re.compile(r"(-?\$?\s*(?:\d{1,3}(?:[ ,]\d{3})+|\d+)(?:[.,]\d{2}))\s*$")
MONEY_RE = re.compile(r"\b(-?\$?\s*(?:\d{1,3}(?:[ ,]\d{3})+|\d+)(?:[.,]\d{2}))\b")


@dataclass(frozen=True)
class TextWord:
    text: str
    bbox: tuple[float, float, float, float]
    confidence: float = 0.96


@dataclass(frozen=True)
class FormField:
    name: str
    value: str
    page: int
    bbox: tuple[float, float, float, float] | None
    alternate_name: str | None


class OcrSession:
    """A lazy local OCR engine with one batch-wide work allowance."""

    def __init__(self, max_pages: int, max_rendered_pixels: int, max_seconds: float) -> None:
        self.max_pages = max_pages
        self.max_rendered_pixels = max_rendered_pixels
        self.deadline = monotonic() + max_seconds
        self.pages_used = 0
        self.pixels_used = 0
        self.exhausted = False

    def admit(self, width: int, height: int) -> bool:
        pixels = width * height
        if (
            monotonic() >= self.deadline
            or self.pages_used >= self.max_pages
            or self.pixels_used + pixels > self.max_rendered_pixels
        ):
            self.exhausted = True
            return False
        self.pages_used += 1
        self.pixels_used += pixels
        return True

    def recognize(self, bitmap: object) -> tuple[list[str], list[float], list[object]] | None:
        if monotonic() >= self.deadline:
            self.exhausted = True
            return None
        result = _run_local_ocr(bitmap)
        if monotonic() > self.deadline:
            self.exhausted = True
            return None
        return result


_OCR_ENGINE: object | None = None
_OCR_ENGINE_LOCK = Lock()


def _run_local_ocr(bitmap: object) -> tuple[list[str], list[float], list[object]]:
    global _OCR_ENGINE
    with _OCR_ENGINE_LOCK:
        if _OCR_ENGINE is None:
            from rapidocr import RapidOCR

            _OCR_ENGINE = RapidOCR()
        result = _OCR_ENGINE(bitmap)
        texts = [str(item) for item in (getattr(result, "txts", None) or [])]
        scores = [float(item) for item in (getattr(result, "scores", None) or [])]
        result_boxes = getattr(result, "boxes", None)
        boxes = [item.tolist() for item in result_boxes] if result_boxes is not None else []
        return texts, scores, boxes


@dataclass(frozen=True)
class BoxHit:
    box: str
    start: int
    end: int


@dataclass(frozen=True)
class PageText:
    page: int
    text: str
    method: str
    confidence: float
    line_bboxes: dict[str, tuple[float, float, float, float]]
    line_methods: dict[str, str]
    line_confidences: dict[str, float]
    words: tuple[TextWord, ...] = ()


def import_pdf_batch(
    files: Iterable[PdfInput],
    *,
    max_files: int = 50,
    max_bytes: int = 25_000_000,
    max_pages: int = 80,
    enable_ocr: bool = True,
    max_ocr_pages: int = 12,
    max_rendered_pixels: int = 24_000_000,
    max_ocr_seconds: float = 35.0,
) -> PdfImportBatchResult:
    """Import local PDF bytes and return reviewable slip candidates."""

    result = PdfImportBatchResult()
    seen_hashes: dict[str, str] = {}
    logical_seen: dict[
        tuple[str | None, int | None, str | None, tuple[tuple[str, str], ...]], str
    ] = {}
    batch_deadline = monotonic() + max_ocr_seconds
    ocr_pages_used = 0
    ocr_pixels_used = 0

    for index, item in enumerate(files):
        filename, pdf_bytes = (
            item if isinstance(item, tuple) else (f"document-{index + 1}.pdf", item)
        )
        digest = sha256(pdf_bytes).hexdigest()
        document_id = f"doc_{index + 1:03d}"

        if index >= max_files:
            result.documents.append(
                ImportedDocument(
                    document_id=document_id,
                    filename=filename,
                    sha256=digest,
                    status="too_many_files",
                    page_count=0,
                    message="PDF skipped because the batch exceeds the file limit.",
                )
            )
            continue

        if digest in seen_hashes:
            result.documents.append(
                ImportedDocument(
                    document_id=document_id,
                    filename=filename,
                    sha256=digest,
                    status="duplicate",
                    page_count=0,
                    message=f"Identical to {seen_hashes[digest]}.",
                )
            )
            result.candidates.append(
                ImportedSlipCandidate(
                    candidate_id=f"cand_{len(result.candidates) + 1:03d}",
                    document_id=document_id,
                    slip_type=None,
                    tax_year=None,
                    issuer_id=None,
                    decision="duplicate",
                    review_reasons=["exact_duplicate"],
                )
            )
            continue
        seen_hashes[digest] = document_id

        if len(pdf_bytes) > max_bytes:
            result.documents.append(
                ImportedDocument(
                    document_id=document_id,
                    filename=filename,
                    sha256=digest,
                    status="too_large",
                    page_count=0,
                    message="PDF exceeds the configured byte limit.",
                )
            )
            continue

        worker_result = run_import_one_pdf_worker(
            {
                "document_id": document_id,
                "filename": filename,
                "digest": digest,
                "pdf_bytes": pdf_bytes,
                "max_pages": max_pages,
                "enable_ocr": enable_ocr,
                "max_ocr_pages": max(0, max_ocr_pages - ocr_pages_used),
                "max_rendered_pixels": max(0, max_rendered_pixels - ocr_pixels_used),
                "max_ocr_seconds": max(0.0, batch_deadline - monotonic()),
            },
            timeout_seconds=max(0.0, batch_deadline - monotonic()),
            worker_module=_PDF_WORKER_MODULE,
        )
        ocr_pages_used += worker_result.ocr_pages_used
        ocr_pixels_used += worker_result.ocr_pixels_used
        document = worker_result.document
        candidates = worker_result.candidates
        result.documents.append(document)
        for candidate in candidates:
            candidate.candidate_id = f"cand_{len(result.candidates) + 1:03d}"
            _reconcile_candidate(candidate, result.candidates, logical_seen)
            result.candidates.append(candidate)

    return result


def _reconcile_candidate(
    candidate: ImportedSlipCandidate,
    existing: list[ImportedSlipCandidate],
    logical_seen: dict[
        tuple[str | None, int | None, str | None, tuple[tuple[str, str], ...]], str
    ],
) -> None:
    has_identity = (
        candidate.slip_type is not None
        and candidate.tax_year is not None
        and candidate.issuer_id
    )
    if not has_identity:
        return

    logical_key = (
        candidate.slip_type,
        candidate.tax_year,
        candidate.issuer_id,
        tuple(sorted((box, field.value) for box, field in candidate.fields.items())),
    )
    if logical_key in logical_seen:
        candidate.decision = "duplicate"
        candidate.review_reasons.append(f"logical_duplicate_of:{logical_seen[logical_key]}")
        return

    logical_seen[logical_key] = candidate.candidate_id
    for prior in existing:
        prior_fields = {box: field.value for box, field in prior.fields.items()}
        candidate_fields = {box: field.value for box, field in candidate.fields.items()}
        overlapping_boxes = prior_fields.keys() & candidate_fields.keys()
        if (
            prior.document_id != candidate.document_id
            and prior.slip_type == candidate.slip_type
            and prior.tax_year == candidate.tax_year
            and prior.issuer_id == candidate.issuer_id
            and any(prior_fields[box] != candidate_fields[box] for box in overlapping_boxes)
        ):
            candidate.decision = "needs_review"
            candidate.review_reasons.append("conflicting_values_for_same_slip")
            prior.decision = "needs_review"
            if "conflicting_values_for_same_slip" not in prior.review_reasons:
                prior.review_reasons.append("conflicting_values_for_same_slip")


def _import_one_pdf(
    document_id: str,
    filename: str,
    digest: str,
    pdf_bytes: bytes,
    *,
    max_pages: int,
    enable_ocr: bool,
    ocr_session: OcrSession,
) -> tuple[ImportedDocument, list[ImportedSlipCandidate]]:
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except Exception:
        return (
            _document(document_id, filename, digest, "malformed", 0, "PDF could not be parsed."),
            [],
        )

    if reader.is_encrypted:
        try:
            readable = bool(reader.decrypt(""))
        except Exception:
            readable = False
        if not readable:
            return (
                _document(document_id, filename, digest, "encrypted", 0, "Password-protected PDF."),
                [],
            )

    page_count = len(reader.pages)
    if page_count > max_pages:
        return (
            _document(
                document_id,
                filename,
                digest,
                "too_many_pages",
                page_count,
                "PDF exceeds the page limit.",
            ),
            [],
        )

    form_fields = _read_form_fields(reader)
    pages: list[PageText] = []
    ocr_attempted = False
    try:
        doc = pypdfium2.PdfDocument(pdf_bytes)
        for page_index in range(len(doc)):
            page = doc[page_index]
            textpage = page.get_textpage()
            raw_text = textpage.get_text_range()
            page_text = _digital_page_text(page_index + 1, textpage, raw_text)
            if page_text.text.strip():
                if (
                    enable_ocr
                    and not form_fields
                    and not _is_blank_digital_template(page_text.text)
                    and _needs_ocr_overlay(page_text.text)
                ):
                    ocr_attempted = True
                    ocr_pages = _ocr_pdfium_pages(doc, [page_index], scale=2.0, session=ocr_session)
                    if ocr_pages:
                        page_text = _merge_page_text(page_text, ocr_pages[0])
                pages.append(page_text)
            elif enable_ocr:
                ocr_attempted = True
                pages.extend(_ocr_pdfium_pages(doc, [page_index], scale=1.5, session=ocr_session))
    except Exception:
        return (
            _document(
                document_id,
                filename,
                digest,
                "malformed",
                page_count,
                "PDF text extraction failed.",
            ),
            [],
        )

    form_pages = _official_form_pages(form_fields, pages)
    if not form_pages:
        official_form = any(
            _detect_slip_type(page.text) in {"T4", "T2202", "RL-1", "RL-8"}
            for page in pages
        )
        generic_fields = [
            f"{field.name} {field.value}"
            for field in form_fields
            if field.value and not official_form
        ]
        if generic_fields:
            form_pages = [_plain_page_text(1, "\n".join(generic_fields), "acroform", 0.98)]
    if form_pages:
        pages = form_pages

    candidates = [
        candidate
        for group in _candidate_page_groups(pages)
        if (candidate := _candidate_from_pages("cand_pending", document_id, group)) is not None
    ]
    if ocr_session.exhausted and ocr_attempted:
        return (
            _document(
                document_id,
                filename,
                digest,
                "resource_limited",
                page_count,
                "OCR work limit reached; extracted candidates may be incomplete.",
            ),
            candidates,
        )
    if not candidates:
        return (
            _document(
                document_id,
                filename,
                digest,
                "unsupported",
                page_count,
                "No supported tax slip found.",
            ),
            [],
        )
    return _document(document_id, filename, digest, "processed", page_count, None), candidates


def _candidate_from_pages(
    candidate_id: str, document_id: str, pages: list[PageText]
) -> ImportedSlipCandidate | None:
    text = "\n".join(page.text for page in pages)
    slip_type = _detect_slip_type(text)
    if not slip_type:
        return None

    contribution_period = (
        _detect_rrsp_contribution_period(text) if slip_type == "RRSP_RECEIPT" else None
    )
    year = _detect_tax_year(text, slip_type=slip_type, contribution_period=contribution_period)
    if year is None:
        year = next((value for page in pages if (value := _spatial_year(page))), None)
    issuer = _detect_issuer(text) or next(
        (value for page in pages if (value := _spatial_issuer(page, slip_type))), None
    )
    status = _detect_amended_status(text)
    review_reasons: list[str] = []
    if year is None:
        review_reasons.append("missing_tax_year")
    elif year not in SUPPORTED_YEARS:
        review_reasons.append("unsupported_tax_year")
    if not issuer:
        review_reasons.append("missing_issuer")

    fields: dict[str, ExtractedField] = {}
    metadata: dict[str, ExtractedField] = {}
    for page in pages:
        for box, field in _spatial_amount_fields(page, slip_type).items():
            if box in fields and fields[box].value != field.value:
                fields[box].review_required = True
                field.review_required = True
                review_reasons.append(f"conflicting_box:{box}")
                continue
            fields.setdefault(box, field)
        for line in _clean_lines(page.text):
            for key, field in _metadata_fields_for_line(line, page, slip_type).items():
                metadata.setdefault(key, field)
            for box, field in _count_fields_for_line(line, page, slip_type).items():
                if box in fields and fields[box].value != field.value:
                    fields[box].review_required = True
                    field.review_required = True
                    review_reasons.append(f"conflicting_box:{box}")
                    continue
                fields.setdefault(box, field)
            box_hits = _box_hits(line, slip_type)
            for index, hit in enumerate(box_hits):
                box = hit.box
                if _looks_sensitive(line):
                    continue
                value_match = _amount_for_box_line(
                    line, hit, box_hits[index + 1] if index + 1 < len(box_hits) else None
                )
                if not value_match:
                    continue
                value = _normalize_money(value_match.group(1))
                if value is None:
                    continue
                supported = box in SUPPORTED_BOXES.get(slip_type, set())
                raw = _focused_snippet(line, hit.start, len(line))
                method = page.line_methods.get(line, page.method)
                confidence = page.line_confidences.get(line, page.confidence)
                defer_unsupported_review = not supported and method == "acroform"
                field = ExtractedField(
                    value=value,
                    method=method,  # type: ignore[arg-type]
                    confidence=confidence,
                    review_required=confidence < 0.9 or (not supported and not defer_unsupported_review),
                    page=page.page,
                    bbox=page.line_bboxes.get(line),
                    raw_text=raw,
                )
                if not supported and not defer_unsupported_review:
                    review_reasons.append(f"unsupported_box:{box}")
                if box in fields and fields[box].value != value:
                    fields[box].review_required = True
                    field.review_required = True
                    review_reasons.append(f"conflicting_box:{box}")
                    continue
                fields.setdefault(box, field)
            if slip_type == "RRSP_RECEIPT" and "contribution" in line.lower():
                amount = MONEY_RE.search(line)
                if amount and not _looks_sensitive(line):
                    value = _normalize_money(amount.group(1))
                    if value is not None:
                        method = page.line_methods.get(line, page.method)
                        confidence = page.line_confidences.get(line, page.confidence)
                        period_raw = (
                            contribution_period or _detect_rrsp_contribution_period(text) or ""
                        )
                        raw_text = _focused_snippet(line, amount.start(), amount.end())
                        if period_raw and period_raw.lower() not in raw_text.lower():
                            raw_text = f"{period_raw.replace('_', ' ')} {period_raw} {raw_text}"
                        fields["contribution_amount"] = ExtractedField(
                            value=value,
                            method=method,  # type: ignore[arg-type]
                            confidence=confidence,
                            review_required=confidence < 0.9,
                            page=page.page,
                            bbox=page.line_bboxes.get(line),
                            raw_text=raw_text,
                        )

    if not fields:
        review_reasons.append("missing_supported_amounts")
    for required_box in sorted(REQUIRED_AUTO_BOXES.get(slip_type, set()) - fields.keys()):
        review_reasons.append(f"missing_required_box:{required_box}")
    decision = "accepted_auto" if not review_reasons and fields else "needs_review"
    return ImportedSlipCandidate(
        candidate_id=candidate_id,
        document_id=document_id,
        slip_type=slip_type,
        tax_year=year,
        issuer_id=issuer,
        contribution_period=contribution_period,
        amended_status=status,
        decision=decision,
        fields=fields,
        metadata=metadata,
        review_reasons=sorted(set(review_reasons)),
    )


def _document(
    document_id: str,
    filename: str,
    digest: str,
    status: str,
    page_count: int,
    message: str | None,
) -> ImportedDocument:
    return ImportedDocument(
        document_id=document_id,
        filename=filename,
        sha256=digest,
        status=status,  # type: ignore[arg-type]
        page_count=page_count,
        message=message,
    )


def _read_form_fields(reader: PdfReader) -> list[FormField]:
    """Read widgets directly; some official RQ forms have malformed appearance dictionaries."""

    fields: list[FormField] = []
    for page_number, page in enumerate(reader.pages, 1):
        for reference in page.get("/Annots", ()):
            try:
                widget = reference.get_object()
                parent_ref = widget.get("/Parent")
                parent = parent_ref.get_object() if parent_ref else None
                name = widget.get("/T") or (parent.get("/T") if parent else None)
                field_type = widget.get("/FT") or (parent.get("/FT") if parent else None)
                value = widget.get("/V") if "/V" in widget else None
                if value is None and parent is not None:
                    value = parent.get("/V")
                alternate = widget.get("/TU") or (parent.get("/TU") if parent else None)
                rect = widget.get("/Rect")
                bbox = tuple(float(item) for item in rect) if rect and len(rect) == 4 else None
            except Exception:
                continue
            if name and str(field_type) in {"/Tx", "/Ch", "/Btn"}:
                text = "" if value is None else str(value)
                fields.append(
                    FormField(
                        name=str(name),
                        value=text.strip(),
                        page=page_number,
                        bbox=bbox,  # type: ignore[arg-type]
                        alternate_name=str(alternate) if alternate else None,
                    )
                )
    return fields


def _official_form_pages(fields: list[FormField], source_pages: list[PageText]) -> list[PageText]:
    groups: dict[tuple[int, str], list[tuple[str, tuple[float, float, float, float] | None]]] = {}
    for field in fields:
        source_text = source_pages[field.page - 1].text if field.page <= len(source_pages) else ""
        slip_type = _detect_slip_type(source_text)
        if not slip_type:
            continue
        canonical = _canonical_form_field(slip_type, field, source_text)
        if canonical is None:
            continue
        copy_key = ".2" if field.name.endswith(".2") else ""
        if slip_type in {"T4", "T2202"} and field.bbox:
            page_height = max(
                (word.bbox[3] for word in source_pages[field.page - 1].words),
                default=792.0,
            )
            copy_key = "upper" if _box_center_y(field.bbox) >= page_height / 2 else "lower"
        if slip_type.startswith("RL-"):
            copy_key = str(field.page)
        groups.setdefault((field.page, copy_key), []).append((canonical, field.bbox))

    pages: list[PageText] = []
    for (page_number, _), rows in groups.items():
        source_text = source_pages[page_number - 1].text if page_number <= len(source_pages) else ""
        slip_type = _detect_slip_type(source_text)
        if not slip_type:
            continue
        year = _detect_tax_year(source_text, slip_type=slip_type)
        lines = [_form_title(slip_type)]
        if year is not None and not any(line.lower().startswith("tax year") for line, _ in rows):
            lines.append(f"Tax year {year}")
        lines.extend(line for line, _ in rows)
        bboxes = {line: bbox for line, bbox in rows if bbox is not None}
        text = "\n".join(lines)
        pages.append(
            PageText(
                page=page_number,
                text=text,
                method="acroform",
                confidence=0.99,
                line_bboxes=bboxes,
                line_methods={line: "acroform" for line in lines},
                line_confidences={line: 0.99 for line in lines},
            )
        )
    return pages


def _canonical_form_field(slip_type: str, field: FormField, source_text: str) -> str | None:
    name = field.name.lower()
    value = field.value.strip()
    if slip_type == "T4":
        t4_button_fields = {
            "slip1cpp": "cpp_qpp_exempt",
            "slip1ei": "ei_exempt",
            "slip1ppip": "ppip_exempt",
        }
        for prefix, key in t4_button_fields.items():
            if name.startswith(prefix):
                return f"Box 28 {key} {_button_bool(value)}"
        if "employersname" in name or name.startswith("employer name"):
            if not value:
                return None
            return f"Employer name {value}"
        if "year" in name:
            if not value:
                return None
            return f"Tax year {value}"
        if "box10" in name:
            if not value:
                return None
            return f"Box 10 Province of employment {value.upper()}"
        return _canonical_numbered_money_form_field(field)
    elif slip_type in {"T4A", "T4E"}:
        return _canonical_numbered_money_form_field(field)
    elif slip_type == "T2202":
        if "part1_name_address" in name:
            if not value:
                return None
            return f"Institution name {_first_value_line(value)}"
        if "slip1year" in name:
            if not value:
                return None
            return f"Tax year {value}"
        label = f"{field.name} {field.alternate_name or ''}"
        if value:
            if "box 24" in label.lower() or "totals_box21" in name:
                return f"Box 24 {value}"
            if "box 25" in label.lower() or "totals_box25" in name:
                return f"Box 25 {value}"
            match = re.search(r"totals_box(2[67])", name, re.I)
            if match:
                return f"Box {match.group(1)} {value}"
    elif slip_type == "RL-1":
        if name in {"nom2", "rep_payeur"}:
            if not value:
                return None
            return f"Nom de l'employeur {_first_value_line(value)}"
        match = re.search(r"(?:^|_)case([a-z](?:-?[a-z])?|211)$", name, re.I)
        if match and value:
            box = _canonical_rl1_box(match.group(1))
            amount = _normalize_money(value)
            if box and amount is not None:
                return f"Case {box} {amount}"
    elif slip_type == "RL-8":
        if name in {"nom2", "rep_etablissement"}:
            if not value:
                return None
            return f"Institution name {_first_value_line(value)}"
        if name in {"an", "rep_an"}:
            if not value:
                return None
            return f"Tax year {value}"
        match = re.search(r"(?:^|_)case([abc])(?:1)?$", name, re.I)
        if match and value and not (match.group(1).upper() == "A" and value == "0"):
            return f"Case {match.group(1).upper()} {value}"
    return None


def _canonical_numbered_money_form_field(field: FormField) -> str | None:
    match = re.search(
        r"(?:^|[^A-Za-z0-9]|Slip\d*)Box\s*(\d{1,3}[A-Za-z]?)(?=$|[^A-Za-z0-9])",
        field.name,
        re.I,
    )
    amount = _normalize_money(field.value)
    if not match or amount is None:
        return None
    return f"Box {match.group(1).upper()} {amount}"


def _canonical_rl1_box(raw_box: str) -> str | None:
    box = raw_box.upper().replace("-", ".")
    aliases = {"BA": "B.A", "BB": "B.B"}
    box = aliases.get(box, box)
    if re.fullmatch(r"[A-Z](?:\.[A-Z])?|211", box):
        return box
    return None


def _first_value_line(value: str) -> str:
    return next((line.strip() for line in value.splitlines() if line.strip()), value.strip())


def _button_bool(value: str) -> str:
    return "false" if value in {"", "Off", "/Off"} else "true"


def _form_title(slip_type: str) -> str:
    return {
        "T4": "T4 Statement of Remuneration Paid",
        "T4A": "T4A Statement of Pension Retirement Annuity and Other Income",
        "T4E": "T4E Statement of Employment Insurance and Other Benefits",
        "T5": "T5 Statement of Investment Income",
        "T2202": "T2202 Tuition and Enrolment Certificate",
        "RL-1": "RL-1 Releve 1 Revenus emploi",
        "RL-8": "RL-8 Releve 8 Montant pour etudes postsecondaires",
    }.get(slip_type, slip_type)


def _metadata_fields_for_line(line: str, page: PageText, slip_type: str) -> dict[str, ExtractedField]:
    if slip_type != "T4":
        return {}
    method = page.line_methods.get(line, page.method)
    confidence = page.line_confidences.get(line, page.confidence)
    bbox = page.line_bboxes.get(line)
    metadata: dict[str, ExtractedField] = {}
    province = re.search(r"\bbox\s+10\b.*?\b([A-Z]{2})\b\s*$", line, re.I)
    if province:
        metadata["province_of_employment"] = ExtractedField(
            value=province.group(1).upper(),
            method=method,  # type: ignore[arg-type]
            confidence=confidence,
            review_required=confidence < 0.9,
            page=page.page,
            bbox=bbox,
            raw_text=_focused_snippet(line, province.start(1), province.end(1)),
        )
    exemption = re.search(r"\bbox\s+28\s+(cpp_qpp_exempt|ei_exempt|ppip_exempt)\s+(true|false)\b", line, re.I)
    if exemption:
        value = exemption.group(2).lower() == "true"
        metadata[exemption.group(1).lower()] = ExtractedField(
            value=value,
            method=method,  # type: ignore[arg-type]
            confidence=confidence,
            review_required=confidence < 0.9,
            page=page.page,
            bbox=bbox,
            raw_text=_focused_snippet(line, exemption.start(1), exemption.end(2)),
            value_state="present" if value else "off",
        )
    return metadata


def _count_fields_for_line(line: str, page: PageText, slip_type: str) -> dict[str, ExtractedField]:
    if slip_type != "T2202":
        return {}
    match = re.search(r"\bbox\s+(24|25)\b.*?\b(\d{1,2})\b\s*$", line, re.I)
    if not match:
        return {}
    method = page.line_methods.get(line, page.method)
    confidence = page.line_confidences.get(line, page.confidence)
    return {
        match.group(1): ExtractedField(
            value=match.group(2),
            method=method,  # type: ignore[arg-type]
            confidence=confidence,
            review_required=confidence < 0.9,
            page=page.page,
            bbox=page.line_bboxes.get(line),
            raw_text=_focused_snippet(line, match.start(1), match.end(2)),
        )
    }


def _plain_page_text(page: int, text: str, method: str, confidence: float) -> PageText:
    line_bboxes: dict[str, tuple[float, float, float, float]] = {}
    line_methods: dict[str, str] = {}
    line_confidences: dict[str, float] = {}
    for line in _clean_lines(text):
        line_methods[line] = method
        line_confidences[line] = confidence
    return PageText(
        page=page,
        text=text,
        method=method,
        confidence=confidence,
        line_bboxes=line_bboxes,
        line_methods=line_methods,
        line_confidences=line_confidences,
    )


def _digital_page_text(page: int, textpage: object, raw_text: str) -> PageText:
    words = _text_words(textpage)
    if words:
        text, line_bboxes = _text_from_words(words)
    else:
        text = raw_text.replace("\r", "\n")
        line_bboxes = _line_bboxes(textpage, raw_text)
    line_methods = {line: "digital_text" for line in _clean_lines(text)}
    line_confidences = {line: 0.96 for line in _clean_lines(text)}
    return PageText(
        page=page,
        text=text,
        method="digital_text",
        confidence=0.96,
        line_bboxes=line_bboxes,
        line_methods=line_methods,
        line_confidences=line_confidences,
        words=tuple(words),
    )


def _merge_page_text(digital: PageText, ocr: PageText) -> PageText:
    text = "\n".join(part for part in (digital.text, ocr.text) if part.strip())
    return PageText(
        page=digital.page,
        text=text,
        method=digital.method,
        confidence=min(digital.confidence, ocr.confidence),
        line_bboxes={**digital.line_bboxes, **ocr.line_bboxes},
        line_methods={**digital.line_methods, **ocr.line_methods},
        line_confidences={**digital.line_confidences, **ocr.line_confidences},
        words=(*digital.words, *ocr.words),
    )


def _needs_ocr_overlay(text: str) -> bool:
    if not _looks_like_slip_page(text):
        return False
    return (
        _detect_issuer(text) is None
        or _detect_tax_year(text) is None
        or not _text_has_amount_field(text)
    )


def _is_blank_digital_template(text: str) -> bool:
    return len(text) > 500 and _looks_like_slip_page(text) and not MONEY_RE.search(text)


def _text_has_amount_field(text: str) -> bool:
    for line in _clean_lines(text):
        if BOX_RE.search(line) and MONEY_RE.search(line) and not _looks_sensitive(line):
            return True
        if "contribution" in line.lower() and MONEY_RE.search(line) and not _looks_sensitive(line):
            return True
    return False


def _candidate_page_groups(pages: list[PageText]) -> list[list[PageText]]:
    groups: list[list[PageText]] = []
    last_group: list[PageText] | None = None
    for page in pages:
        for region in _split_page_regions(page):
            if _looks_like_slip_page(region.text):
                group = [region]
                groups.append(group)
                last_group = group
            elif last_group is not None and _is_continuation_page(region.text):
                last_group.append(region)
    return groups


def _split_page_regions(page: PageText) -> list[PageText]:
    anchors = _slip_anchors(page.words)
    if len(anchors) < 2:
        return [page]
    x_span = max(anchor[0] for anchor in anchors) - min(anchor[0] for anchor in anchors)
    y_span = max(anchor[1] for anchor in anchors) - min(anchor[1] for anchor in anchors)
    axis = 0 if x_span >= y_span else 1
    anchors = sorted(anchors, key=lambda anchor: anchor[axis])
    if axis == 0 or page.method == "ocr_rapidocr":
        cuts = [anchors[index + 1][axis] - 20 for index in range(len(anchors) - 1)]
    else:
        cuts = [anchors[index][axis] + 40 for index in range(len(anchors) - 1)]
    bounds = [(-float("inf"), cuts[0])]
    bounds.extend((cuts[index - 1], cuts[index]) for index in range(1, len(cuts)))
    bounds.append((cuts[-1], float("inf")))

    regions: list[PageText] = []
    for left, right in bounds:
        words = []
        for word in page.words:
            center = (
                (word.bbox[0] + word.bbox[2]) / 2
                if axis == 0
                else (word.bbox[1] + word.bbox[3]) / 2
            )
            if left <= center < right:
                words.append(word)
        if not words:
            continue
        text, line_bboxes = _text_from_words(words)
        lines = _clean_lines(text)
        regions.append(
            PageText(
                page=page.page,
                text=text,
                method=page.method,
                confidence=page.confidence,
                line_bboxes=line_bboxes,
                line_methods={line: page.line_methods.get(line, page.method) for line in lines},
                line_confidences={
                    line: page.line_confidences.get(line, page.confidence) for line in lines
                },
                words=tuple(words),
            )
        )
    return regions or [page]


def _slip_anchors(words: tuple[TextWord, ...]) -> list[tuple[float, float, str]]:
    anchors: list[tuple[float, float, str]] = []
    rows = _word_rows(words)
    for row in rows:
        texts = [word.text.upper().strip(":-") for word in row]
        row_text = " ".join(texts)
        for index, text in enumerate(texts):
            if (
                text in {"T4", "T4A", "T4E", "T5", "T2202", "RC210"}
                and "BOX" not in row_text
                and (_title_row(text, row_text) or _near_slip_title(row[index], words, text))
            ):
                anchors.append(
                    (_box_center_x(row[index].bbox), _box_center_y(row[index].bbox), text)
                )
            elif text in {"RRSP", "REER"} and "CONTRIBUTION" in row_text:
                anchors.append(
                    (
                        _box_center_x(row[index].bbox),
                        _box_center_y(row[index].bbox),
                        "RRSP_RECEIPT",
                    )
                )
    deduped: list[tuple[float, float, str]] = []
    for x, y, slip_type in anchors:
        if not any(abs(old_x - x) <= 40 and abs(old_y - y) <= 25 for old_x, old_y, _ in deduped):
            deduped.append((x, y, slip_type))
    return deduped


def _title_row(slip_type: str, row_text: str) -> bool:
    if slip_type == "T4":
        return "STATEMENT" in row_text or "REMUNERATION" in row_text
    return True


def _near_slip_title(
    anchor: TextWord, words: tuple[TextWord, ...], slip_type: str
) -> bool:
    title_token = "REMUNERATION" if slip_type == "T4" else "STATEMENT"
    for word in words:
        if title_token not in word.text.upper():
            continue
        if (
            abs(_box_center_y(anchor.bbox) - _box_center_y(word.bbox)) <= 80
            and abs(_box_center_x(anchor.bbox) - _box_center_x(word.bbox)) <= 300
        ):
            return True
    return False


def _text_words(textpage: object) -> list[TextWord]:
    words: list[TextWord] = []
    current = ""
    current_box: tuple[float, float, float, float] | None = None
    last_box: tuple[float, float, float, float] | None = None
    for index in range(textpage.count_chars()):
        char = textpage.get_text_range(index, 1)
        if not char or char.isspace():
            if current and current_box:
                words.append(TextWord(current, current_box))
            current = ""
            current_box = None
            last_box = None
            continue
        try:
            char_box = textpage.get_charbox(index)
        except Exception:
            continue
        same_word = (
            current_box is not None
            and last_box is not None
            and abs(_box_center_y(char_box) - _box_center_y(last_box)) <= 3
            and char_box[0] - last_box[2] <= 4
        )
        if not same_word and current and current_box:
            words.append(TextWord(current, current_box))
            current = ""
            current_box = None
        current += char
        current_box = _merge_bbox(current_box, char_box)
        last_box = char_box
    if current and current_box:
        words.append(TextWord(current, current_box))
    return words


def _text_from_words(
    words: list[TextWord] | tuple[TextWord, ...],
) -> tuple[str, dict[str, tuple[float, float, float, float]]]:
    lines: list[str] = []
    line_bboxes: dict[str, tuple[float, float, float, float]] = {}
    for row in _word_rows(words):
        line = _join_layout_tokens(" ".join(word.text for word in row).strip())
        if not line:
            continue
        bbox: tuple[float, float, float, float] | None = None
        for word in row:
            bbox = _merge_bbox(bbox, word.bbox)
        lines.append(line)
        if bbox:
            line_bboxes[line] = bbox
    return "\n".join(lines), line_bboxes


def _join_layout_tokens(line: str) -> str:
    line = re.sub(r"(?<=\d)\s+([,.])\s+(?=\d)", r"\1", line)
    line = re.sub(r"\b([A-Z])\s+\.\s+([A-Z])\b", r"\1.\2", line)
    line = re.sub(r"\b(RL)\s*-\s*(\d+)\b", r"\1-\2", line, flags=re.I)
    line = re.sub(r"'\s+", "'", line)
    return line


def _word_rows(words: list[TextWord] | tuple[TextWord, ...]) -> list[list[TextWord]]:
    rows: list[list[TextWord]] = []
    for word in sorted(words, key=lambda item: (-_box_center_y(item.bbox), item.bbox[0])):
        for row in rows:
            if abs(_box_center_y(row[0].bbox) - _box_center_y(word.bbox)) <= 5:
                row.append(word)
                break
        else:
            rows.append([word])
    for row in rows:
        row.sort(key=lambda item: item.bbox[0])
    return rows


def _merge_bbox(
    left: tuple[float, float, float, float] | None,
    right: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    if left is None:
        return right
    return (
        min(left[0], right[0]),
        min(left[1], right[1]),
        max(left[2], right[2]),
        max(left[3], right[3]),
    )


def _box_center_y(bbox: tuple[float, float, float, float]) -> float:
    return (bbox[1] + bbox[3]) / 2


def _box_center_x(bbox: tuple[float, float, float, float]) -> float:
    return (bbox[0] + bbox[2]) / 2


def _line_bboxes(textpage: object, raw_text: str) -> dict[str, tuple[float, float, float, float]]:
    bboxes: dict[str, tuple[float, float, float, float]] = {}
    for match in re.finditer(r"[^\r\n]+", raw_text):
        line = match.group(0).strip()
        if not line:
            continue
        try:
            rects = [
                textpage.get_rect(index)
                for index in range(textpage.count_rects(match.start(), len(match.group(0))))
            ]
        except Exception:
            continue
        if rects:
            bboxes[line] = (
                min(rect[0] for rect in rects),
                min(rect[1] for rect in rects),
                max(rect[2] for rect in rects),
                max(rect[3] for rect in rects),
            )
    return bboxes


def _ocr_pdfium_pages(
    doc: pypdfium2.PdfDocument,
    page_indexes: list[int],
    *,
    scale: float,
    session: OcrSession,
) -> list[PageText]:
    try:
        pages: list[PageText] = []
        for page_index in page_indexes:
            page = doc[page_index]
            width = int(page.get_width() * scale + 0.5)
            height = int(page.get_height() * scale + 0.5)
            if not session.admit(width, height):
                continue
            bitmap = page.render(scale=scale).to_pil()
            recognized = session.recognize(bitmap)
            if recognized is None:
                continue
            lines, confidences, result_boxes = recognized
            bboxes: dict[str, tuple[float, float, float, float]] = {}
            words: list[TextWord] = []
            for index, (text, box) in enumerate(zip(lines, result_boxes, strict=False)):
                xs = [float(point[0]) for point in box]
                ys = [float(point[1]) for point in box]
                bbox = (min(xs), min(ys), max(xs), max(ys))
                clean_text = text.strip()
                bboxes[clean_text] = bbox
                score = confidences[index] if index < len(confidences) else 0.5
                words.append(TextWord(clean_text, bbox, score))
            confidence = min(confidences) if confidences else 0.5
            if lines:
                text = "\n".join(lines)
                pages.append(
                    PageText(
                        page_index + 1,
                        text,
                        "ocr_rapidocr",
                        confidence,
                        bboxes,
                        {line: "ocr_rapidocr" for line in _clean_lines(text)},
                        {line: confidence for line in _clean_lines(text)},
                        tuple(words),
                    )
                )
        return pages
    except Exception:
        return []


def _detect_slip_type(text: str) -> str | None:
    normalized = text.upper().replace("RELEVE", "RELEVE").replace("RELEVÉ", "RELEVE")
    if "T2202" in normalized:
        return "T2202"
    if "RC210" in normalized:
        return "RC210"
    if "T4A" in normalized:
        return "T4A"
    if "T4E" in normalized:
        return "T4E"
    if "T4" in normalized:
        return "T4"
    if "T5" in normalized:
        return "T5"
    if "RL-19" in normalized or "RL19" in normalized or "RELEVE 19" in normalized:
        return "RL-19"
    if "RL-8" in normalized or "RL8" in normalized or "RELEVE 8" in normalized:
        return "RL-8"
    if "RL-3" in normalized or "RL3" in normalized or "RELEVE 3" in normalized:
        return "RL-3"
    if "RL-1" in normalized or "RL1" in normalized or "RELEVE 1" in normalized:
        return "RL-1"
    if "RRSP" in normalized or "REER" in normalized:
        return "RRSP_RECEIPT"
    return None


def _looks_like_slip_page(text: str) -> bool:
    slip_type = _detect_slip_type(text)
    if not slip_type:
        return False
    normalized = text.upper().replace("É", "E")
    titles = {
        "T4": ("STATEMENT OF REMUNERATION PAID", "ETAT DE LA REMUNERATION PAYEE"),
        "T4A": ("STATEMENT OF PENSION", "PENSION RETIREMENT ANNUITY"),
        "T4E": ("STATEMENT OF EMPLOYMENT INSURANCE",),
        "T5": ("STATEMENT OF INVESTMENT INCOME",),
        "T2202": ("TUITION AND ENROLMENT CERTIFICATE", "CERTIFICAT POUR FRAIS DE SCOLARITE"),
        "RL-1": ("RL-1 RELEVE", "RELEVE 1", "RL-1 ("),
        "RL-3": ("RL-3 RELEVE", "RELEVE 3", "RL-3 ("),
        "RL-8": ("RL-8 RELEVE", "RELEVE 8", "RL-8 ("),
        "RL-19": ("RL-19 RELEVE", "RELEVE 19", "RL-19 ("),
        "RC210": ("RC210",),
        "RRSP_RECEIPT": ("RRSP CONTRIBUTION RECEIPT", "RECU DE COTISATION REER"),
    }
    return any(title in normalized for title in titles.get(slip_type, (slip_type,)))


def _spatial_amount_fields(page: PageText, slip_type: str) -> dict[str, ExtractedField]:
    supported = SUPPORTED_BOXES.get(slip_type, set())
    anchors: list[tuple[str, TextWord]] = []
    amounts: list[TextWord] = []
    for word in page.words:
        if MONEY_RE.fullmatch(word.text.strip()) and not _looks_sensitive(word.text):
            amounts.append(word)
        box = _spatial_box_code(word.text, slip_type)
        if box in supported:
            anchors.append((box, word))

    fields: dict[str, ExtractedField] = {}
    for amount in amounts:
        matches: list[tuple[float, str, TextWord]] = []
        for box, anchor in anchors:
            horizontal_gap = max(
                0.0, amount.bbox[0] - anchor.bbox[2], anchor.bbox[0] - amount.bbox[2]
            )
            vertical_gap = max(
                0.0, amount.bbox[1] - anchor.bbox[3], anchor.bbox[1] - amount.bbox[3]
            )
            same_row = abs(_box_center_y(amount.bbox) - _box_center_y(anchor.bbox)) <= 45
            same_column = horizontal_gap == 0 and vertical_gap <= 45
            if horizontal_gap <= 180 and vertical_gap <= 55 and (same_row or same_column):
                distance = horizontal_gap + vertical_gap + 0.05 * abs(
                    _box_center_x(amount.bbox) - _box_center_x(anchor.bbox)
                )
                matches.append((distance, box, anchor))
        if not matches:
            continue
        _, box, anchor = min(matches, key=lambda item: item[0])
        value = _normalize_money(amount.text)
        if value is None:
            continue
        confidence = min(amount.confidence, anchor.confidence)
        field = ExtractedField(
            value=value,
            method=page.method,  # type: ignore[arg-type]
            confidence=confidence,
            review_required=confidence < 0.9,
            page=page.page,
            bbox=amount.bbox,
            raw_text=f"{anchor.text} {amount.text}",
        )
        if box not in fields or field.confidence > fields[box].confidence:
            fields[box] = field
    return fields


def _spatial_box_code(text: str, slip_type: str) -> str | None:
    supported = SUPPORTED_BOXES.get(slip_type, set())
    exact = text.strip().upper()
    if exact in supported:
        return exact
    labelled = re.match(
        r"\s*(?:BOX|CASE)?\s*([A-Z](?:\.[A-Z])?|\d{1,3}[A-Z]?)\s*[-–:]",
        text,
        re.I,
    )
    if labelled:
        box = labelled.group(1).upper()
        return box if box in supported else None
    return None


def _spatial_issuer(page: PageText, slip_type: str) -> str | None:
    labels = [
        word
        for word in page.words
        if re.search(
            r"employer(?:'s)? name|nom et adresse de l['’]employeur|"
            r"institution name|nom et adresse de l['’]etablissement",
            word.text,
            re.I,
        )
    ]
    candidates: list[tuple[float, str]] = []
    for label in labels:
        for word in page.words:
            if word is label or not _plausible_issuer(word.text):
                continue
            horizontal_gap = max(0.0, word.bbox[0] - label.bbox[2], label.bbox[0] - word.bbox[2])
            vertical_gap = max(0.0, word.bbox[1] - label.bbox[3], label.bbox[1] - word.bbox[3])
            if horizontal_gap <= 25 and vertical_gap <= 55:
                distance = vertical_gap + 0.1 * horizontal_gap
                candidates.append((distance, word.text.strip()))
    return min(candidates, default=(0.0, None), key=lambda item: item[0])[1]


def _spatial_year(page: PageText) -> int | None:
    labels = [
        word for word in page.words if word.text.strip().lower() in {"year", "année", "annee"}
    ]
    years = [word for word in page.words if re.fullmatch(r"20\d{2}", word.text.strip())]
    matches: list[tuple[float, int]] = []
    for label in labels:
        for year in years:
            horizontal_gap = max(0.0, year.bbox[0] - label.bbox[2], label.bbox[0] - year.bbox[2])
            vertical_gap = max(0.0, year.bbox[1] - label.bbox[3], label.bbox[1] - year.bbox[3])
            if horizontal_gap <= 90 and vertical_gap <= 35:
                matches.append((horizontal_gap + vertical_gap, int(year.text)))
    return min(matches, default=(0.0, None), key=lambda item: item[0])[1]


def _amount_for_box_line(
    line: str,
    hit: BoxHit,
    next_hit: BoxHit | None,
) -> re.Match[str] | None:
    end = next_hit.start if next_hit else len(line)
    forward = line[hit.end : end]
    value = END_MONEY_RE.search(forward)
    if value:
        return value
    preceding = line[: hit.start]
    amounts = list(MONEY_RE.finditer(preceding))
    return amounts[-1] if amounts else None


def _box_hits(line: str, slip_type: str) -> list[BoxHit]:
    hits = [
        BoxHit(match.group(1).upper(), match.start(), match.end())
        for match in BOX_RE.finditer(line)
    ]
    if hits:
        return hits

    supported = SUPPORTED_BOXES.get(slip_type, set())
    if not supported or not MONEY_RE.search(line):
        return []
    for box in sorted(supported, key=len, reverse=True):
        pattern = rf"(?<![A-Z0-9.]){re.escape(box)}(?![A-Z0-9.])"
        matches = list(re.finditer(pattern, line, re.I))
        if len(matches) == 1:
            match = matches[0]
            return [BoxHit(box, match.start(), match.end())]
    return []


def _detect_tax_year(
    text: str,
    *,
    slip_type: str | None = None,
    contribution_period: str | None = None,
) -> int | None:
    if slip_type == "RRSP_RECEIPT":
        rrsp_year = _rrsp_reporting_year(contribution_period)
        if rrsp_year is not None:
            return rrsp_year
    label = re.search(
        r"(?:tax\s+(?:year|vear)|annee d'imposition|année d'imposition)\D{0,20}(20\d{2})",
        text,
        re.I,
    )
    if label:
        return int(label.group(1))
    if slip_type == "T4":
        revision = re.search(r"\bT4\s*\((2[0-5])\)", text, re.I)
        if revision:
            return 2000 + int(revision.group(1))
    if slip_type == "RL-1":
        revision = re.search(r"RL-1\s*\((20\d{2})-\d{2}\)", text, re.I)
        if revision:
            return int(revision.group(1))
    return None


def _detect_rrsp_contribution_period(text: str) -> str | None:
    for line in _clean_lines(text):
        normalized = line.lower()
        if "contribution" not in normalized and "cotisation" not in normalized:
            continue
        year_match = YEAR_RE.search(line)
        if not year_match:
            continue
        year = int(year_match.group(1))
        if re.search(r"\bfirst\s+60\b", normalized):
            return f"first_60_days_{year}"
        if re.search(r"\b(?:jan(?:uary)?|janvier)\b", normalized) and re.search(
            r"\b(?:mar(?:ch)?|mars)\b", normalized
        ):
            return f"first_60_days_{year}"
        if re.search(r"\b(?:mar(?:ch)?|mars)\b", normalized) and re.search(
            r"\b(?:dec(?:ember)?|decembre|décembre)\b", normalized
        ):
            return f"march_to_december_{year}"
    return None


def _rrsp_reporting_year(contribution_period: str | None) -> int | None:
    if not contribution_period:
        return None
    match = re.search(r"(20\d{2})$", contribution_period)
    if not match:
        return None
    year = int(match.group(1))
    if contribution_period.startswith("first_60_days_"):
        return year - 1
    return year


def _detect_issuer(text: str) -> str | None:
    patterns = (
        r"(?:Employer(?:'s)? name|Nom de l'employeur)\s+([^\r\n]+)",
        r"(?:Payer name|Nom du payeur)\s+([^\r\n]+)",
        r"(?:Issuer|Émetteur|Emetteur)\s+([^\r\n]+)",
        r"(?:Institution name|Nom de l'établissement)\s+([^\r\n]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            value = match.group(1).strip(" :-\r")
            if _plausible_issuer(value):
                return value[:120]
    return None


def _plausible_issuer(value: str) -> bool:
    normalized = value.strip(" :-\r")
    if len(normalized) < 3:
        return False
    return not bool(
        re.search(
            r"canada revenue|revenue agency|agence du revenu|revenu quebec|"
            r"formulaire prescrit|a conserver|à conserver|^agency$|^t\d|^rl-?\d|"
            r"employer(?:'s)? name|nom (?:et adresse )?de l['’]employeur|^year$|^annee$",
            normalized,
            re.I,
        )
    )


def _detect_amended_status(text: str) -> str:
    if re.search(r"\b(amended|modified|modifi[eé])\b", text, re.I):
        return "amended"
    if re.search(r"\b(original)\b", text, re.I):
        return "original"
    return "unknown"


def _is_continuation_page(text: str) -> bool:
    return bool(
        re.search(r"\b(continuation|suite|other information|autres renseignements)\b", text, re.I)
    )


def _clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _looks_sensitive(line: str) -> bool:
    return bool(SENSITIVE_LINE.search(line))


def _normalize_money(value: str) -> str | None:
    candidate = value.replace("$", "").replace(" ", "").strip()
    if "," in candidate and "." not in candidate:
        candidate = candidate.replace(",", ".")
    else:
        candidate = candidate.replace(",", "")
    try:
        amount = Decimal(candidate)
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return f"{amount.quantize(Decimal('0.01'))}"


def _focused_snippet(line: str, start: int, end: int) -> str:
    snippet = line[max(0, start - 40) : min(len(line), end + 20)]
    return SENSITIVE_LINE.sub("[redacted]", snippet)

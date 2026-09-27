from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "pdf" / "official"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from taxagent.intake import import_pdf_batch


def _digest(path: Path) -> str:
    h = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _check(path: Path, expected: dict[str, Any]) -> None:
    if not path.is_file():
        raise AssertionError(
            f"official fixture is missing: {path}\n"
            "This opt-in acceptance suite requires tester-provided government PDF originals. "
            "Place them under tests/fixtures/pdf/official/official or pass --source-corpus, "
            "then run scripts/release/provision_official_pdf_fixtures.py --offline."
        )
    size = path.stat().st_size
    digest = _digest(path)
    if size != expected["bytes"] or digest != expected["sha256"]:
        raise AssertionError(
            f"official fixture changed: {path} got {size} bytes {digest}, "
            f"expected {expected['bytes']} bytes {expected['sha256']}"
        )


def _filled_official_form(source: Path, values: dict[str, str]) -> bytes:
    from io import BytesIO

    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(source)
    if reader.is_encrypted:
        reader.decrypt("")
    writer = PdfWriter(clone_from=reader)
    writer.update_page_form_field_values(writer.pages[0], values, auto_regenerate=False)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _candidate(result, slip_type: str):
    return next(candidate for candidate in result.candidates if candidate.slip_type == slip_type)


def _assert_original_fillable_forms(official_dir: Path) -> None:
    t4 = _filled_official_form(
        official_dir / "cra-t4-fill-2025.pdf",
        {
            "Slip1EmployersName[0]": "EXAMPLE ROBOTICS INC.",
            "Slip1Year[0]": "2025",
            "Slip1Box14[0]": "48000.00",
            "Slip1Box22[0]": "5000.00",
        },
    )
    rl1 = _filled_official_form(
        official_dir / "rq-rl1-fill-2025.pdf",
        {"nom2": "EXAMPLE ROBOTICS INC.", "caseA": "48000.00", "caseE": "5000.00"},
    )
    t2202 = _filled_official_form(
        official_dir / "cra-t2202-fill-2025.pdf",
        {
            "Slip1Year[0]": "2025",
            "Part1_Name_Address[0]": "EXAMPLE COLLEGE",
            "Totals_Box26_row5[0]": "7000.00",
        },
    )
    rl8 = _filled_official_form(
        official_dir / "rq-rl8-fill-2022.pdf",
        {"an": "2025", "nom2": "EXAMPLE COLLEGE", "caseA": "3000.00", "caseB1": "7000.00"},
    )
    result = import_pdf_batch(
        [
            ("official-t4.pdf", t4),
            ("official-rl1.pdf", rl1),
            ("official-t2202.pdf", t2202),
            ("official-rl8.pdf", rl8),
        ],
        enable_ocr=False,
    )
    assert _candidate(result, "T4").issuer_id == "EXAMPLE ROBOTICS INC."
    assert _candidate(result, "T4").fields["14"].value == "48000.00"
    assert _candidate(result, "T4").fields["22"].value == "5000.00"
    assert _candidate(result, "RL-1").issuer_id == "EXAMPLE ROBOTICS INC."
    assert _candidate(result, "RL-1").fields["A"].value == "48000.00"
    assert _candidate(result, "RL-1").fields["E"].value == "5000.00"
    assert _candidate(result, "T2202").issuer_id == "EXAMPLE COLLEGE"
    assert _candidate(result, "T2202").fields["26"].value == "7000.00"
    assert _candidate(result, "RL-8").issuer_id == "EXAMPLE COLLEGE"
    assert _candidate(result, "RL-8").fields["A"].value == "3000.00"
    assert _candidate(result, "RL-8").fields["B"].value == "7000.00"


def run_acceptance(fixture_root: Path, source_corpus: Path | None) -> None:
    from scripts.release import provision_official_pdf_fixtures as provisioner

    manifest_path = fixture_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["official"]:
        source = fixture_root / "official" / item["name"]
        if not source.is_file() and source_corpus is not None:
            source = source_corpus / "official" / item["name"]
        _check(source, item)

    provisioner.provision(manifest_path, fixture_root, source_corpus, timeout=0.0, offline=True)
    _assert_original_fillable_forms(fixture_root / "official")
    release_dir = fixture_root / "generated" / "release"
    uploads = []
    for entry in manifest["annual_flow"]:
        uploads.append((release_dir / entry["t4"]).read_bytes())
        uploads.append((release_dir / entry["rl1"]).read_bytes())

    result = import_pdf_batch(
        [(f"official-release-{index}.pdf", payload) for index, payload in enumerate(uploads, 1)],
        enable_ocr=False,
    )
    years = {candidate.tax_year for candidate in result.candidates if candidate.decision == "accepted_auto"}
    if years != {2020, 2021, 2022, 2023, 2024, 2025}:
        raise AssertionError(f"official release acceptance did not import all years: {sorted(years)}")
    print("local official PDF acceptance passed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURE_ROOT)
    parser.add_argument("--source-corpus", type=Path, default=None)
    args = parser.parse_args(argv)
    run_acceptance(args.fixtures.resolve(), args.source_corpus.resolve() if args.source_corpus else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

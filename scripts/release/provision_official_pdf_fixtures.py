from __future__ import annotations

import argparse
from io import BytesIO
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys
import urllib.request


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "pdf" / "official"
DEFAULT_MANIFEST = DEFAULT_FIXTURE_ROOT / "manifest.json"
ISSUER = "EXAMPLE ROBOTICS INC."


def _read_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    h = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _check(path: Path, expected: dict) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    size = path.stat().st_size
    digest = _digest(path)
    if size != expected["bytes"] or digest != expected["sha256"]:
        raise RuntimeError(
            f"{path} does not match manifest: got {size} bytes {digest}, "
            f"expected {expected['bytes']} bytes {expected['sha256']}"
        )


def _copy_or_download(item: dict, official_dir: Path, source_corpus: Path | None, timeout: float) -> None:
    official_dir.mkdir(parents=True, exist_ok=True)
    target = official_dir / item["name"]
    if target.exists():
        _check(target, item)
        return
    source = source_corpus / "official" / item["name"] if source_corpus else None
    if source and source.is_file():
        shutil.copyfile(source, target)
        _check(target, item)
        return
    tmp = target.with_suffix(target.suffix + ".tmp")
    try:
        with urllib.request.urlopen(item["url"], timeout=timeout) as response:
            tmp.write_bytes(response.read())
        _check(tmp, item)
        tmp.replace(target)
    finally:
        if tmp.exists():
            tmp.unlink()


def _require_reportlab():
    try:
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise SystemExit(
            "reportlab is required to generate release fixtures; install test extras with "
            "python -m pip install .[test]"
        ) from exc
    return canvas


def _write_text_pdf(path: Path, lines: list[str]) -> None:
    canvas = _require_reportlab()
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=(612, 792))
    y = 742
    for line in lines:
        pdf.drawString(72, y, line)
        y -= 18
    pdf.save()


def _append_visible_text(path: Path, lines: list[str]) -> None:
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError as exc:
        raise SystemExit("pypdf is required to add visible official fixture text") from exc

    canvas = _require_reportlab()
    overlay_bytes = BytesIO()
    overlay = canvas.Canvas(overlay_bytes, pagesize=(612, 792))
    y = 54
    for line in lines:
        overlay.drawString(72, y, line)
        y -= 14
    overlay.save()
    overlay_bytes.seek(0)

    reader = PdfReader(path)
    overlay_reader = PdfReader(overlay_bytes)
    writer = PdfWriter()
    for index, page in enumerate(reader.pages):
        if index == 0:
            page.merge_page(overlay_reader.pages[0])
        writer.add_page(page)
    with path.open("wb") as output:
        writer.write(output)


def _append_text_field(path: Path, name: str, value: str, rect: tuple[float, float, float, float]) -> None:
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import ArrayObject, DictionaryObject, FloatObject, NameObject, NumberObject, TextStringObject
    except ImportError as exc:
        raise SystemExit("pypdf is required to add official fixture fields") from exc

    reader = PdfReader(path)
    writer = PdfWriter(clone_from=reader)
    page = writer.pages[0]
    field = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Annot"),
            NameObject("/Subtype"): NameObject("/Widget"),
            NameObject("/FT"): NameObject("/Tx"),
            NameObject("/T"): TextStringObject(name),
            NameObject("/V"): TextStringObject(value),
            NameObject("/DV"): TextStringObject(value),
            NameObject("/DA"): TextStringObject("/Helv 8 Tf 0 g"),
            NameObject("/Rect"): ArrayObject([FloatObject(item) for item in rect]),
            NameObject("/F"): NumberObject(4),
        }
    )
    field_ref = writer._add_object(field)
    annotations = page.get(NameObject("/Annots"), ArrayObject())
    if hasattr(annotations, "get_object"):
        annotations = annotations.get_object()
    annotations.append(field_ref)
    page[NameObject("/Annots")] = annotations
    with path.open("wb") as output:
        writer.write(output)


def _make_text_pair(entry: dict, release_dir: Path) -> None:
    year = entry["year"]
    t4_lines = [
        "T4 Statement of Remuneration Paid",
        f"Tax year {year}",
        f"Employer name {ISSUER}",
        f"Box 10 Province of employment {entry['province_of_employment']}",
        f"Box 14 Employment income {entry['salary']}",
        f"Box 17 Employee QPP contributions {entry['qpp']}",
        f"Box 18 Employee EI premiums {entry['ei']}",
        "Box 20 RPP contributions 0.00",
        f"Box 22 Income tax deducted {entry['federal_withholding']}",
        f"Box 24 EI insurable earnings {entry['salary']}",
        f"Box 26 QPP pensionable earnings {entry['salary']}",
        "Box 44 Union dues 0.00",
        "Box 52 Pension adjustment 0.00",
        f"Box 55 Employee PPIP premiums {entry['ppip']}",
        f"Box 28 CPP or QPP exempt {'Yes' if entry['cpp_qpp_exempt'] else 'No'}",
        f"Box 28 EI exempt {'Yes' if entry['ei_exempt'] else 'No'}",
        f"Box 28 PPIP exempt {'Yes' if entry['ppip_exempt'] else 'No'}",
    ]
    if year == 2020:
        t4_lines.append("Box 57 Employment income March 15 to May 9 5000.00")
    rl1_qpp_box = "B.A" if year >= 2024 else "B"
    rl1_lines = [
        "RL-1 Releve 1 Revenus emploi",
        f"Annee d'imposition {year}",
        f"Nom de l'employeur {ISSUER}",
        f"Case A Revenus d'emploi {entry['salary']}",
        f"Case {rl1_qpp_box} Cotisation au RRQ {entry['qpp']}",
        f"Case C Cotisation a l'assurance emploi {entry['ei']}",
        "Case D Cotisation a un RPA 0.00",
        f"Case E Impot du Quebec retenu {entry['quebec_withholding']}",
        "Case F Cotisation syndicale 0.00",
        f"Case G Salaire admissible au RRQ {entry['salary']}",
        f"Case H Cotisation au RQAP {entry['ppip']}",
        f"Case I Salaire admissible au RQAP {entry['salary']}",
        "Case 211 Avantage imposable 0.00",
    ]
    _write_text_pdf(release_dir / entry["t4"], t4_lines)
    _write_text_pdf(release_dir / entry["rl1"], rl1_lines)


def _update_form(source: Path, target: Path, values: dict[str, str]) -> None:
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError as exc:
        raise SystemExit("pypdf is required to generate official fillable fixtures") from exc

    reader = PdfReader(source)
    if reader.is_encrypted:
        reader.decrypt("")
    writer = PdfWriter(clone_from=reader)
    writer.update_page_form_field_values(writer.pages[0], values, auto_regenerate=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as output:
        writer.write(output)


def _make_official_pair(entry: dict, official_dir: Path, release_dir: Path) -> None:
    year = entry["year"]
    suffix = str(year)
    t4_values = {
        "Slip1EmployersName[0]": ISSUER,
        "Slip1Year[0]": suffix,
        "Slip1Box10[0]": entry["province_of_employment"],
        "Slip1Box14[0]": entry["salary"],
        "Slip1Box17[0]": entry["qpp"],
        "Slip1Box17A[0]": entry.get("qpp2", "0.00"),
        "Slip1Box18[0]": entry["ei"],
        "Slip1Box20[0]": "0.00",
        "Slip1Box22[0]": entry["federal_withholding"],
        "Slip1Box24[0]": entry["salary"],
        "Slip1Box26[0]": entry["salary"],
        "Slip1Box44[0]": "0.00",
        "Slip1Box52[0]": "0.00",
        "Slip1Box55[0]": entry["ppip"],
        "Slip1EmployersName[0].2": ISSUER,
        "Slip1Year[0].2": suffix,
        "Slip1Box10[0].2": entry["province_of_employment"],
        "Slip1Box14[0].2": entry["salary"],
        "Slip1Box17[0].2": entry["qpp"],
        "Slip1Box17A[0].2": entry.get("qpp2", "0.00"),
        "Slip1Box18[0].2": entry["ei"],
        "Slip1Box20[0].2": "0.00",
        "Slip1Box22[0].2": entry["federal_withholding"],
        "Slip1Box24[0].2": entry["salary"],
        "Slip1Box26[0].2": entry["salary"],
        "Slip1Box44[0].2": "0.00",
        "Slip1Box52[0].2": "0.00",
        "Slip1Box55[0].2": entry["ppip"],
    }
    rl1_values = {
        "nom2": ISSUER,
        "caseA": entry["salary"],
        "caseB-A": entry["qpp"],
        "caseB-B": entry.get("qpp2", "0.00"),
        "caseC": entry["ei"],
        "caseD": "0.00",
        "caseE": entry["quebec_withholding"],
        "caseF": "0.00",
        "caseG": entry["salary"],
        "caseH": entry["ppip"],
        "caseI": entry["salary"],
    }
    _update_form(official_dir / f"cra-t4-fill-{year}.pdf", release_dir / entry["t4"], t4_values)
    rl1_target = release_dir / entry["rl1"]
    _update_form(official_dir / f"rq-rl1-fill-{year}.pdf", rl1_target, rl1_values)
    _append_visible_text(rl1_target, ["Case 211 Avantage imposable 0.00"])
    _append_text_field(rl1_target, "case211", "0.00", (72, 42, 180, 58))


def _verify_generated_required(manifest: dict, fixture_root: Path, source_corpus: Path | None) -> None:
    generated_dir = fixture_root / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    for item in manifest.get("generated_required", []):
        target = generated_dir / item["name"]
        if not target.exists() and source_corpus is not None:
            source = source_corpus / "generated" / item["name"]
            if source.is_file():
                shutil.copyfile(source, target)
        _check(target, item)


def provision(manifest_path: Path, fixture_root: Path, source_corpus: Path | None, timeout: float) -> None:
    manifest = _read_manifest(manifest_path)
    official_dir = fixture_root / "official"
    release_dir = fixture_root / "generated" / "release"
    for item in manifest["official"]:
        _copy_or_download(item, official_dir, source_corpus, timeout)
    _verify_generated_required(manifest, fixture_root, source_corpus)
    for entry in manifest["annual_flow"]:
        if entry["source"] == "synthetic_text":
            _make_text_pair(entry, release_dir)
        elif entry["source"] == "official_fillable":
            _make_official_pair(entry, official_dir, release_dir)
        else:
            raise RuntimeError(f"unknown release fixture source: {entry['source']}")
    print(f"official PDF fixtures ready at {fixture_root}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--fixture-root", type=Path, default=DEFAULT_FIXTURE_ROOT)
    parser.add_argument(
        "--source-corpus",
        type=Path,
        default=None,
        help="Optional local official-pdf-acceptance directory to copy from before downloading.",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    provision(args.manifest, args.fixture_root, args.source_corpus, args.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import sys

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    BooleanObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    TextStringObject,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "pdf" / "synthetic"
DEFAULT_MANIFEST = DEFAULT_FIXTURE_ROOT / "manifest.json"
ISSUER = "EXAMPLE ROBOTICS INC"


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
            f"{path} does not match synthetic manifest: got {size} bytes {digest}, "
            f"expected {expected['bytes']} bytes {expected['sha256']}"
        )


def _require_reportlab():
    try:
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise SystemExit(
            "reportlab is required to generate synthetic fixtures; install development extras with "
            'python -m pip install ".[dev]"'
        ) from exc
    return canvas


def _write_text_pdf(path: Path, lines: list[str]) -> None:
    canvas = _require_reportlab()
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=(612, 792), invariant=1)
    y = 742
    for line in lines:
        pdf.drawString(72, y, line)
        y -= 18
    pdf.save()


def _base_pdf(title: str, year: int, labels: list[tuple[str, float, float]]) -> BytesIO:
    canvas = _require_reportlab()
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(612, 792), invariant=1)
    pdf.drawString(72, 742, title)
    pdf.drawString(72, 720, f"Tax year {year}")
    for label, x, y in labels:
        pdf.drawString(x, y + 4, label)
    pdf.save()
    buffer.seek(0)
    return buffer


def _field(
    writer: PdfWriter,
    name: str,
    rect: tuple[float, float, float, float],
    field_type: str = "/Tx",
) -> object:
    value = NameObject("/Off") if field_type == "/Btn" else TextStringObject("")
    field = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Annot"),
            NameObject("/Subtype"): NameObject("/Widget"),
            NameObject("/FT"): NameObject(field_type),
            NameObject("/T"): TextStringObject(name),
            NameObject("/V"): value,
            NameObject("/DV"): value,
            NameObject("/DA"): TextStringObject("/Helv 8 Tf 0 g"),
            NameObject("/Rect"): ArrayObject([FloatObject(item) for item in rect]),
            NameObject("/F"): NumberObject(4),
        }
    )
    return writer._add_object(field)


def _write_fillable_pdf(
    path: Path,
    title: str,
    year: int,
    fields: list[tuple[str, float, float, float, float, str]],
) -> None:
    labels = [(name, x - 165, y) for name, x, y, _, _, _ in fields]
    reader = PdfReader(_base_pdf(title, year, labels))
    writer = PdfWriter()
    writer.add_page(reader.pages[0])
    annotations = ArrayObject()
    form_fields = ArrayObject()
    for name, x, y, width, height, field_type in fields:
        reference = _field(writer, name, (x, y, x + width, y + height), field_type)
        annotations.append(reference)
        form_fields.append(reference)
    writer.pages[0][NameObject("/Annots")] = annotations
    writer._root_object.update(
        {
            NameObject("/AcroForm"): DictionaryObject(
                {
                    NameObject("/Fields"): form_fields,
                    NameObject("/NeedAppearances"): BooleanObject(True),
                }
            )
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as output:
        writer.write(output)


def _t4_fields() -> list[tuple[str, float, float, float, float, str]]:
    names = [
        "Slip1EmployersName[0]",
        "Slip1Year[0]",
        "Slip1Box10[0]",
        "Slip1Box14[0]",
        "Slip1Box17[0]",
        "Slip1Box17A[0]",
        "Slip1Box18[0]",
        "Slip1Box20[0]",
        "Slip1Box22[0]",
        "Slip1Box24[0]",
        "Slip1Box26[0]",
        "Slip1Box44[0]",
        "Slip1Box52[0]",
        "Slip1Box55[0]",
        "Slip1CPP[0]",
        "Slip1EI[0]",
        "Slip1PPIP[0]",
    ]
    copied = [name + ".2" for name in names if not name.startswith("Slip1CPP") and not name.startswith("Slip1EI") and not name.startswith("Slip1PPIP")]
    fields: list[tuple[str, float, float, float, float, str]] = []
    for index, name in enumerate(names):
        fields.append((name, 250, 690 - index * 15, 160, 14, "/Tx"))
    for index, name in enumerate(copied):
        fields.append((name, 250, 320 - index * 18, 160, 14, "/Tx"))
    return fields


def _t2202_fields() -> list[tuple[str, float, float, float, float, str]]:
    names = [
        "Slip1Year[0]",
        "Part1_Name_Address[0]",
        "Totals_Box21_row5[0]",
        "Totals_Box25_row5[0]",
        "Totals_Box26_row5[0]",
        "Totals_Box27_row5[0]",
    ]
    return [(name, 270, 650 - index * 20, 160, 14, "/Tx") for index, name in enumerate(names)]


def _rl1_fields() -> list[tuple[str, float, float, float, float, str]]:
    names = [
        "nom2",
        "caseA",
        "caseB-A",
        "caseB-B",
        "caseBA",
        "caseBB",
        "caseC",
        "caseD",
        "caseE",
        "caseF",
        "caseG",
        "caseH",
        "caseI",
        "caseS",
        "case211",
    ]
    return [(name, 240, 650 - index * 20, 150, 14, "/Tx") for index, name in enumerate(names)]


def _rl8_fields() -> list[tuple[str, float, float, float, float, str]]:
    names = ["an", "nom2", "caseA", "caseB1", "caseC"]
    return [(name, 240, 650 - index * 20, 150, 14, "/Tx") for index, name in enumerate(names)]


def _make_text_pair(entry: dict, release_dir: Path) -> None:
    year = entry["year"]
    t4_lines = [
        "T4 Statement of Remuneration Paid",
        f"Tax year {year}",
        f"Employer name {ISSUER}",
        f"Box 10 Province of employment {entry['province_of_employment']}",
        f"Box 14 Employment income {entry['salary']}",
        f"Box 17 Employee QPP contributions {entry['qpp']}",
        f"Box 17A Employee QPP2 contributions {entry.get('qpp2', '0.00')}",
        f"Box 18 Employee EI premiums {entry['ei']}",
        "Box 20 RPP contributions 0.00",
        f"Box 22 Income tax deducted {entry['federal_withholding']}",
        f"Box 24 EI insurable earnings {entry['salary']}",
        f"Box 26 QPP pensionable earnings {entry['salary']}",
        "Box 44 Union dues 0.00",
        "Box 52 Pension adjustment 0.00",
        f"Box 55 Employee PPIP premiums {entry['ppip']}",
        f"Box 28 cpp_qpp_exempt {str(entry['cpp_qpp_exempt']).lower()}",
        f"Box 28 ei_exempt {str(entry['ei_exempt']).lower()}",
        f"Box 28 ppip_exempt {str(entry['ppip_exempt']).lower()}",
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
        f"Case B.B Deuxieme cotisation au RRQ {entry.get('qpp2', '0.00')}",
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


def provision(manifest_path: Path, fixture_root: Path) -> None:
    manifest = _read_manifest(manifest_path)
    acroform_dir = fixture_root / "acroforms"
    _write_fillable_pdf(acroform_dir / "synthetic-t4-2024.pdf", "T4 Statement of Remuneration Paid", 2024, _t4_fields())
    _write_fillable_pdf(acroform_dir / "synthetic-t4-2025.pdf", "T4 Statement of Remuneration Paid", 2025, _t4_fields())
    _write_fillable_pdf(acroform_dir / "synthetic-t2202-2024.pdf", "T2202 Tuition and Enrolment Certificate", 2024, _t2202_fields())
    _write_fillable_pdf(acroform_dir / "synthetic-t2202-2025.pdf", "T2202 Tuition and Enrolment Certificate", 2025, _t2202_fields())
    _write_fillable_pdf(acroform_dir / "synthetic-rl1-2024.pdf", "RL-1 Releve 1 Revenus emploi", 2024, _rl1_fields())
    _write_fillable_pdf(acroform_dir / "synthetic-rl1-2025.pdf", "RL-1 Releve 1 Revenus emploi", 2025, _rl1_fields())
    _write_fillable_pdf(acroform_dir / "synthetic-rl8-2022.pdf", "RL-8 Releve 8 Montant pour etudes postsecondaires", 2022, _rl8_fields())
    _write_text_pdf(
        acroform_dir / "synthetic-t4-instructions-2025.pdf",
        ["T4 Statement of Remuneration Paid", "Instructions", "Do not report this page as a slip"],
    )
    release_dir = fixture_root / "generated" / "release"
    for entry in manifest["annual_flow"]:
        _make_text_pair(entry, release_dir)
    for item in manifest["acroforms"]:
        _check(acroform_dir / item["name"], item)
    for item in manifest["release"]:
        _check(release_dir / item["name"], item)
    print(f"synthetic PDF fixtures ready at {fixture_root}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--fixture-root", type=Path, default=DEFAULT_FIXTURE_ROOT)
    args = parser.parse_args(argv)
    provision(args.manifest, args.fixture_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

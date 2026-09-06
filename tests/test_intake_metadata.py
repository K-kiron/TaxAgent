from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject

from taxagent.intake import import_pdf_batch
from taxagent.web import local_app


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "pdf" / "synthetic" / "acroforms"


def _synthetic_fixture(name: str) -> bytes:
    path = FIXTURE_DIR / name
    if not path.exists():
        raise AssertionError(
            "synthetic PDF fixture is unavailable; run "
            "python scripts/release/provision_synthetic_pdf_fixtures.py"
        )
    return path.read_bytes()


def _filled_synthetic_form(name: str, values: dict[str, object]) -> bytes:
    reader = PdfReader(BytesIO(_synthetic_fixture(name)))
    if reader.is_encrypted:
        assert reader.decrypt("")
    writer = PdfWriter(clone_from=reader)
    writer.update_page_form_field_values(writer.pages[0], values, auto_regenerate=False)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _client() -> TestClient:
    return TestClient(local_app.app, base_url="http://127.0.0.1:8056")


def _t4_values(*, include_source_metadata: bool = True) -> dict[str, object]:
    values: dict[str, object] = {
        "Slip1EmployersName[0]": "Northern Lab Coop",
        "Slip1Year[0]": "2025",
        "Slip1Box14[0]": "50000.00",
        "Slip1Box17[0]": "2976.00",
        "Slip1Box17A[0]": "0.00",
        "Slip1Box18[0]": "655.00",
        "Slip1Box20[0]": "0.00",
        "Slip1Box22[0]": "6000.00",
        "Slip1Box24[0]": "50000.00",
        "Slip1Box26[0]": "50000.00",
        "Slip1Box44[0]": "0.00",
        "Slip1Box52[0]": "0.00",
        "Slip1Box55[0]": "247.00",
    }
    if include_source_metadata:
        values.update(
            {
                "Slip1Box10[0]": "QC",
                "Slip1CPP[0]": NameObject("/Off"),
                "Slip1EI[0]": NameObject("/Off"),
                "Slip1PPIP[0]": NameObject("/Off"),
            }
        )
    return values


def _rl1_values() -> dict[str, object]:
    return {
        "nom2": "Northern Lab Coop",
        "caseA": "50000.00",
        "caseBA": "2976.00",
        "caseBB": "0.00",
        "caseC": "655.00",
        "caseD": "0.00",
        "caseE": "5000.00",
        "caseF": "0.00",
        "caseG": "50000.00",
        "caseH": "247.00",
        "caseI": "50000.00",
        "case211": "0.00",
    }


def _t2202_values(*, include_months: bool = True) -> dict[str, object]:
    values: dict[str, object] = {
        "Slip1Year[0]": "2025",
        "Part1_Name_Address[0]": "City College",
        "Totals_Box26_row5[0]": "4200.00",
    }
    if include_months:
        values.update(
            {
                "Totals_Box21_row5[0]": "0",
                "Totals_Box25_row5[0]": "8",
            }
        )
    return values


def test_synthetic_acroforms_preserve_t4_metadata_and_t2202_explicit_months():
    result = import_pdf_batch(
        [
            ("t4.pdf", _filled_synthetic_form("synthetic-t4-2025.pdf", _t4_values())),
            ("t2202.pdf", _filled_synthetic_form("synthetic-t2202-2025.pdf", _t2202_values())),
        ],
        enable_ocr=False,
    )

    t4 = next(candidate for candidate in result.candidates if candidate.slip_type == "T4")
    t2202 = next(candidate for candidate in result.candidates if candidate.slip_type == "T2202")

    assert t4.metadata["province_of_employment"].value == "QC"
    assert t4.metadata["province_of_employment"].value_state == "present"
    assert t4.metadata["cpp_qpp_exempt"].value is False
    assert t4.metadata["cpp_qpp_exempt"].value_state == "off"
    assert t4.metadata["ei_exempt"].value is False
    assert t4.metadata["ppip_exempt"].value is False
    assert t2202.fields["24"].value == "0"
    assert t2202.fields["24"].value_state == "present"
    assert t2202.fields["25"].value == "8"

    workspace = local_app.workspace_from_import(result)
    slips = workspace.years["2025"].input["slips"]
    imported_t4 = next(slip for slip in slips if slip["slip_type"] == "T4")
    imported_t2202 = next(slip for slip in slips if slip["slip_type"] == "T2202")
    evidence = workspace.years["2025"].evidence

    assert imported_t4["province_of_employment"] == "QC"
    assert imported_t4["cpp_qpp_exempt"] is False
    assert imported_t4["ei_exempt"] is False
    assert imported_t4["ppip_exempt"] is False
    assert imported_t2202["fields"]["24"] == "0"
    assert imported_t2202["fields"]["25"] == "8"
    assert evidence[t4.candidate_id]["metadata"]["province_of_employment"]["accepted_value"] == "QC"
    assert evidence[t4.candidate_id]["metadata"]["cpp_qpp_exempt"]["accepted_value"] is False


def test_public_import_corrections_for_missing_metadata_survive_reconcile_and_calculate():
    client = _client()
    response = client.post(
        "/api/import-pdfs",
        files=[
            (
                "files",
                ("t4.pdf", _filled_synthetic_form("synthetic-t4-2025.pdf", _t4_values(include_source_metadata=False)), "application/pdf"),
            ),
            ("files", ("rl1.pdf", _filled_synthetic_form("synthetic-rl1-2025.pdf", _rl1_values()), "application/pdf")),
            (
                "files",
                ("t2202.pdf", _filled_synthetic_form("synthetic-t2202-2025.pdf", _t2202_values(include_months=False)), "application/pdf"),
            ),
        ],
    )
    assert response.status_code == 200
    workspace = response.json()["workspace"]
    workspace["years"]["2025"]["input"] = local_app._sample_input().model_copy(
        update={"schema_version": "qc-return-v2", "slips": []}
    ).model_dump(mode="json")
    workspace["active_years"] = [2025]
    t4_id = next(
        candidate["candidate_id"]
        for candidate in response.json()["import_result"]["candidates"]
        if candidate["slip_type"] == "T4" and candidate["decision"] == "accepted_auto"
    )
    t2202_id = next(
        candidate["candidate_id"]
        for candidate in response.json()["import_result"]["candidates"]
        if candidate["slip_type"] == "T2202" and candidate["decision"] == "accepted_auto"
    )

    blocked = client.post("/api/calculate-years", json=workspace)
    assert blocked.status_code == 200
    blocker_paths = {
        fact["path"]
        for fact in blocked.json()["results"]["2025"]["missing_facts"]
    }
    assert f"slips.0.province_of_employment" in blocker_paths
    assert f"slips.2.fields.24" in blocker_paths
    assert f"slips.2.fields.25" in blocker_paths

    corrections = [
        {
            "candidate_id": t4_id,
            "metadata": {
                "province_of_employment": "QC",
                "cpp_qpp_exempt": False,
                "ei_exempt": False,
                "ppip_exempt": False,
            },
            "reason": "Reviewed against the synthetic T4 source widgets.",
        },
        {
            "candidate_id": t2202_id,
            "fields": {"24": "0", "25": "8"},
            "reason": "Reviewed against the synthetic T2202 enrolment boxes.",
        },
    ]
    reconciled = client.post(
        "/api/reconcile-workspace",
        json={"workspace": blocked.json()["workspace"], "active_years": [2025], "corrections": corrections},
    )
    assert reconciled.status_code == 200
    calculated = client.post("/api/calculate-years", json=reconciled.json())
    assert calculated.status_code == 200
    repeated = client.post("/api/calculate-years", json=calculated.json()["workspace"])
    assert repeated.status_code == 200

    final = repeated.json()
    final_year = final["workspace"]["years"]["2025"]
    final_t4 = next(slip for slip in final_year["input"]["slips"] if slip["document_id"] == t4_id)
    final_t2202 = next(slip for slip in final_year["input"]["slips"] if slip["document_id"] == t2202_id)
    final_paths = {
        fact["path"]
        for fact in final["results"]["2025"].get("missing_facts", [])
    }

    assert final["results"]["2025"]["status"] == "complete"
    assert final_t4["province_of_employment"] == "QC"
    assert final_t4["cpp_qpp_exempt"] is False
    assert final_t4["ei_exempt"] is False
    assert final_t4["ppip_exempt"] is False
    assert final_t2202["fields"]["24"] == "0"
    assert final_t2202["fields"]["25"] == "8"
    assert f"slips.0.province_of_employment" not in final_paths
    assert f"slips.2.fields.24" not in final_paths
    assert final_year["evidence"][t2202_id]["fields"]["24"]["correction_only"] is True
    assert final_year["evidence"][t2202_id]["fields"]["24"]["accepted_value"] == "0"

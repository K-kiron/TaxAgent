
from __future__ import annotations

import argparse
from collections.abc import Iterable
import base64
from hashlib import sha256
from importlib import metadata
import json
from pathlib import Path
import sys
from typing import Any


LOOPBACK_BASE_URL = "http://127.0.0.1:8056"


def _read_manifest(fixture_root: Path) -> dict[str, Any]:
    path = fixture_root / "manifest.json"
    if not path.is_file():
        raise AssertionError(f"official fixture manifest is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    h = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_fixture(path: Path, expected: dict[str, Any]) -> None:
    if not path.is_file():
        raise AssertionError(f"official fixture is missing: {path}")
    size = path.stat().st_size
    digest = _digest(path)
    if size != expected["bytes"] or digest != expected["sha256"]:
        raise AssertionError(
            f"official fixture changed: {path} got {size} bytes {digest}, "
            f"expected {expected['bytes']} bytes {expected['sha256']}"
        )


def _assert_official_fixtures(fixture_root: Path, manifest: dict[str, Any]) -> None:
    official_dir = fixture_root / "official"
    for item in manifest["official"]:
        _check_fixture(official_dir / item["name"], item)

    generated_dir = fixture_root / "generated"
    for item in manifest.get("generated_required", []):
        _check_fixture(generated_dir / item["name"], item)

    release_dir = generated_dir / "release"
    for entry in manifest["annual_flow"]:
        for key in ("t4", "rl1"):
            path = release_dir / entry[key]
            if not path.is_file():
                raise AssertionError(f"release fixture is missing: {path}")



def _record_sha256_value(digest: str) -> str:
    return base64.urlsafe_b64encode(bytes.fromhex(digest)).rstrip(b"=").decode("ascii")


def _assert_rapidocr_model_artifacts() -> None:
    expected = {
        "rapidocr/models/PP-OCRv6_det_small.onnx": {
            "bytes": 9929594,
            "sha256": "090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f",
        },
        "rapidocr/models/PP-OCRv6_rec_small.onnx": {
            "bytes": 21234383,
            "sha256": "6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884",
        },
        "rapidocr/models/ch_ppocr_mobile_v2.0_cls_mobile.onnx": {
            "bytes": 585532,
            "sha256": "e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c",
        },
    }
    dist = metadata.distribution("rapidocr")
    if dist.version != "3.9.2":
        raise AssertionError(f"rapidocr version mismatch: {dist.version}")
    record = {str(item).replace("\\", "/"): item for item in dist.files or []}
    for name, expected_item in expected.items():
        record_item = record.get(name)
        if record_item is None:
            raise AssertionError(f"rapidocr model missing from distribution RECORD: {name}")
        path = Path(dist.locate_file(record_item))
        if not path.is_file():
            raise AssertionError(f"rapidocr model file missing from installed artifact: {path}")
        size = path.stat().st_size
        digest = _digest(path)
        if size != expected_item["bytes"] or digest != expected_item["sha256"]:
            raise AssertionError(
                f"rapidocr model changed: {name} got {size} bytes {digest}, "
                f"expected {expected_item['bytes']} bytes {expected_item['sha256']}"
            )
        record_hash = getattr(record_item, "hash", None)
        record_size = getattr(record_item, "size", None)
        if record_size != expected_item["bytes"] or record_hash is None:
            raise AssertionError(f"rapidocr RECORD metadata is incomplete for {name}")
        if record_hash.mode != "sha256" or record_hash.value != _record_sha256_value(expected_item["sha256"]):
            raise AssertionError(f"rapidocr RECORD hash mismatch for {name}: {record_hash}")


def _assert_installed_package(repo_root: Path | None) -> None:
    import taxagent

    package_path = Path(taxagent.__file__).resolve()
    if repo_root is not None:
        source_root = (repo_root / "src").resolve()
        try:
            package_path.relative_to(source_root)
        except ValueError:
            return
        raise AssertionError(f"taxagent imported from source checkout, not installed wheel: {package_path}")


def _line(result: dict[str, Any], form_id: str, line_id: str) -> dict[str, Any]:
    return next(
        line for line in result["lines"] if line["form_id"] == form_id and line["line_id"] == line_id
    )


def _assert_success(response, endpoint: str) -> dict[str, Any]:
    if response.status_code != 200:
        raise AssertionError(f"{endpoint} failed with {response.status_code}: {response.text}")
    return response.json()


def _client():
    from fastapi.testclient import TestClient
    from taxagent.web.local_app import app

    return TestClient(app, base_url=LOOPBACK_BASE_URL)


def _release_uploads(fixture_root: Path, manifest: dict[str, Any]) -> list[tuple[str, tuple[str, bytes, str]]]:
    release_dir = fixture_root / "generated" / "release"
    uploads = []
    for entry in manifest["annual_flow"]:
        for key in ("t4", "rl1"):
            path = release_dir / entry[key]
            uploads.append(("files", (path.name, path.read_bytes(), "application/pdf")))
    return uploads


def _post_import(client, uploads: list[tuple[str, tuple[str, bytes, str]]]) -> dict[str, Any]:
    return _assert_success(client.post("/api/import-pdfs", files=uploads), "/api/import-pdfs")


def _reconcile(
    client,
    workspace: dict[str, Any],
    active_years: Iterable[int],
    corrections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = {
        "workspace": workspace,
        "active_years": list(active_years),
        "corrections": corrections or [],
        "decisions": [],
        "carryforward_choices": [],
    }
    return _assert_success(client.post("/api/reconcile-workspace", json=payload), "/api/reconcile-workspace")


def _calculate(client, workspace: dict[str, Any]) -> dict[str, Any]:
    return _assert_success(client.post("/api/calculate-years", json=workspace), "/api/calculate-years")


def _apply_personal_facts(data: dict[str, Any], entry: dict[str, Any]) -> None:
    """Fill explicit non-PDF facts without modifying imported slip fields."""

    year = int(entry["year"])
    data["schema_version"] = "qc-return-v2"
    data["province_dec31"] = "QC"
    data["taxpayer"].update(
        {
            "full_year_canada_resident": True,
            "full_year_quebec_resident": True,
            "province_dec31": "QC",
            "age_dec31": 30,
            "marital_status": "single",
            "dependant_count": 0,
            "deceased_return": False,
            "bankruptcy_return": False,
            "has_self_employment": False,
            "has_capital_gains": False,
            "has_rental_income": False,
            "has_foreign_income_or_tax": False,
            "has_foreign_property_over_100k": False,
            "has_crypto_transactions": False,
            "has_pension_or_benefit_income": False,
            "has_indian_act_exempt_income": False,
            "has_disability_or_caregiver_claim": False,
            "has_employment_expenses": False,
            "has_medical_expenses": False,
            "has_donations": False,
            "has_childcare_expenses": False,
            "has_moving_expenses": False,
            "has_tips_or_other_employment_income": False,
            "has_student_loan_interest": False,
            "received_qpp_disability_pension": False,
            "made_qpp_cpt30_election": False,
            "was_full_time_student_more_than_13_weeks": False,
        }
    )
    data["inventory"].update(
        {
            "income_sources_reviewed": True,
            "deductions_reviewed": True,
            "credits_reviewed": True,
            "cra_records_reviewed": True,
            "revenu_quebec_records_reviewed": True,
            "no_income_sources": False,
        }
    )
    data["federal_tuition"].update(
        {
            "has_current_tuition": False,
            "has_prior_unused": False,
            "wants_transfer": False,
            "wants_canada_training_credit": False,
        }
    )
    data["quebec_tuition"].update(
        {
            "has_current_tuition": False,
            "institution_outside_quebec": False,
            "has_prior_unused": False,
            "wants_transfer": False,
        }
    )
    data["rrsp"].update(
        {
            "has_contributions": False,
            "has_prior_unused_contributions": False,
            "has_hbp_or_llp_activity": False,
        }
    )
    data["instalments"].update(
        {
            "federal_reviewed": True,
            "federal_paid": "0.00",
            "quebec_reviewed": True,
            "quebec_paid": "0.00",
        }
    )
    data["quebec_schedule_b"].update(
        {
            "living_alone_reviewed": True,
            "eligible_for_living_alone_amount": False,
        }
    )
    origins = {str(origin): "0.00" for origin in range(year - 5, year)}
    data["student_loan_interest"].update(
        {
            "reviewed": True,
            "qualifying_government_loans_confirmed": True,
            "federal_current_year_paid": "0.00",
            "federal_unused_by_origin_year": origins,
            "federal_claim_amount": "0.00",
            "quebec_prior_unused": "0.00",
            "quebec_current_year_paid": "0.00",
            "quebec_claim_amount": "0.00",
        }
    )
    for origin, amount in origins.items():
        field = f"federal_unused_{origin}"
        if field in data["student_loan_interest"]:
            data["student_loan_interest"][field] = amount
    data["scholarships"].update({"reviewed": True, "awards": [], "part_time_programs": []})
    data["resp_eap"].update(
        {
            "reviewed": True,
            "has_other_resp_payments": False,
            "qesi_cumulative_amount_over_3600": False,
            "payments": [],
        }
    )
    data.setdefault("pandemic_repayment", {}).update({"reviewed": False})
    data["additional_return_screens"].update(
        {
            "immigrated_or_emigrated_2025": False,
            "immigrated_or_emigrated_in_tax_year": False,
            "quebec_trust_return": False,
            "separate_post_death_return": False,
            "quebec_enterprise_registration_or_annual_fee": False,
        }
    )
    data["drug_insurance"].update(
        {
            "reviewed": True,
            "group_plan_months": entry["drug_group_plan_months"],
            "group_plan_source": entry["drug_group_plan_source"],
            "eligible_student_months": entry["drug_eligible_student_months"],
            "other_exemption_applies": entry["drug_other_exemption_applies"],
        }
    )
    data["refundable_credits"].update(
        {
            "work_premium_answers_reviewed": True,
            "solidarity_answers_reviewed": True,
            "canada_workers_benefit_answers_reviewed": True,
            "rl19_advance_payments_reviewed": True,
            "rl19_box_a": "0.00",
            "rl19_box_b": "0.00",
            "rl19_has_other_advance_boxes": False,
            "cwb_incarcerated_90_days": False,
            "cwb_foreign_officer_exempt": False,
            "advanced_cwb_paid": "0.00",
            "advanced_cwb_disability_paid": "0.00",
            "work_premium_eligible_status": True,
            "quebec_work_premium_full_time_student": False,
            "transferred_schedule_s_amount": False,
            "family_allowance_received_for_self": False,
            "turned_18_before_december": True,
            "designated_as_dependent_child": False,
            "incarcerated_over_183_days": False,
            "adapted_work_premium_eligible": False,
            "work_premium_supplement_months": 0,
            "request_tax_shield": False,
            "wants_solidarity_credit": False,
        }
    )


def _populate_personal_facts(workspace: dict[str, Any], manifest: dict[str, Any]) -> None:
    for entry in manifest["annual_flow"]:
        _apply_personal_facts(workspace["years"][str(entry["year"])]["input"], entry)


def _year_slips(workspace: dict[str, Any], year: int) -> list[dict[str, Any]]:
    return workspace["years"][str(year)]["input"]["slips"]


def _slip_snapshot(workspace: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    snapshot = {}
    for entry in manifest["annual_flow"]:
        year = int(entry["year"])
        snapshot[str(year)] = {
            slip["document_id"]: {
                "slip_type": slip["slip_type"],
                "tax_year": slip["tax_year"],
                "issuer_id": slip["issuer_id"],
                "province_of_employment": slip.get("province_of_employment"),
                "cpp_qpp_exempt": slip.get("cpp_qpp_exempt"),
                "ei_exempt": slip.get("ei_exempt"),
                "ppip_exempt": slip.get("ppip_exempt"),
                "fields": slip["fields"],
            }
            for slip in _year_slips(workspace, year)
        }
    return snapshot



def _release_metadata_corrections(workspace: dict[str, Any], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    corrections: list[dict[str, Any]] = []
    metadata_keys = ("province_of_employment", "cpp_qpp_exempt", "ei_exempt", "ppip_exempt")
    for entry in manifest["annual_flow"]:
        year = int(entry["year"])
        source_notes = entry.get("fixture_fact_sources", {})
        for key in metadata_keys:
            source = source_notes.get(key, "")
            if not source.startswith("T4 box"):
                raise AssertionError(f"{year} metadata {key} is not backed by T4 source evidence: {source!r}")
        expected = {key: entry[key] for key in metadata_keys}
        for slip in _year_slips(workspace, year):
            if slip["slip_type"] != "T4":
                continue
            missing = {key: value for key, value in expected.items() if slip.get(key) is None}
            if missing:
                corrections.append(
                    {
                        "candidate_id": slip["document_id"],
                        "metadata": missing,
                        "reason": "Release acceptance mirrors visible T4 Box 10/28 fixture evidence.",
                    }
                )
    return corrections


def _assert_import_workspace(payload: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    import_result = payload["import_result"]
    workspace = payload["workspace"]
    errors = [doc for doc in import_result["documents"] if doc["status"] not in {"processed", "duplicate"}]
    if errors or workspace["file_errors"] or workspace["unassigned_candidates"]:
        raise AssertionError(json.dumps({"errors": errors, "workspace": workspace}, indent=2))

    expected_years = [entry["year"] for entry in manifest["annual_flow"]]
    if workspace["active_years"] != expected_years:
        raise AssertionError(f"active years mismatch: {workspace['active_years']} != {expected_years}")
    if len(workspace["source_candidates"]) < 2 * len(expected_years):
        raise AssertionError("source candidate registry did not retain every imported release PDF")

    for entry in manifest["annual_flow"]:
        year = int(entry["year"])
        year_state = workspace["years"][str(year)]
        if year_state["unresolved_candidates"]:
            raise AssertionError(f"{year} has unresolved import candidates: {year_state}")
        unexpected_duplicates = [
            item for item in year_state["duplicate_candidates"]
            if item.get("reason") != "duplicate_candidate"
            or item.get("candidate", {}).get("decision") != "duplicate"
            or not any(
                str(reason).startswith("logical_duplicate_of:")
                for reason in item.get("review_reasons", [])
            )
        ]
        if unexpected_duplicates:
            raise AssertionError(f"{year} has unexpected duplicate import candidates: {unexpected_duplicates}")
        observed = {(slip["slip_type"], slip["tax_year"]) for slip in _year_slips(workspace, year)}
        if ("T4", year) not in observed or ("RL1", year) not in observed:
            raise AssertionError(f"{year} missing imported T4/RL1 slips: {_year_slips(workspace, year)}")
    return workspace


def _assert_rebuilt_slips_unchanged(
    original: dict[str, Any],
    calculated_workspace: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    rebuilt = _slip_snapshot(calculated_workspace, manifest)
    if rebuilt != original:
        raise AssertionError(
            "calculation rebuilt imported slips with different values or metadata:\n"
            + json.dumps({"before": original, "after": rebuilt}, indent=2, sort_keys=True)
        )


def _assert_required_t4_metadata(workspace: dict[str, Any], manifest: dict[str, Any]) -> None:
    for entry in manifest["annual_flow"]:
        year = int(entry["year"])
        expected = {
            "province_of_employment": entry["province_of_employment"],
            "cpp_qpp_exempt": entry["cpp_qpp_exempt"],
            "ei_exempt": entry["ei_exempt"],
            "ppip_exempt": entry["ppip_exempt"],
        }
        t4_slips = [slip for slip in _year_slips(workspace, year) if slip["slip_type"] == "T4"]
        if not t4_slips:
            raise AssertionError(f"{year} has no T4 slip after public import")
        for slip in t4_slips:
            actual = {key: slip.get(key) for key in expected}
            if actual != expected:
                raise AssertionError(f"{year} T4 metadata mismatch: {actual} != {expected}")


def _assert_evidence(workspace: dict[str, Any], manifest: dict[str, Any]) -> None:
    for entry in manifest["annual_flow"]:
        year = int(entry["year"])
        evidence = workspace["years"][str(year)]["evidence"]
        t4 = next(item for item in evidence.values() if item["slip_type"] == "T4")
        rl1 = next(item for item in evidence.values() if item["slip_type"].replace("-", "") == "RL1")
        assert t4["fields"]["14"]["accepted_value"] == entry["salary"]
        assert t4["fields"]["17"]["accepted_value"] == entry["qpp"]
        assert t4["fields"]["18"]["accepted_value"] == entry["ei"]
        assert t4["fields"]["55"]["accepted_value"] == entry["ppip"]
        assert rl1["fields"]["A"]["accepted_value"] == entry["salary"]
        rl1_qpp_box = "B.A" if year >= 2024 else "B"
        assert rl1["fields"][rl1_qpp_box]["accepted_value"] == entry["qpp"]
        assert rl1["fields"]["H"]["accepted_value"] == entry["ppip"]


def _assert_year_result(result: dict[str, Any], entry: dict[str, Any]) -> None:
    year = entry["year"]
    if result["status"] != "complete":
        raise AssertionError(f"{year} did not complete: {json.dumps(result, indent=2, sort_keys=True)}")
    expected_profile = (
        "2025-qc-single-salaried-student-v1"
        if year == 2025
        else f"{year}-qc-single-salaried-student-v2"
    )
    assert result["coverage_profile_id"] == expected_profile
    assert result["federal_refund_or_balance"] == entry["expected_federal_refund_or_balance"]
    assert result["quebec_refund_or_balance"] == entry["expected_quebec_refund_or_balance"]
    assert len(result["lines"]) >= entry["expected_line_count"]

    t1_income = _line(result, "T1", "10100")
    tp1_income = _line(result, "TP1", "101")
    tp1_qpp = _line(result, "TP1", "98")
    assert t1_income["value"] == entry["salary"]
    assert tp1_income["value"] == entry["salary"]
    assert tp1_qpp["value"] == entry["qpp"]
    assert t1_income["source_ids"]
    assert tp1_income["source_ids"]
    assert result["ruleset_hash"]


def _assert_complete_batch(
    response: dict[str, Any],
    workspace_before_calculate: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    if response["status"] != "complete":
        raise AssertionError(f"batch calculation did not complete: {json.dumps(response, indent=2, sort_keys=True)}")
    expected_years = [str(entry["year"]) for entry in manifest["annual_flow"]]
    if sorted(response["results"]) != expected_years:
        raise AssertionError(f"calculated years mismatch: {sorted(response['results'])} != {expected_years}")
    for entry in manifest["annual_flow"]:
        _assert_year_result(response["results"][str(entry["year"])], entry)

    _assert_required_t4_metadata(response["workspace"], manifest)
    _assert_rebuilt_slips_unchanged(_slip_snapshot(workspace_before_calculate, manifest), response["workspace"], manifest)
    _assert_evidence(response["workspace"], manifest)


def _assert_scan_import(client, scan_fixture: Path | None) -> None:
    if scan_fixture is None:
        return
    payload = _post_import(
        client,
        [("files", (scan_fixture.name, scan_fixture.read_bytes(), "application/pdf"))],
    )
    candidates = payload["import_result"]["candidates"]
    if len(candidates) != 1:
        raise AssertionError(f"scan fixture produced unexpected candidates: {candidates}")
    candidate = candidates[0]
    assert candidate["fields"]["14"]["method"] == "ocr_rapidocr"
    assert candidate["fields"]["14"]["value"] == "45000.00"


def run_acceptance(repo_root: Path | None, fixture_root: Path, scan_fixture: Path | None) -> None:
    _assert_installed_package(repo_root)
    manifest = _read_manifest(fixture_root)
    _assert_official_fixtures(fixture_root, manifest)
    client = _client()
    _assert_rapidocr_model_artifacts()
    _assert_scan_import(client, scan_fixture)

    import_payload = _post_import(client, _release_uploads(fixture_root, manifest))
    workspace = _assert_import_workspace(import_payload, manifest)
    workspace = json.loads(json.dumps(workspace))
    active_years = [entry["year"] for entry in manifest["annual_flow"]]
    corrections = _release_metadata_corrections(workspace, manifest)
    workspace = _reconcile(client, workspace, active_years, corrections)
    _populate_personal_facts(workspace, manifest)

    first = _calculate(client, workspace)
    _assert_complete_batch(first, workspace, manifest)

    roundtripped_workspace = json.loads(json.dumps(first["workspace"], sort_keys=True))
    second = _calculate(client, roundtripped_workspace)
    _assert_complete_batch(second, first["workspace"], manifest)
    for year in first["results"]:
        assert second["results"][year]["federal_refund_or_balance"] == first["results"][year]["federal_refund_or_balance"]
        assert second["results"][year]["quebec_refund_or_balance"] == first["results"][year]["quebec_refund_or_balance"]
        assert second["results"][year]["input_digest"] == first["results"][year]["input_digest"]

    print("installed PDF release acceptance passed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--scan-fixture", type=Path, default=None)
    args = parser.parse_args(argv)
    run_acceptance(
        args.repo_root.resolve() if args.repo_root else None,
        args.fixtures.resolve(),
        args.scan_fixture.resolve() if args.scan_fixture else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

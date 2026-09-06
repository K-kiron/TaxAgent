"""Offline local browser app for 2025 Quebec return preparation.

This app is separate from the public festival demo. It keeps return inputs in
browser memory unless the user explicitly imports or exports JSON.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import importlib
import json
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from ..returns import (
    AdditionalReturnScreenInput,
    CompletenessBlocker,
    DocumentInventory,
    DrugInsuranceInput,
    FederalTuitionInput,
    InstalmentInput,
    QuebecScheduleBInput,
    QuebecTuitionInput,
    RefundableCreditInput,
    RespEapInput,
    RrspInput,
    SlipInput,
    ScholarshipInput,
    StudentLoanInterestInput,
    TaxReturnInput,
    TaxReturnResult,
    TaxpayerFacts,
    preflight,
)
from ..returns.sources import SOURCES


MAX_REQUEST_BYTES = 256 * 1024
PROFILE_ID = "2025-qc-single-salaried-student-v1"
_STATIC = Path(__file__).parent / "static"
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

app = FastAPI(
    title="TaxAgent Local Return Workspace",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "frame-src 'self' blob:; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "form-action 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _blank_input() -> TaxReturnInput:
    return TaxReturnInput(
        tax_year=2025,
        province_dec31="QC",
        taxpayer=TaxpayerFacts(),
        inventory=DocumentInventory(),
        federal_tuition=FederalTuitionInput(),
        quebec_tuition=QuebecTuitionInput(),
        rrsp=RrspInput(),
        instalments=InstalmentInput(),
        quebec_schedule_b=QuebecScheduleBInput(),
        student_loan_interest=StudentLoanInterestInput(),
        scholarships=ScholarshipInput(),
        resp_eap=RespEapInput(),
        additional_return_screens=AdditionalReturnScreenInput(),
        drug_insurance=DrugInsuranceInput(),
        refundable_credits=RefundableCreditInput(),
    )


def _sample_input() -> TaxReturnInput:
    return TaxReturnInput(
        tax_year=2025,
        province_dec31="QC",
        taxpayer=TaxpayerFacts(
            full_year_canada_resident=True,
            full_year_quebec_resident=True,
            province_dec31="QC",
            age_dec31=24,
            marital_status="single",
            dependant_count=0,
            deceased_return=False,
            bankruptcy_return=False,
            has_self_employment=False,
            has_capital_gains=False,
            has_rental_income=False,
            has_foreign_income_or_tax=False,
            has_foreign_property_over_100k=False,
            has_crypto_transactions=False,
            has_pension_or_benefit_income=False,
            has_indian_act_exempt_income=False,
            has_disability_or_caregiver_claim=False,
            has_employment_expenses=False,
            has_medical_expenses=False,
            has_donations=False,
            has_childcare_expenses=False,
            has_moving_expenses=False,
            has_tips_or_other_employment_income=False,
            has_student_loan_interest=False,
            received_qpp_disability_pension=False,
            made_qpp_cpt30_election=False,
            was_full_time_student_more_than_13_weeks=True,
        ),
        slips=[
            SlipInput(
                slip_type="T4",
                document_id="sample-t4-northern-lab",
                issuer_id="Northern Lab Coop",
                tax_year=2025,
                province_of_employment="QC",
                cpp_qpp_exempt=False,
                ei_exempt=False,
                ppip_exempt=False,
                confirmed=True,
                fields={
                    "14": Decimal("50000.00"),
                    "17": Decimal("2976.00"),
                    "17A": Decimal("0.00"),
                    "18": Decimal("655.00"),
                    "20": Decimal("0.00"),
                    "22": Decimal("6000.00"),
                    "24": Decimal("50000.00"),
                    "26": Decimal("50000.00"),
                    "44": Decimal("0.00"),
                    "52": Decimal("0.00"),
                    "55": Decimal("247.00"),
                },
            ),
            SlipInput(
                slip_type="RL1",
                document_id="sample-rl1-northern-lab",
                issuer_id="Northern Lab Coop",
                tax_year=2025,
                province_of_employment="QC",
                confirmed=True,
                fields={
                    "A": Decimal("50000.00"),
                    "B.A": Decimal("2976.00"),
                    "B.B": Decimal("0.00"),
                    "C": Decimal("655.00"),
                    "D": Decimal("0.00"),
                    "E": Decimal("5000.00"),
                    "F": Decimal("0.00"),
                    "G": Decimal("50000.00"),
                    "H": Decimal("247.00"),
                    "I": Decimal("50000.00"),
                    "211": Decimal("0.00"),
                },
            ),
            SlipInput(
                slip_type="T2202",
                document_id="sample-t2202-city-college",
                issuer_id="City College",
                tax_year=2025,
                confirmed=True,
                fields={
                    "24": Decimal("0.00"),
                    "25": Decimal("8.00"),
                    "26": Decimal("4200.00"),
                },
            ),
        ],
        inventory=DocumentInventory(
            income_sources_reviewed=True,
            deductions_reviewed=True,
            credits_reviewed=True,
            cra_records_reviewed=True,
            revenu_quebec_records_reviewed=True,
            no_income_sources=False,
        ),
        federal_tuition=FederalTuitionInput(
            has_current_tuition=True,
            has_prior_unused=False,
            wants_transfer=False,
            wants_canada_training_credit=False,
            t2202_eligible_fees=Decimal("4200.00"),
        ),
        quebec_tuition=QuebecTuitionInput(
            has_current_tuition=True,
            institution_outside_quebec=False,
            has_prior_unused=False,
            wants_transfer=False,
            eligible_tuition_or_exam_receipts=Decimal("4200.00"),
        ),
        rrsp=RrspInput(
            has_contributions=False,
            has_prior_unused_contributions=False,
            has_hbp_or_llp_activity=False,
        ),
        instalments=InstalmentInput(
            federal_reviewed=True,
            federal_paid=Decimal("0.00"),
            quebec_reviewed=True,
            quebec_paid=Decimal("0.00"),
        ),
        quebec_schedule_b=QuebecScheduleBInput(
            living_alone_reviewed=True,
            eligible_for_living_alone_amount=False,
        ),
        student_loan_interest=StudentLoanInterestInput(
            reviewed=True,
            qualifying_government_loans_confirmed=True,
            federal_current_year_paid=Decimal("0.00"),
            federal_unused_2020=Decimal("0.00"),
            federal_unused_2021=Decimal("0.00"),
            federal_unused_2022=Decimal("0.00"),
            federal_unused_2023=Decimal("0.00"),
            federal_unused_2024=Decimal("0.00"),
            federal_claim_amount=Decimal("0.00"),
            quebec_prior_unused=Decimal("0.00"),
            quebec_current_year_paid=Decimal("0.00"),
            quebec_claim_amount=Decimal("0.00"),
        ),
        scholarships=ScholarshipInput(reviewed=True, awards=[], part_time_programs=[]),
        resp_eap=RespEapInput(
            reviewed=True,
            has_other_resp_payments=False,
            qesi_cumulative_amount_over_3600=False,
            payments=[],
        ),
        additional_return_screens=AdditionalReturnScreenInput(
            immigrated_or_emigrated_2025=False,
            quebec_trust_return=False,
            separate_post_death_return=False,
            quebec_enterprise_registration_or_annual_fee=False,
        ),
        drug_insurance=DrugInsuranceInput(
            reviewed=True,
            group_plan_months=set(),
            eligible_student_months=set(range(1, 13)),
            other_exemption_applies=False,
        ),
        refundable_credits=RefundableCreditInput(
            work_premium_answers_reviewed=True,
            solidarity_answers_reviewed=True,
            canada_workers_benefit_answers_reviewed=True,
            rl19_advance_payments_reviewed=True,
            rl19_box_a=Decimal("0.00"),
            rl19_box_b=Decimal("0.00"),
            rl19_has_other_advance_boxes=False,
            cwb_incarcerated_90_days=False,
            cwb_foreign_officer_exempt=False,
            advanced_cwb_paid=Decimal("0.00"),
            advanced_cwb_disability_paid=Decimal("0.00"),
            work_premium_eligible_status=True,
            quebec_work_premium_full_time_student=True,
            transferred_schedule_s_amount=False,
            family_allowance_received_for_self=False,
            turned_18_before_december=True,
            designated_as_dependent_child=False,
            incarcerated_over_183_days=False,
            adapted_work_premium_eligible=False,
            work_premium_supplement_months=0,
            request_tax_shield=False,
            wants_solidarity_credit=False,
        ),
    )


def _dump_model(model) -> dict:
    return model.model_dump(mode="json")


def _source_payload() -> dict:
    return {source_id: _dump_model(source) for source_id, source in SOURCES.items()}


def _ruleset_hash() -> str:
    raw = json.dumps(_source_payload(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _input_digest(data: TaxReturnInput) -> str:
    raw = data.model_dump_json(exclude_none=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    raw = host.split(",", 1)[0].strip().lower()
    if raw.startswith("[") and "]" in raw:
        parsed = raw[1 : raw.index("]")]
    else:
        parsed = raw.rsplit(":", 1)[0] if ":" in raw else raw
    return parsed in _LOOPBACK_HOSTS


def _is_loopback_url(value: str | None) -> bool:
    if not value:
        return True
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and (parsed.hostname or "").lower() in _LOOPBACK_HOSTS


def _check_browser_boundary(request: Request) -> None:
    if not _is_loopback_host(request.headers.get("host")):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "host_not_loopback",
                "message": "The local tax app accepts API calls only on localhost.",
            },
        )
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "cross_origin_blocked",
                "message": "Cross-site browser requests are not accepted.",
            },
        )
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    if not _is_loopback_url(origin) or (origin is None and not _is_loopback_url(referer)):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "cross_origin_blocked",
                "message": "Only same-machine browser requests can calculate a return.",
            },
        )


async def _read_json_body(request: Request) -> dict:
    content_type = request.headers.get("content-type", "")
    if content_type and "application/json" not in content_type:
        raise HTTPException(
            status_code=415,
            detail={"code": "unsupported_media_type", "message": "Send JSON only."},
        )
    content_length = request.headers.get("content-length")
    try:
        declared_length = int(content_length) if content_length else 0
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_content_length", "message": "Content-Length is invalid."},
        ) from None
    if declared_length > MAX_REQUEST_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "request_too_large",
                "message": "Input JSON is too large for the local workspace.",
            },
        )
    body = await request.body()
    if len(body) > MAX_REQUEST_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "request_too_large",
                "message": "Input JSON is too large for the local workspace.",
            },
        )
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_json", "message": "Request body is not valid UTF-8 JSON."},
        ) from None
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_schema", "message": "The calculation input must be a JSON object."},
        )
    return payload


def _schema_errors(exc: ValidationError) -> list[dict]:
    return [
        {"path": ".".join(str(part) for part in err["loc"]), "message": err["msg"]}
        for err in exc.errors()
    ]


def _decimalize_json_money(data: TaxReturnInput) -> TaxReturnInput:
    slips = []
    for slip in data.slips:
        fields = {}
        for box, value in slip.fields.items():
            if isinstance(value, str):
                try:
                    fields[box] = Decimal(value)
                    continue
                except InvalidOperation:
                    pass
            fields[box] = value
        slips.append(slip.model_copy(update={"fields": fields}))
    return data.model_copy(update={"slips": slips})


def _local_blockers(data: TaxReturnInput) -> list[CompletenessBlocker]:
    blockers: list[CompletenessBlocker] = []
    seen_document_ids: dict[str, int] = {}
    for index, slip in enumerate(data.slips):
        if slip.document_id in seen_document_ids:
            blockers.append(
                CompletenessBlocker(
                    code="duplicate_document_id",
                    message="Each imported or entered slip must have a unique document reference.",
                    input_paths=[
                        f"slips.{seen_document_ids[slip.document_id]}.document_id",
                        f"slips.{index}.document_id",
                    ],
                    source_ids=[],
                    resolution="Rename or remove the duplicate slip reference before calculating.",
                )
            )
        else:
            seen_document_ids[slip.document_id] = index
    return blockers


def _blocked_result(
    data: TaxReturnInput | None,
    blockers: list[CompletenessBlocker],
    *,
    warnings: list[str] | None = None,
) -> TaxReturnResult:
    return TaxReturnResult(
        status="blocked",
        coverage_profile_id=PROFILE_ID,
        ruleset_hash=_ruleset_hash(),
        blockers=blockers,
        warnings=warnings or [],
        input_digest=_input_digest(data) if data else None,
    )


def _engine_pending_result(data: TaxReturnInput) -> TaxReturnResult:
    return _blocked_result(
        data,
        [
            CompletenessBlocker(
                code="engine_pending",
                message="The federal and Quebec return calculator is not available in this checkout.",
                input_paths=[],
                source_ids=[],
                resolution="Install or merge the return calculator before calculating a complete return.",
            )
        ],
    )


def _calculate_return(data: TaxReturnInput) -> TaxReturnResult:
    try:
        engine = importlib.import_module("taxagent.returns.engine")
    except ModuleNotFoundError as exc:
        if exc.name == "taxagent.returns.engine":
            return _engine_pending_result(data)
        raise
    try:
        result = engine.calculate_return(data)
    except Exception:
        return _blocked_result(
            data,
            [
                CompletenessBlocker(
                    code="calculation_failed",
                    message="The return calculator could not complete this return.",
                    input_paths=[],
                    source_ids=[],
                    resolution="Review the input JSON and engine installation, then try again.",
                )
            ],
        )
    if not isinstance(result, TaxReturnResult):
        result = TaxReturnResult.model_validate(result)
    if result.input_digest is None:
        result = result.model_copy(update={"input_digest": _input_digest(data)})
    return result


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC / "local.html")


@app.get("/api/health")
def health() -> dict:
    engine_available = importlib.util.find_spec("taxagent.returns.engine") is not None
    return {
        "ok": True,
        "mode": "local_offline_no_submission",
        "assets": {
            "html": (_STATIC / "local.html").is_file(),
            "css": (_STATIC / "local.css").is_file(),
            "js": (_STATIC / "local.js").is_file(),
        },
        "sources": len(SOURCES),
        "engine_available": engine_available,
    }


@app.get("/api/schema")
def schema() -> dict:
    return {
        "schema_version": "2025-qc-v1",
        "tax_year": 2025,
        "province": "QC",
        "default_sample_loaded": False,
        "max_request_bytes": MAX_REQUEST_BYTES,
        "profile": {
            "id": PROFILE_ID,
            "label": "2025 Quebec full-year resident, single salaried student profile",
            "no_submission": True,
            "no_automatic_storage": True,
        },
        "blank_input": _dump_model(_blank_input()),
        "supported_slips": ["T4", "T4A", "RL1", "T5", "RL3", "T2202", "RRSP_RECEIPT", "RC210", "RL19"],
        "collection_links": [
            {
                "label": "CRA My Account tax slips",
                "url": "https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-individuals/account-individuals.html",
            },
            {
                "label": "Revenu Quebec My Account",
                "url": "https://www.revenuquebec.ca/en/online-services/online-services/online-services-for-citizens/my-account-for-citizens/",
            },
            {
                "label": "CRA certified tax software list",
                "url": "https://www.canada.ca/en/services/taxes/income-tax/personal-income-tax/how-file/tax-software/find-software.html",
            },
            {
                "label": "Revenu Quebec online filing options",
                "url": "https://www.revenuquebec.ca/en/citizens/income-tax-return/filing-your-income-tax-return/filing-your-income-tax-return-online/",
            },
        ],
        "sources": _source_payload(),
    }


@app.get("/api/sample")
def sample() -> dict:
    return {
        "sample_only": True,
        "label": "Sample supported 2025 Quebec salary/student fixture - not your data",
        "input": _dump_model(_sample_input()),
    }


@app.post("/api/calculate")
async def calculate(request: Request) -> dict:
    _check_browser_boundary(request)
    payload = await _read_json_body(request)
    try:
        data = _decimalize_json_money(TaxReturnInput.model_validate(payload))
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_schema",
                "message": "The input does not match TaxReturnInput.",
                "errors": _schema_errors(exc),
            },
        ) from None

    blockers = preflight(data) + _local_blockers(data)
    result = _blocked_result(data, blockers) if blockers else _calculate_return(data)
    source_ids = sorted(
        {source_id for blocker in result.blockers for source_id in blocker.source_ids}
        | {source_id for line in result.lines for source_id in line.source_ids}
    )
    return {
        "result": _dump_model(result),
        "sources": {
            source_id: _dump_model(SOURCES[source_id])
            for source_id in source_ids
            if source_id in SOURCES
        },
        "coverage": {
            "complete_return_allowed": result.status == "complete",
            "filing_submission": "not_supported",
        },
    }


app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

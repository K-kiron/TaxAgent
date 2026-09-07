"""Fail-closed eligibility and evidence gates for the 2025 Quebec ruleset."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .federal_2025_qc import _taxable_scholarships
from .models import CompletenessBlocker, TaxReturnInput


_COVERAGE_FACTS = (
    "full_year_canada_resident",
    "full_year_quebec_resident",
    "province_dec31",
    "age_dec31",
    "marital_status",
    "dependant_count",
    "deceased_return",
    "bankruptcy_return",
    "has_self_employment",
    "has_capital_gains",
    "has_rental_income",
    "has_foreign_income_or_tax",
    "has_foreign_property_over_100k",
    "has_crypto_transactions",
    "has_pension_or_benefit_income",
    "has_indian_act_exempt_income",
    "has_disability_or_caregiver_claim",
    "has_employment_expenses",
    "has_medical_expenses",
    "has_donations",
    "has_childcare_expenses",
    "has_moving_expenses",
    "has_tips_or_other_employment_income",
    "has_student_loan_interest",
    "received_qpp_disability_pension",
    "made_qpp_cpt30_election",
    "was_full_time_student_more_than_13_weeks",
)

_UNSUPPORTED_FACTS = (
    "deceased_return",
    "bankruptcy_return",
    "has_self_employment",
    "has_capital_gains",
    "has_rental_income",
    "has_foreign_income_or_tax",
    "has_foreign_property_over_100k",
    "has_crypto_transactions",
    "has_pension_or_benefit_income",
    "has_indian_act_exempt_income",
    "has_disability_or_caregiver_claim",
    "has_employment_expenses",
    "has_medical_expenses",
    "has_donations",
    "has_childcare_expenses",
    "has_moving_expenses",
    "has_tips_or_other_employment_income",
)

_INVENTORY_REVIEWS = (
    "income_sources_reviewed",
    "deductions_reviewed",
    "credits_reviewed",
    "cra_records_reviewed",
    "revenu_quebec_records_reviewed",
)

_SUPPORTED_SLIPS = {"T4", "T4A", "RL1", "T5", "RL3", "T2202", "RRSP_RECEIPT", "RC210", "RL19"}
_ALLOWED_BOXES = {
    "T4": {"14", "17", "17A", "18", "20", "22", "24", "26", "44", "52", "55"},
    "T4A": {"22", "040", "042", "105"},
    "RL1": {"A", "B.A", "B.B", "C", "D", "E", "F", "G", "H", "I", "O", "211"},
    "T5": {"13"},
    "RL3": {"D"},
    "T2202": {"24", "25", "26"},
    "RRSP_RECEIPT": {"amount"},
    "RC210": {"10", "11"},
    "RL19": {"A", "B", "C", "D", "G", "H"},
}
_REQUIRED_MONEY_BOXES = {
    "T4": {"14"},
    "T4A": set(),
    "RL1": set(),
    "T5": {"13"},
    "RL3": {"D"},
    "T2202": {"24", "25", "26"},
    "RRSP_RECEIPT": {"amount"},
    "RC210": set(),
    "RL19": set(),
}


def _blocker(
    code: str,
    message: str,
    *input_paths: str,
    source_ids: tuple[str, ...] = (),
    resolution: str = "Complete or correct the identified return facts.",
) -> CompletenessBlocker:
    return CompletenessBlocker(
        code=code,
        message=message,
        input_paths=list(input_paths),
        source_ids=list(source_ids),
        resolution=resolution,
    )


def _schedule_b_blockers(data: TaxReturnInput) -> list[CompletenessBlocker]:
    schedule_b = data.quebec_schedule_b
    missing = [
        f"quebec_schedule_b.{name}"
        for name in ("living_alone_reviewed", "eligible_for_living_alone_amount")
        if getattr(schedule_b, name) is None
        or (name == "living_alone_reviewed" and getattr(schedule_b, name) is not True)
    ]
    if not missing:
        return []
    return [
        _blocker(
            "missing_schedule_b_answers",
            "The Schedule B living-arrangement questions must be reviewed and answered.",
            *missing,
            source_ids=("rq_2025_schedule_b",),
        )
    ]


def _student_loan_interest_blockers(data: TaxReturnInput) -> list[CompletenessBlocker]:
    interest = data.student_loan_interest
    amount_fields = (
        "federal_current_year_paid",
        "federal_unused_2020",
        "federal_unused_2021",
        "federal_unused_2022",
        "federal_unused_2023",
        "federal_unused_2024",
        "federal_claim_amount",
        "quebec_prior_unused",
        "quebec_current_year_paid",
        "quebec_claim_amount",
    )
    missing = [
        f"student_loan_interest.{name}"
        for name in ("reviewed", "qualifying_government_loans_confirmed", *amount_fields)
        if getattr(interest, name) is None
        or (name == "reviewed" and getattr(interest, name) is not True)
    ]
    if missing:
        return [
            _blocker(
                "missing_student_loan_interest_answers",
                "Student-loan interest and prior unused amounts must be reviewed and entered, including zero.",
                *missing,
                source_ids=("cra_2025_line_31900", "rq_2025_schedule_m"),
            )
        ]

    amounts = [getattr(interest, name) for name in amount_fields]
    assert all(isinstance(amount, Decimal) for amount in amounts)
    has_amount = any(amount > 0 for amount in amounts)
    blockers: list[CompletenessBlocker] = []
    if interest.qualifying_government_loans_confirmed is not True and (
        data.taxpayer.has_student_loan_interest is True or has_amount
    ):
        blockers.append(
            _blocker(
                "ineligible_student_loan_interest",
                "Only interest on a qualifying government student loan is supported.",
                "student_loan_interest.qualifying_government_loans_confirmed",
                source_ids=("cra_2025_line_31900", "rq_2025_schedule_m"),
            )
        )
    if data.taxpayer.has_student_loan_interest is False and has_amount:
        blockers.append(
            _blocker(
                "contradictory_student_loan_interest",
                "Student-loan interest amounts were entered after declaring that none applies.",
                "taxpayer.has_student_loan_interest",
                "student_loan_interest",
            )
        )
    if data.taxpayer.has_student_loan_interest is True and not has_amount:
        blockers.append(
            _blocker(
                "missing_student_loan_interest_amount",
                "Student-loan interest was declared but no current or unused amount was entered.",
                "student_loan_interest",
            )
        )

    federal_available = sum(
        (getattr(interest, name) for name in amount_fields[:6]), start=Decimal("0")
    )
    quebec_available = interest.quebec_prior_unused + interest.quebec_current_year_paid
    if (
        interest.federal_claim_amount > federal_available
        or interest.quebec_claim_amount > quebec_available
    ):
        blockers.append(
            _blocker(
                "student_loan_interest_claim_exceeds_available",
                "A student-loan interest claim exceeds the evidenced amount available.",
                "student_loan_interest.federal_claim_amount",
                "student_loan_interest.quebec_claim_amount",
                source_ids=("cra_2025_line_31900", "rq_2025_schedule_m"),
            )
        )
    if interest.federal_current_year_paid != interest.quebec_current_year_paid:
        blockers.append(
            _blocker(
                "student_loan_current_interest_mismatch",
                "The federal and Quebec current-year qualifying interest amounts do not match.",
                "student_loan_interest.federal_current_year_paid",
                "student_loan_interest.quebec_current_year_paid",
            )
        )
    return blockers


def _scholarship_blockers(data: TaxReturnInput) -> list[CompletenessBlocker]:
    scholarships = data.scholarships
    if (
        scholarships.reviewed is not True
        or scholarships.awards is None
        or scholarships.part_time_programs is None
    ):
        return [
            _blocker(
                "missing_scholarship_answers",
                "Scholarship receipts and exemption facts must be reviewed explicitly.",
                "scholarships.reviewed",
                "scholarships.awards",
                "scholarships.part_time_programs",
                source_ids=("cra_2025_p105", "cra_2025_line_13010"),
            )
        ]

    blockers: list[CompletenessBlocker] = []
    supported_by_issuer: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for index, award in enumerate(scholarships.awards):
        path = f"scholarships.awards.{index}"
        missing = [
            f"{path}.{name}"
            for name in (
                "amount",
                "category",
                "qualifying_student",
                "attendance",
                "intended_enrolment_support",
            )
            if getattr(award, name) is None
        ]
        if missing:
            blockers.append(
                _blocker(
                    "missing_scholarship_award_facts",
                    "Each award needs its amount, type, study status, and supported costs.",
                    *missing,
                    source_ids=("cra_2025_p105", "cra_2025_line_13010"),
                )
            )
            continue
        if award.category != "ordinary_postsecondary":
            blockers.append(
                _blocker(
                    "unsupported_scholarship_category",
                    "This award category has a different income or exemption calculation.",
                    f"{path}.category",
                    source_ids=("cra_2025_line_13010",),
                )
            )
            continue
        assert award.amount is not None
        assert award.intended_enrolment_support is not None
        if award.intended_enrolment_support > award.amount:
            blockers.append(
                _blocker(
                    "scholarship_support_exceeds_award",
                    "The portion intended to support enrolment cannot exceed the award.",
                    f"{path}.intended_enrolment_support",
                    f"{path}.amount",
                    source_ids=("cra_2025_line_13010",),
                )
            )
        if (award.qualifying_student is True) != (award.attendance != "nonqualifying"):
            blockers.append(
                _blocker(
                    "inconsistent_scholarship_student_status",
                    "Qualifying-student status and the reported attendance category disagree.",
                    f"{path}.qualifying_student",
                    f"{path}.attendance",
                    source_ids=("cra_2025_p105",),
                )
            )
        if award.attendance == "part_time" and not award.part_time_program_id:
            blockers.append(
                _blocker(
                    "missing_scholarship_part_time_program",
                    "Each part-time award must identify the program whose eligible costs limit the exemption.",
                    f"{path}.part_time_program_id",
                    source_ids=("cra_2025_line_13010",),
                )
            )
        supported_by_issuer[award.issuer_id] += award.amount

    programs_by_id = {
        program.program_id: program for program in scholarships.part_time_programs
    }
    if len(programs_by_id) != len(scholarships.part_time_programs):
        blockers.append(
            _blocker(
                "duplicate_scholarship_part_time_program",
                "Each part-time program cost pool must have a unique identifier.",
                "scholarships.part_time_programs",
                source_ids=("cra_2025_line_13010",),
            )
        )
    for index, program in enumerate(scholarships.part_time_programs):
        if program.eligible_tuition_and_required_materials is None:
            blockers.append(
                _blocker(
                    "missing_scholarship_part_time_program_cost",
                    "Each part-time program requires its total unused eligible tuition and material costs.",
                    f"scholarships.part_time_programs.{index}.eligible_tuition_and_required_materials",
                    source_ids=("cra_2025_line_13010",),
                )
            )
    referenced_program_ids = {
        award.part_time_program_id
        for award in scholarships.awards
        if award.attendance == "part_time" and award.part_time_program_id
    }
    missing_program_ids = sorted(referenced_program_ids - programs_by_id.keys())
    if missing_program_ids:
        blockers.append(
            _blocker(
                "unknown_scholarship_part_time_program",
                "A part-time award references a program without an eligible-cost record.",
                "scholarships.awards",
                "scholarships.part_time_programs",
                source_ids=("cra_2025_line_13010",),
            )
        )

    t4a_by_issuer: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    rl1_by_issuer: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for slip in data.slips:
        if slip.slip_type == "T4A" and isinstance(slip.fields.get("105"), Decimal):
            t4a_by_issuer[slip.issuer_id] += slip.fields["105"]
        if slip.slip_type == "RL1" and slip.rl1_box_o_allocations:
            rl1_by_issuer[slip.issuer_id] += sum(
                (
                    amount
                    for code, amount in slip.rl1_box_o_allocations.items()
                    if code in {"RB", "RZ-RB"}
                ),
                start=Decimal("0"),
            )
    for issuer in set(supported_by_issuer) | set(t4a_by_issuer) | set(rl1_by_issuer):
        if not (
            supported_by_issuer[issuer]
            == t4a_by_issuer[issuer]
            == rl1_by_issuer[issuer]
        ):
            blockers.append(
                _blocker(
                    "scholarship_receipt_mismatch",
                    "Award facts must reconcile to T4A box 105 and RL-1 box O code RB by issuer.",
                    "scholarships.awards",
                    "slips",
                    source_ids=("cra_2025_p105", "rq_2025_line_154_scholarship"),
                )
            )
    return blockers


def _resp_eap_blockers(data: TaxReturnInput) -> list[CompletenessBlocker]:
    resp = data.resp_eap
    missing = [
        f"resp_eap.{name}"
        for name in (
            "reviewed",
            "has_other_resp_payments",
            "qesi_cumulative_amount_over_3600",
            "payments",
        )
        if getattr(resp, name) is None
        or (name == "reviewed" and getattr(resp, name) is not True)
    ]
    if missing:
        return [
            _blocker(
                "missing_resp_eap_answers",
                "RESP beneficiary payments and Quebec education savings incentive facts must be reviewed explicitly.",
                *missing,
                source_ids=("cra_2025_t4a", "rq_2025_line_154_resp"),
            )
        ]

    blockers: list[CompletenessBlocker] = []
    if resp.has_other_resp_payments is True:
        blockers.append(
            _blocker(
                "unsupported_resp_payment_type",
                "RESP payments other than beneficiary educational assistance payments require a different calculation.",
                "resp_eap.has_other_resp_payments",
                source_ids=("cra_2025_t4a",),
            )
        )
    if resp.qesi_cumulative_amount_over_3600 is True:
        blockers.append(
            _blocker(
                "unsupported_resp_qesi_special_tax",
                "RESP educational assistance payments above the cumulative QESI limit require the Quebec special-tax calculation.",
                "resp_eap.qesi_cumulative_amount_over_3600",
                source_ids=("rq_2025_line_154_resp",),
            )
        )

    payment_by_issuer: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for index, payment in enumerate(resp.payments or []):
        if payment.amount is None:
            blockers.append(
                _blocker(
                    "missing_resp_eap_payment_amount",
                    "Each RESP educational assistance payment requires its gross amount.",
                    f"resp_eap.payments.{index}.amount",
                    source_ids=("cra_2025_t4a",),
                )
            )
            continue
        payment_by_issuer[payment.issuer_id] += payment.amount

    t4a_by_issuer: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    rl1_by_issuer: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for slip in data.slips:
        if slip.slip_type == "T4A":
            if (
                isinstance(slip.fields.get("040"), Decimal)
                and slip.fields["040"] > Decimal("0")
            ):
                blockers.append(
                    _blocker(
                        "unsupported_resp_accumulated_income_payment",
                        "A T4A box 040 accumulated income payment requires federal special-tax screening.",
                        "slips",
                        source_ids=("cra_2025_t4a",),
                    )
                )
            if isinstance(slip.fields.get("042"), Decimal):
                t4a_by_issuer[slip.issuer_id] += slip.fields["042"]
        if slip.slip_type == "RL1" and slip.rl1_box_o_allocations:
            rl1_by_issuer[slip.issuer_id] += sum(
                (
                    amount
                    for code, amount in slip.rl1_box_o_allocations.items()
                    if code in {"RU", "RZ-RU"}
                ),
                start=Decimal("0"),
            )
    for issuer in set(payment_by_issuer) | set(t4a_by_issuer) | set(rl1_by_issuer):
        if not (
            payment_by_issuer[issuer]
            == t4a_by_issuer[issuer]
            == rl1_by_issuer[issuer]
        ):
            blockers.append(
                _blocker(
                    "resp_eap_receipt_mismatch",
                    "RESP payment facts must reconcile to T4A box 042 and RL-1 box O code RU by issuer.",
                    "resp_eap.payments",
                    "slips",
                    source_ids=("cra_2025_t4a", "rq_2025_line_154_resp"),
                )
            )
    return blockers


def _additional_return_screen_blockers(data: TaxReturnInput) -> list[CompletenessBlocker]:
    screens = data.additional_return_screens
    names = (
        "immigrated_or_emigrated_2025",
        "quebec_trust_return",
        "separate_post_death_return",
        "quebec_enterprise_registration_or_annual_fee",
    )
    missing = [
        f"additional_return_screens.{name}"
        for name in names
        if getattr(screens, name) is None
    ]
    blockers: list[CompletenessBlocker] = []
    if missing:
        blockers.append(
            _blocker(
                "missing_additional_return_screens",
                "Every additional T1 and TP-1 filing situation must be answered explicitly.",
                *missing,
                source_ids=("cra_2025_5005_r", "rq_2025_tp1"),
            )
        )
    for name in names:
        if getattr(screens, name) is True:
            blockers.append(
                _blocker(
                    f"unsupported_{name}",
                    "This filing situation requires return lines outside the supported salary-and-student profile.",
                    f"additional_return_screens.{name}",
                    source_ids=("cra_2025_5005_r", "rq_2025_tp1"),
                )
            )
    return blockers


def preflight(data: TaxReturnInput) -> list[CompletenessBlocker]:
    """Return every known blocker; an empty list means calculation may start."""

    blockers: list[CompletenessBlocker] = []
    facts = data.taxpayer

    missing_facts = [
        f"taxpayer.{name}" for name in _COVERAGE_FACTS if getattr(facts, name) is None
    ]
    if missing_facts:
        blockers.append(
            _blocker(
                "missing_coverage_answer",
                "Every coverage question must be answered explicitly.",
                *missing_facts,
                resolution="Answer each unanswered coverage question.",
            )
        )

    if data.tax_year != 2025:
        blockers.append(
            _blocker(
                "unsupported_tax_year",
                "This ruleset calculates only 2025 returns.",
                "tax_year",
                resolution="Use tax year 2025 or a ruleset for the requested year.",
            )
        )
    if data.province_dec31 != "QC" or (
        facts.province_dec31 is not None and facts.province_dec31 != "QC"
    ):
        blockers.append(
            _blocker(
                "unsupported_province",
                "This release covers Quebec residents only.",
                "province_dec31",
                "taxpayer.province_dec31",
            )
        )
    if facts.full_year_canada_resident is False or facts.full_year_quebec_resident is False:
        blockers.append(
            _blocker(
                "unsupported_residency",
                "Part-year or non-resident returns are outside this ruleset.",
                "taxpayer.full_year_canada_resident",
                "taxpayer.full_year_quebec_resident",
            )
        )
    if (
        (facts.age_dec31 is not None and not 18 <= facts.age_dec31 <= 64)
        or (facts.marital_status is not None and facts.marital_status != "single")
        or (facts.dependant_count is not None and facts.dependant_count != 0)
    ):
        blockers.append(
            _blocker(
                "unsupported_family_status",
                "The covered persona is age 18 to 64, single, and has no dependants.",
                "taxpayer.age_dec31",
                "taxpayer.marital_status",
                "taxpayer.dependant_count",
            )
        )

    if (
        facts.age_dec31 == 18
        or facts.received_qpp_disability_pension is True
        or facts.made_qpp_cpt30_election is True
    ):
        blockers.append(
            _blocker(
                "unsupported_qpp_contributory_period",
                "Schedule 8 requires a prorated QPP contributory period for this return.",
                "taxpayer.age_dec31",
                "taxpayer.received_qpp_disability_pension",
                "taxpayer.made_qpp_cpt30_election",
                source_ids=("cra_2025_schedule_8_qc",),
                resolution="Use authorized tax software for a nonstandard QPP contributory period.",
            )
        )

    unsupported = [
        f"taxpayer.{name}" for name in _UNSUPPORTED_FACTS if getattr(facts, name) is True
    ]
    if unsupported:
        blockers.append(
            _blocker(
                "unsupported_situation",
                "One or more selected tax situations require forms outside this ruleset.",
                *unsupported,
                resolution="Use certified tax software or a preparer for this return.",
            )
        )

    missing_reviews = [
        f"inventory.{name}"
        for name in _INVENTORY_REVIEWS
        if getattr(data.inventory, name) is not True
    ]
    if data.inventory.no_income_sources is None:
        missing_reviews.append("inventory.no_income_sources")
    if missing_reviews:
        blockers.append(
            _blocker(
                "missing_document_inventory",
                "The income, deduction, credit, CRA, and Revenu Quebec inventories must be confirmed.",
                *missing_reviews,
                resolution="Review each inventory and explicitly confirm its status.",
            )
        )
    income_slips = [slip for slip in data.slips if slip.slip_type in {"T4", "T4A", "RL1", "T5", "RL3"}]
    if data.inventory.no_income_sources is True and income_slips:
        blockers.append(
            _blocker(
                "contradictory_income_inventory",
                "The return includes slips but also says there are no income sources.",
                "inventory.no_income_sources",
                "slips",
            )
        )
    if data.inventory.no_income_sources is False and not income_slips:
        blockers.append(
            _blocker(
                "missing_income_slips",
                "Income sources were declared but no slips were supplied.",
                "slips",
            )
        )

    slips_by_type_and_issuer: dict[tuple[str, str], int] = defaultdict(int)
    for index, slip in enumerate(data.slips):
        path = f"slips.{index}"
        slips_by_type_and_issuer[(slip.slip_type, slip.issuer_id)] += 1
        if slip.slip_type not in _SUPPORTED_SLIPS:
            blockers.append(
                _blocker(
                    "unsupported_slip",
                    f"Slip type {slip.slip_type!r} is outside this ruleset.",
                    f"{path}.slip_type",
                )
            )
        if slip.tax_year != 2025:
            blockers.append(
                _blocker(
                    "wrong_slip_year",
                    "Every slip must be for tax year 2025.",
                    f"{path}.tax_year",
                )
            )
        if slip.confirmed is not True:
            blockers.append(
                _blocker(
                    "unconfirmed_slip",
                    "Every imported or entered slip must be confirmed by the user.",
                    f"{path}.confirmed",
                )
            )
        if slip.slip_type == "T4":
            missing_exemptions = [
                f"{path}.{name}"
                for name in ("cpp_qpp_exempt", "ei_exempt", "ppip_exempt")
                if getattr(slip, name) is None
            ]
            if missing_exemptions:
                blockers.append(
                    _blocker(
                        "missing_t4_exemption_answer",
                        "Each T4 box 28 exemption indicator must be entered explicitly.",
                        *missing_exemptions,
                        source_ids=("cra_2025_schedule_8_qc", "cra_2025_t2204"),
                    )
                )
        if slip.slip_type == "RRSP_RECEIPT" and slip.rrsp_period is None:
            blockers.append(
                _blocker(
                    "missing_rrsp_receipt_period",
                    "Each RRSP receipt must identify its Schedule 7 contribution period.",
                    f"{path}.rrsp_period",
                )
            )
        if slip.slip_type == "RL1" and "O" in slip.fields:
            if slip.rl1_box_o_allocations is None:
                blockers.append(
                    _blocker(
                        "missing_rl1_box_o_allocations",
                        "RL-1 box O requires an explicit allocation by other-information code.",
                        f"{path}.rl1_box_o_allocations",
                    )
                )
            elif sum(slip.rl1_box_o_allocations.values(), start=Decimal("0")) != slip.fields["O"]:
                blockers.append(
                    _blocker(
                        "rl1_box_o_allocation_mismatch",
                        "RL-1 box O code allocations must add to the box O total.",
                        f"{path}.fields.O",
                        f"{path}.rl1_box_o_allocations",
                    )
                )
            elif unsupported_codes := sorted(
                set(slip.rl1_box_o_allocations) - {"RB", "RZ-RB", "RU", "RZ-RU"}
            ):
                blockers.append(
                    _blocker(
                        "unsupported_rl1_box_o_code",
                        f"RL-1 box O contains unsupported codes: {', '.join(unsupported_codes)}.",
                        f"{path}.rl1_box_o_allocations",
                        source_ids=("rq_2025_line_154_scholarship", "rq_2025_line_154_resp"),
                    )
                )
        if slip.slip_type == "RL1" and any(
            box in slip.fields for box in {"A", "B.A", "B.B", "C", "D", "F", "G", "H", "I", "211"}
        ) and "A" not in slip.fields:
            blockers.append(
                _blocker(
                    "missing_slip_box",
                    f"Slip {slip.document_id!r} is missing required monetary box A.",
                    f"{path}.fields.A",
                )
            )
        missing_boxes = sorted(_REQUIRED_MONEY_BOXES.get(slip.slip_type, set()) - slip.fields.keys())
        if missing_boxes:
            blockers.append(
                _blocker(
                    "missing_slip_box",
                    f"Slip {slip.document_id!r} is missing required monetary boxes: {', '.join(missing_boxes)}.",
                    *[f"{path}.fields.{box}" for box in missing_boxes],
                    resolution="Enter every required box explicitly, including printed zero amounts.",
                )
            )
        invalid_money_boxes = sorted(
            box
            for box in (_ALLOWED_BOXES.get(slip.slip_type, set()) & slip.fields.keys())
            if not isinstance(slip.fields[box], Decimal)
        )
        if invalid_money_boxes:
            blockers.append(
                _blocker(
                    "invalid_slip_box_type",
                    f"Slip {slip.document_id!r} has non-numeric monetary boxes: {', '.join(invalid_money_boxes)}.",
                    *[f"{path}.fields.{box}" for box in invalid_money_boxes],
                    resolution="Enter these boxes as monetary amounts.",
                )
            )
        unsupported_boxes = sorted(slip.fields.keys() - _ALLOWED_BOXES.get(slip.slip_type, set()))
        if unsupported_boxes:
            blockers.append(
                _blocker(
                    "unsupported_slip_box",
                    f"Slip {slip.document_id!r} contains boxes outside the supported amount map: {', '.join(unsupported_boxes)}.",
                    *[f"{path}.fields.{box}" for box in unsupported_boxes],
                    resolution="Import only the documented monetary boxes; never place identifiers in slip amount fields.",
                )
            )
        if slip.slip_type == "T4" and slip.province_of_employment != "QC":
            blockers.append(
                _blocker(
                    "outside_quebec_employment",
                    "Employment outside Quebec requires federal Schedule 10 or RC381.",
                    f"{path}.province_of_employment",
                source_ids=("cra_2025_schedule_10_qc",),
                )
            )

    for left, right in (("T5", "RL3"),):
        issuers = {
            issuer for slip_type, issuer in slips_by_type_and_issuer if slip_type in {left, right}
        }
        for issuer in issuers:
            if not (
                slips_by_type_and_issuer[(left, issuer)]
                and slips_by_type_and_issuer[(right, issuer)]
            ):
                blockers.append(
                    _blocker(
                        "missing_slip_counterpart",
                        f"Issuer {issuer!r} requires both {left} and {right} slips.",
                        "slips",
                    )
                )

    t4_issuers = {slip.issuer_id for slip in data.slips if slip.slip_type == "T4"}
    employment_rl1_issuers = {
        slip.issuer_id
        for slip in data.slips
        if slip.slip_type == "RL1" and "A" in slip.fields
    }
    if t4_issuers != employment_rl1_issuers:
        blockers.append(
            _blocker(
                "missing_slip_counterpart",
                "Each employment issuer requires both a T4 and an employment RL-1 slip.",
                "slips",
            )
        )

    blockers.extend(_rrsp_blockers(data))
    blockers.extend(_tuition_blockers(data))
    blockers.extend(_advance_payment_blockers(data))
    blockers.extend(_schedule_b_blockers(data))
    blockers.extend(_student_loan_interest_blockers(data))
    blockers.extend(_scholarship_blockers(data))
    blockers.extend(_resp_eap_blockers(data))
    blockers.extend(_additional_return_screen_blockers(data))

    missing_instalments = [
        f"instalments.{name}"
        for name in ("federal_reviewed", "federal_paid", "quebec_reviewed", "quebec_paid")
        if getattr(data.instalments, name) is None
        or (name.endswith("reviewed") and getattr(data.instalments, name) is not True)
    ]
    if missing_instalments:
        blockers.append(
            _blocker(
                "missing_instalment_answers",
                "Federal and Quebec instalment payments must be reviewed and entered, including zero.",
                *missing_instalments,
                source_ids=("cra_2025_5005_r", "rq_2025_tp1"),
            )
        )

    supported_gross_income = _taxable_scholarships(data) + sum(
        (
            value
            for slip in data.slips
            for box, value in slip.fields.items()
            if isinstance(value, Decimal)
            and (
                (slip.slip_type == "T4" and box == "14")
                or (slip.slip_type == "T5" and box == "13")
                or (slip.slip_type == "T4A" and box == "042")
            )
        ),
        start=Decimal("0"),
    )
    if supported_gross_income > Decimal("177882"):
        blockers.append(
            _blocker(
                "alternative_minimum_tax_screen",
                "Income exceeds the 2025 alternative minimum tax basic exemption and requires Form T691.",
                "slips",
                source_ids=("cra_2025_t691",),
                resolution="Use authorized tax software to calculate alternative minimum tax.",
            )
        )

    missing_drug = [
        f"drug_insurance.{name}"
        for name in (
            "reviewed",
            "group_plan_months",
            "eligible_student_months",
            "other_exemption_applies",
        )
        if getattr(data.drug_insurance, name) is None
    ]
    if data.drug_insurance.group_plan_months and data.drug_insurance.group_plan_source is None:
        missing_drug.append("drug_insurance.group_plan_source")
    if missing_drug or data.drug_insurance.reviewed is not True:
        blockers.append(
            _blocker(
                "missing_drug_insurance_answers",
                "Quebec prescription drug insurance facts must be reviewed.",
                *(missing_drug or ["drug_insurance.reviewed"]),
                source_ids=("rq_2025_schedule_k",),
            )
        )
    missing_refundable = [
        f"refundable_credits.{name}"
        for name in (
            "work_premium_answers_reviewed",
            "solidarity_answers_reviewed",
            "canada_workers_benefit_answers_reviewed",
            "rl19_advance_payments_reviewed",
            "rl19_box_a",
            "rl19_box_b",
            "rl19_has_other_advance_boxes",
            "cwb_incarcerated_90_days",
            "cwb_foreign_officer_exempt",
            "advanced_cwb_paid",
            "advanced_cwb_disability_paid",
            "work_premium_eligible_status",
            "quebec_work_premium_full_time_student",
            "transferred_schedule_s_amount",
            "family_allowance_received_for_self",
            "turned_18_before_december",
            "designated_as_dependent_child",
            "incarcerated_over_183_days",
            "adapted_work_premium_eligible",
            "work_premium_supplement_months",
            "request_tax_shield",
            "wants_solidarity_credit",
        )
        if (
            getattr(data.refundable_credits, name) is None
            or (name.endswith("answers_reviewed") and getattr(data.refundable_credits, name) is not True)
        )
    ]
    if missing_refundable:
        blockers.append(
            _blocker(
                "missing_refundable_credit_answers",
                "Refundable-credit eligibility must be reviewed before calculation.",
                *missing_refundable,
            )
        )

    if data.refundable_credits.rl19_has_other_advance_boxes is True:
        blockers.append(
            _blocker(
                "unsupported_rl19_advance_boxes",
                "RL-19 advance-payment boxes other than A and B require credits outside this ruleset.",
                "refundable_credits.rl19_has_other_advance_boxes",
                source_ids=("rq_2025_tp1_guide",),
                resolution="Use authorized software to report the other RL-19 advance payments.",
            )
        )

    if data.refundable_credits.request_tax_shield is True:
        blockers.append(
            _blocker(
                "unsupported_tax_shield",
                "The Quebec tax shield calculation is outside this ruleset.",
                "refundable_credits.request_tax_shield",
                source_ids=("rq_2025_schedule_p",),
            )
        )
    if data.refundable_credits.adapted_work_premium_eligible is True:
        blockers.append(
            _blocker(
                "unsupported_adapted_work_premium",
                "The adapted work premium is outside this ruleset.",
                "refundable_credits.adapted_work_premium_eligible",
                source_ids=("rq_2025_schedule_p",),
            )
        )
    if (data.refundable_credits.work_premium_supplement_months or 0) > 0:
        blockers.append(
            _blocker(
                "unsupported_work_premium_supplement",
                "The supplement to the work premium requires RL-5 transition facts.",
                "refundable_credits.work_premium_supplement_months",
                source_ids=("rq_2025_schedule_p",),
            )
        )

    if data.refundable_credits.wants_solidarity_credit is True:
        solidarity_fields = (
            "solidarity_eligible_immigration_status",
            "solidarity_refugee_claimant_dec31",
            "solidarity_family_allowance_paid_for_user_december",
            "solidarity_turned_18_in_december",
            "solidarity_lived_alone_all_year",
            "solidarity_address_same_as_return",
            "solidarity_occupancy",
        )
        missing_solidarity = [
            f"refundable_credits.{name}"
            for name in solidarity_fields
            if getattr(data.refundable_credits, name) is None
        ]
        if missing_solidarity:
            blockers.append(
                _blocker(
                    "missing_solidarity_answers",
                    "Schedule D eligibility and housing facts are incomplete.",
                    *missing_solidarity,
                    source_ids=("rq_2025_schedule_d",),
                )
            )
        if data.refundable_credits.solidarity_address_same_as_return is False:
            blockers.append(
                _blocker(
                    "unsupported_solidarity_different_address",
                    "Schedule D needs address lines 14 to 16 when the dwelling address differs.",
                    "refundable_credits.solidarity_address_same_as_return",
                    source_ids=("rq_2025_schedule_d",),
                )
            )
        if (
            data.refundable_credits.solidarity_occupancy == "owner"
            and data.refundable_credits.solidarity_owner_has_municipal_tax_bill is None
        ):
            blockers.append(
                _blocker(
                    "missing_solidarity_owner_tax_bill_status",
                    "An owner must confirm whether the dwelling has a municipal tax bill.",
                    "refundable_credits.solidarity_owner_has_municipal_tax_bill",
                    source_ids=("rq_2025_schedule_d",),
                )
            )

    return blockers


def _rrsp_blockers(data: TaxReturnInput) -> list[CompletenessBlocker]:
    rrsp = data.rrsp
    blockers: list[CompletenessBlocker] = []
    if (
        rrsp.has_contributions is None
        or rrsp.has_prior_unused_contributions is None
        or rrsp.has_hbp_or_llp_activity is None
    ):
        blockers.append(
            _blocker(
                "missing_rrsp_answers",
                "RRSP contribution and HBP/LLP questions must be answered.",
                "rrsp.has_contributions",
                "rrsp.has_prior_unused_contributions",
                "rrsp.has_hbp_or_llp_activity",
            )
        )
    if rrsp.has_hbp_or_llp_activity is True:
        blockers.append(
            _blocker(
                "unsupported_hbp_llp",
                "Home Buyers' Plan and Lifelong Learning Plan activity is outside this ruleset.",
                "rrsp.has_hbp_or_llp_activity",
            )
        )
    if rrsp.has_contributions is True:
        if rrsp.contribution_receipts is None:
            blockers.append(
                _blocker(
                    "missing_rrsp_receipts",
                    "RRSP receipts are required for a contribution claim.",
                    "rrsp.contribution_receipts",
                )
            )
        for name in ("march_to_december_contributions", "first_60_days_contributions"):
            if getattr(rrsp, name) is None:
                blockers.append(
                    _blocker(
                        "missing_rrsp_period_total",
                        "Current RRSP contributions must be split into the two Schedule 7 periods.",
                        f"rrsp.{name}",
                    )
                )
        receipts = [slip for slip in data.slips if slip.slip_type == "RRSP_RECEIPT"]
        receipt_total = sum(
            (
                slip.fields.get("amount", Decimal("0"))
                for slip in receipts
                if isinstance(slip.fields.get("amount"), Decimal)
            ),
            start=Decimal("0"),
        )
        if not receipts:
            blockers.append(
                _blocker(
                    "missing_rrsp_receipt_document",
                    "Current RRSP contributions require at least one confirmed receipt.",
                    "slips",
                )
            )
        elif rrsp.contribution_receipts is not None and receipt_total != rrsp.contribution_receipts:
            blockers.append(
                _blocker(
                    "rrsp_receipt_mismatch",
                    "The current RRSP receipt total does not match the imported receipts.",
                    "rrsp.contribution_receipts",
                    "slips",
                )
            )
        period_totals = {
            period: sum(
                (
                    slip.fields.get("amount", Decimal("0"))
                    for slip in receipts
                    if slip.rrsp_period == period
                    and isinstance(slip.fields.get("amount"), Decimal)
                ),
                start=Decimal("0"),
            )
            for period in ("march_to_december_2025", "first_60_days_2026")
        }
        entered_periods = {
            "march_to_december_2025": rrsp.march_to_december_contributions,
            "first_60_days_2026": rrsp.first_60_days_contributions,
        }
        if any(
            entered is not None and period_totals[period] != entered
            for period, entered in entered_periods.items()
        ):
            blockers.append(
                _blocker(
                    "rrsp_receipt_period_mismatch",
                    "The Schedule 7 period totals do not match the imported RRSP receipts.",
                    "rrsp.march_to_december_contributions",
                    "rrsp.first_60_days_contributions",
                    "slips",
                )
            )
        if (
            rrsp.contribution_receipts is not None
            and rrsp.march_to_december_contributions is not None
            and rrsp.first_60_days_contributions is not None
            and rrsp.march_to_december_contributions + rrsp.first_60_days_contributions
            != rrsp.contribution_receipts
        ):
            blockers.append(
                _blocker(
                    "rrsp_period_total_mismatch",
                    "The two Schedule 7 contribution periods must add to current receipts.",
                    "rrsp.contribution_receipts",
                    "rrsp.march_to_december_contributions",
                    "rrsp.first_60_days_contributions",
                )
            )
    if rrsp.has_prior_unused_contributions is True and rrsp.prior_unused_contributions is None:
        blockers.append(
            _blocker(
                "missing_prior_unused_rrsp",
                "Prior unused RRSP contributions from the latest NOA are required.",
                "rrsp.prior_unused_contributions",
            )
        )
    has_available = rrsp.has_contributions is True or rrsp.has_prior_unused_contributions is True
    if has_available:
        if rrsp.deduction_limit is None:
            blockers.append(
                _blocker(
                    "missing_rrsp_limit",
                    "The 2025 RRSP deduction limit from the latest NOA is required.",
                    "rrsp.deduction_limit",
                )
            )
        if rrsp.deduction_requested is None:
            blockers.append(
                _blocker(
                    "missing_rrsp_deduction",
                    "The requested RRSP deduction must be stated explicitly.",
                    "rrsp.deduction_requested",
                )
            )
        available = (rrsp.contribution_receipts or Decimal("0")) + (
            rrsp.prior_unused_contributions or Decimal("0")
        )
        if (
            rrsp.deduction_requested is not None
            and (
                rrsp.deduction_requested > available
                or (
                    rrsp.deduction_limit is not None
                    and rrsp.deduction_requested > rrsp.deduction_limit
                )
            )
        ):
            blockers.append(
                _blocker(
                    "rrsp_deduction_exceeds_limit",
                    "The RRSP deduction cannot exceed receipts or the evidenced deduction limit.",
                    "rrsp.deduction_requested",
                )
            )
    return blockers


def _advance_payment_blockers(data: TaxReturnInput) -> list[CompletenessBlocker]:
    credits = data.refundable_credits
    blockers: list[CompletenessBlocker] = []
    rc210s = [slip for slip in data.slips if slip.slip_type == "RC210"]
    rc210_basic = sum(
        (slip.fields.get("10", Decimal("0")) for slip in rc210s), start=Decimal("0")
    )
    rc210_disability = sum(
        (slip.fields.get("11", Decimal("0")) for slip in rc210s), start=Decimal("0")
    )
    if (credits.advanced_cwb_paid or Decimal("0")) + (
        credits.advanced_cwb_disability_paid or Decimal("0")
    ) > 0 and not rc210s:
        blockers.append(
            _blocker(
                "missing_rc210_slip",
                "Advanced Canada workers benefit amounts require an RC210 slip.",
                "slips",
                source_ids=("cra_2025_schedule_6_qc",),
            )
        )
    if rc210s and (
        rc210_basic != (credits.advanced_cwb_paid or Decimal("0"))
        or rc210_disability != (credits.advanced_cwb_disability_paid or Decimal("0"))
    ):
        blockers.append(
            _blocker(
                "rc210_amount_mismatch",
                "RC210 boxes 10 and 11 do not match the entered advance payments.",
                "refundable_credits.advanced_cwb_paid",
                "refundable_credits.advanced_cwb_disability_paid",
                "slips",
                source_ids=("cra_2025_schedule_6_qc",),
            )
        )

    rl19s = [slip for slip in data.slips if slip.slip_type == "RL19"]
    rl19_a = sum((slip.fields.get("A", Decimal("0")) for slip in rl19s), start=Decimal("0"))
    rl19_b = sum((slip.fields.get("B", Decimal("0")) for slip in rl19s), start=Decimal("0"))
    if (credits.rl19_box_a or Decimal("0")) + (credits.rl19_box_b or Decimal("0")) > 0 and not rl19s:
        blockers.append(
            _blocker(
                "missing_rl19_slip",
                "Advance Quebec work-premium amounts require an RL-19 slip.",
                "slips",
                source_ids=("rq_2025_tp1_guide",),
            )
        )
    if rl19s and (
        rl19_a != (credits.rl19_box_a or Decimal("0"))
        or rl19_b != (credits.rl19_box_b or Decimal("0"))
    ):
        blockers.append(
            _blocker(
                "rl19_amount_mismatch",
                "RL-19 boxes A and B do not match the entered advance payments.",
                "refundable_credits.rl19_box_a",
                "refundable_credits.rl19_box_b",
                "slips",
                source_ids=("rq_2025_tp1_guide",),
            )
        )
    if any(
        isinstance(slip.fields.get(box), Decimal) and slip.fields[box] > 0
        for slip in rl19s
        for box in ("C", "D", "G", "H")
    ):
        blockers.append(
            _blocker(
                "unsupported_rl19_advance_boxes",
                "RL-19 boxes C, D, G, and H require credits outside this ruleset.",
                "slips",
                source_ids=("rq_2025_tp1_guide",),
            )
        )
    return blockers


def _tuition_blockers(data: TaxReturnInput) -> list[CompletenessBlocker]:
    federal = data.federal_tuition
    quebec = data.quebec_tuition
    blockers: list[CompletenessBlocker] = []
    t2202s = [slip for slip in data.slips if slip.slip_type == "T2202"]
    for path, value in (
        ("federal_tuition.has_current_tuition", federal.has_current_tuition),
        ("federal_tuition.has_prior_unused", federal.has_prior_unused),
        ("federal_tuition.wants_transfer", federal.wants_transfer),
        (
            "federal_tuition.wants_canada_training_credit",
            federal.wants_canada_training_credit,
        ),
        ("quebec_tuition.has_current_tuition", quebec.has_current_tuition),
        ("quebec_tuition.has_prior_unused", quebec.has_prior_unused),
        ("quebec_tuition.wants_transfer", quebec.wants_transfer),
    ):
        if value is None:
            blockers.append(
                _blocker(
                    "missing_tuition_answer",
                    "Tuition eligibility and election questions require explicit answers.",
                    path,
                )
            )
    if federal.has_current_tuition is True and federal.t2202_eligible_fees is None:
        blockers.append(
            _blocker(
                "missing_t2202_fees",
                "Federal current-year tuition requires eligible fees from T2202.",
                "federal_tuition.t2202_eligible_fees",
                source_ids=("cra_2025_schedule_11_qc",),
            )
        )
    if federal.has_current_tuition is True and not t2202s:
        blockers.append(
            _blocker(
                "missing_t2202_slip",
                "The covered current-year federal tuition claim requires a confirmed T2202.",
                "slips",
                source_ids=("cra_2025_t2202", "cra_2025_schedule_11_qc"),
            )
        )
    t2202_by_institution: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for slip in t2202s:
        amount = slip.fields.get("26")
        if isinstance(amount, Decimal):
            t2202_by_institution[slip.issuer_id] += amount
    t2202_total = sum(
        (amount for amount in t2202_by_institution.values() if amount > Decimal("100")),
        start=Decimal("0"),
    )
    if (
        federal.has_current_tuition is True
        and federal.t2202_eligible_fees is not None
        and t2202s
        and t2202_total != federal.t2202_eligible_fees
    ):
        blockers.append(
            _blocker(
                "t2202_fee_mismatch",
                "The federal tuition amount does not equal total eligible fees in T2202 box 26.",
                "federal_tuition.t2202_eligible_fees",
                "slips",
                source_ids=("cra_2025_t2202", "cra_2025_schedule_11_qc"),
                resolution="Reconcile the entered fees to T2202 box 26.",
            )
        )
    for index, slip in enumerate(data.slips):
        if slip.slip_type != "T2202":
            continue
        for box in ("24", "25"):
            value = slip.fields.get(box)
            if isinstance(value, Decimal) and (value != value.to_integral_value() or value > 12):
                blockers.append(
                    _blocker(
                        "invalid_t2202_month_count",
                        f"T2202 box {box} must be a whole number from 0 to 12.",
                        f"slips.{index}.fields.{box}",
                        source_ids=("cra_2025_t2202",),
                    )
                )
    if quebec.has_current_tuition is True and quebec.eligible_tuition_or_exam_receipts is None:
        blockers.append(
            _blocker(
                "missing_quebec_tuition_receipts",
                "Quebec tuition requires eligible tuition or examination receipts; RL-8 box A is not sufficient.",
                "quebec_tuition.eligible_tuition_or_exam_receipts",
                source_ids=("rq_2025_schedule_t",),
            )
        )
    if quebec.has_current_tuition is True and quebec.institution_outside_quebec is None:
        blockers.append(
            _blocker(
                "missing_quebec_tuition_location",
                "Schedule T requires whether the institution is outside Quebec.",
                "quebec_tuition.institution_outside_quebec",
                source_ids=("rq_2025_schedule_t",),
            )
        )
    if federal.has_prior_unused is True and federal.prior_unused_amount is None:
        blockers.append(
            _blocker(
                "missing_federal_tuition_carryforward",
                "The prior unused federal tuition amount from the latest NOA is required.",
                "federal_tuition.prior_unused_amount",
            )
        )
    if quebec.has_prior_unused is True and (
        quebec.prior_unused_at_8_percent is None
        or quebec.prior_unused_at_20_percent is None
    ):
        blockers.append(
            _blocker(
                "missing_quebec_tuition_carryforward",
                "Both Quebec tuition carryforward rate buckets from the latest notice are required.",
                "quebec_tuition.prior_unused_at_8_percent",
                "quebec_tuition.prior_unused_at_20_percent",
            )
        )
    if federal.wants_canada_training_credit is True and federal.canada_training_credit_limit is None:
        blockers.append(
            _blocker(
                "missing_canada_training_credit_limit",
                "The Canada training credit limit from the latest NOA is required.",
                "federal_tuition.canada_training_credit_limit",
            )
        )
    if federal.wants_canada_training_credit is True and federal.canada_training_credit_claim is None:
        blockers.append(
            _blocker(
                "missing_canada_training_credit_claim",
                "The Canada training credit claim must be entered explicitly.",
                "federal_tuition.canada_training_credit_claim",
            )
        )
    if federal.wants_canada_training_credit is True and (
        data.taxpayer.age_dec31 is not None and not 26 <= data.taxpayer.age_dec31 <= 65
    ):
        blockers.append(
            _blocker(
                "ineligible_canada_training_credit",
                "The Canada training credit requires age 26 to 65 at year end.",
                "taxpayer.age_dec31",
                source_ids=("cra_2025_schedule_11_qc",),
            )
        )
    if federal.wants_transfer is True or quebec.wants_transfer is True:
        blockers.append(
            _blocker(
                "unsupported_tuition_transfer",
                "Tuition transfers require recipient facts outside this release.",
                "federal_tuition.wants_transfer",
                "quebec_tuition.wants_transfer",
                resolution="Set the transfer election to no or use authorized software.",
            )
        )
    if federal.wants_transfer is True and federal.transfer_amount is None:
        blockers.append(
            _blocker(
                "missing_federal_tuition_transfer",
                "The elected federal tuition transfer must be entered.",
                "federal_tuition.transfer_amount",
            )
        )
    if quebec.wants_transfer is True and quebec.transfer_amount is None:
        blockers.append(
            _blocker(
                "missing_quebec_tuition_transfer",
                "The elected Quebec tuition transfer must be entered.",
                "quebec_tuition.transfer_amount",
            )
        )
    return blockers

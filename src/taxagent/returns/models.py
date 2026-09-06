"""Typed public contract for deterministic Quebec returns."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator


LineState = Literal["input", "calculated", "zero", "not_applicable", "blocked"]
NonNegativeMoney = Annotated[Decimal, Field(ge=Decimal("0"), allow_inf_nan=False)]
MonthNumber = Annotated[StrictInt, Field(ge=1, le=12)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaxpayerFacts(StrictModel):
    """Coverage facts stay unknown until the user explicitly answers them."""

    full_year_canada_resident: StrictBool | None = None
    full_year_quebec_resident: StrictBool | None = None
    province_dec31: str | None = None
    age_dec31: Annotated[StrictInt, Field(ge=0, le=130)] | None = None
    marital_status: Literal[
        "single", "married", "common_law", "separated", "divorced", "widowed"
    ] | None = None
    dependant_count: Annotated[StrictInt, Field(ge=0, le=50)] | None = None
    deceased_return: StrictBool | None = None
    bankruptcy_return: StrictBool | None = None
    has_self_employment: StrictBool | None = None
    has_capital_gains: StrictBool | None = None
    has_rental_income: StrictBool | None = None
    has_foreign_income_or_tax: StrictBool | None = None
    has_foreign_property_over_100k: StrictBool | None = None
    has_crypto_transactions: StrictBool | None = None
    has_pension_or_benefit_income: StrictBool | None = None
    has_indian_act_exempt_income: StrictBool | None = None
    has_disability_or_caregiver_claim: StrictBool | None = None
    has_employment_expenses: StrictBool | None = None
    has_medical_expenses: StrictBool | None = None
    has_donations: StrictBool | None = None
    has_childcare_expenses: StrictBool | None = None
    has_moving_expenses: StrictBool | None = None
    has_tips_or_other_employment_income: StrictBool | None = None
    has_student_loan_interest: StrictBool | None = None
    received_qpp_disability_pension: StrictBool | None = None
    made_qpp_cpt30_election: StrictBool | None = None
    was_full_time_student_more_than_13_weeks: StrictBool | None = None


class FederalTuitionInput(StrictModel):
    """Federal Schedule 11 facts; current fees come from T2202 or equivalent."""

    has_current_tuition: StrictBool | None = None
    has_prior_unused: StrictBool | None = None
    wants_transfer: StrictBool | None = None
    wants_canada_training_credit: StrictBool | None = None
    t2202_eligible_fees: NonNegativeMoney | None = None
    prior_unused_amount: NonNegativeMoney | None = None
    canada_training_credit_limit: NonNegativeMoney | None = None
    canada_training_credit_claim: NonNegativeMoney | None = None
    transfer_amount: NonNegativeMoney | None = None


class QuebecTuitionInput(StrictModel):
    """Quebec Schedule T facts; RL-8 is not evidence of the student's own fees."""

    has_current_tuition: StrictBool | None = None
    institution_outside_quebec: StrictBool | None = None
    has_prior_unused: StrictBool | None = None
    wants_transfer: StrictBool | None = None
    eligible_tuition_or_exam_receipts: NonNegativeMoney | None = None
    prior_unused_at_8_percent: NonNegativeMoney | None = None
    prior_unused_at_20_percent: NonNegativeMoney | None = None
    transfer_amount: NonNegativeMoney | None = None


class SlipInput(StrictModel):
    slip_type: str
    document_id: Annotated[str, Field(min_length=1)]
    issuer_id: Annotated[str, Field(min_length=1)]
    tax_year: StrictInt
    province_of_employment: str | None = None
    cpp_qpp_exempt: StrictBool | None = None
    ei_exempt: StrictBool | None = None
    ppip_exempt: StrictBool | None = None
    rrsp_period: Literal[
        "march_to_december",
        "first_60_days",
        "march_to_december_2025",
        "first_60_days_2026",
    ] | None = None
    rl1_box_o_allocations: dict[str, NonNegativeMoney] | None = None
    confirmed: StrictBool | None = None
    fields: dict[str, Decimal | str | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def reject_invalid_money(self) -> "SlipInput":
        invalid = [
            box
            for box, value in self.fields.items()
            if isinstance(value, Decimal) and (not value.is_finite() or value < 0)
        ]
        if invalid:
            raise ValueError(f"slip money must be finite and nonnegative: {invalid}")
        return self


class DocumentInventory(StrictModel):
    income_sources_reviewed: StrictBool | None = None
    deductions_reviewed: StrictBool | None = None
    credits_reviewed: StrictBool | None = None
    cra_records_reviewed: StrictBool | None = None
    revenu_quebec_records_reviewed: StrictBool | None = None
    no_income_sources: StrictBool | None = None


class RrspInput(StrictModel):
    has_contributions: StrictBool | None = None
    has_prior_unused_contributions: StrictBool | None = None
    contribution_receipts: NonNegativeMoney | None = None
    march_to_december_contributions: NonNegativeMoney | None = None
    first_60_days_contributions: NonNegativeMoney | None = None
    prior_unused_contributions: NonNegativeMoney | None = None
    deduction_limit: NonNegativeMoney | None = None
    deduction_requested: NonNegativeMoney | None = None
    has_hbp_or_llp_activity: StrictBool | None = None


class DrugInsuranceInput(StrictModel):
    reviewed: StrictBool | None = None
    group_plan_months: set[MonthNumber] | None = None
    group_plan_source: Literal["self", "parent"] | None = None
    eligible_student_months: set[MonthNumber] | None = None
    other_exemption_applies: StrictBool | None = None


class InstalmentInput(StrictModel):
    federal_reviewed: StrictBool | None = None
    federal_paid: NonNegativeMoney | None = None
    quebec_reviewed: StrictBool | None = None
    quebec_paid: NonNegativeMoney | None = None


class QuebecScheduleBInput(StrictModel):
    """Eligibility facts for the supported Schedule B living-alone branch."""

    living_alone_reviewed: StrictBool | None = None
    eligible_for_living_alone_amount: StrictBool | None = None


class StudentLoanInterestInput(StrictModel):
    """Qualifying government student-loan interest and elected 2025 claims."""

    reviewed: StrictBool | None = None
    qualifying_government_loans_confirmed: StrictBool | None = None
    federal_current_year_paid: NonNegativeMoney | None = None
    federal_unused_2020: NonNegativeMoney | None = None
    federal_unused_2021: NonNegativeMoney | None = None
    federal_unused_2022: NonNegativeMoney | None = None
    federal_unused_2023: NonNegativeMoney | None = None
    federal_unused_2024: NonNegativeMoney | None = None
    federal_unused_by_origin_year: dict[int, NonNegativeMoney] | None = None
    federal_claim_amount: NonNegativeMoney | None = None
    quebec_prior_unused: NonNegativeMoney | None = None
    quebec_current_year_paid: NonNegativeMoney | None = None
    quebec_claim_amount: NonNegativeMoney | None = None


class ScholarshipAwardInput(StrictModel):
    """One award reported through T4A box 105 and Quebec RL-1 box O."""

    award_id: Annotated[str, Field(min_length=1)]
    issuer_id: Annotated[str, Field(min_length=1)]
    amount: NonNegativeMoney | None = None
    category: Literal[
        "ordinary_postsecondary",
        "artist_project_grant",
        "research_grant",
        "apprenticeship_grant",
        "employment_or_business_award",
        "elementary_or_secondary_award",
        "disability_treatment_exception",
    ] | None = None
    qualifying_student: StrictBool | None = None
    attendance: Literal["full_time", "part_time", "nonqualifying"] | None = None
    intended_enrolment_support: NonNegativeMoney | None = None
    part_time_program_id: Annotated[str, Field(min_length=1)] | None = None


class ScholarshipPartTimeProgramInput(StrictModel):
    """One part-time program's eligible tuition and required-material cost pool."""

    program_id: Annotated[str, Field(min_length=1)]
    eligible_tuition_and_required_materials: NonNegativeMoney | None = None


class ScholarshipInput(StrictModel):
    reviewed: StrictBool | None = None
    awards: list[ScholarshipAwardInput] | None = None
    part_time_programs: list[ScholarshipPartTimeProgramInput] | None = None


class RespEapPaymentInput(StrictModel):
    payment_id: Annotated[str, Field(min_length=1)]
    issuer_id: Annotated[str, Field(min_length=1)]
    amount: NonNegativeMoney | None = None


class RespEapInput(StrictModel):
    reviewed: StrictBool | None = None
    has_other_resp_payments: StrictBool | None = None
    qesi_cumulative_amount_over_3600: StrictBool | None = None
    payments: list[RespEapPaymentInput] | None = None


class PandemicRepaymentInput(StrictModel):
    """Repayment evidence and the taxpayer's annual federal allocation election."""

    reviewed: StrictBool | None = None
    repayment_year: StrictInt | None = None
    benefit_receipt_year: StrictInt | None = None
    eligible_repayment_amount: NonNegativeMoney | None = None
    federal_claim_allocations_by_tax_year: dict[int, NonNegativeMoney] | None = None
    quebec_claim_amount: NonNegativeMoney | None = None


class AdditionalReturnScreenInput(StrictModel):
    """Filing situations printed on the T1 or TP-1 outside the supported profile."""

    immigrated_or_emigrated_2025: StrictBool | None = None
    immigrated_or_emigrated_in_tax_year: StrictBool | None = None
    quebec_trust_return: StrictBool | None = None
    separate_post_death_return: StrictBool | None = None
    quebec_enterprise_registration_or_annual_fee: StrictBool | None = None


class RefundableCreditInput(StrictModel):
    work_premium_answers_reviewed: StrictBool | None = None
    solidarity_answers_reviewed: StrictBool | None = None
    canada_workers_benefit_answers_reviewed: StrictBool | None = None
    rl19_advance_payments_reviewed: StrictBool | None = None
    rl19_box_a: NonNegativeMoney | None = None
    rl19_box_b: NonNegativeMoney | None = None
    rl19_has_other_advance_boxes: StrictBool | None = None
    cwb_incarcerated_90_days: StrictBool | None = None
    cwb_foreign_officer_exempt: StrictBool | None = None
    advanced_cwb_paid: NonNegativeMoney | None = None
    advanced_cwb_disability_paid: NonNegativeMoney | None = None
    work_premium_eligible_status: StrictBool | None = None
    quebec_work_premium_full_time_student: StrictBool | None = None
    transferred_schedule_s_amount: StrictBool | None = None
    family_allowance_received_for_self: StrictBool | None = None
    turned_18_before_december: StrictBool | None = None
    designated_as_dependent_child: StrictBool | None = None
    incarcerated_over_183_days: StrictBool | None = None
    adapted_work_premium_eligible: StrictBool | None = None
    work_premium_supplement_months: Annotated[StrictInt, Field(ge=0, le=12)] | None = None
    request_tax_shield: StrictBool | None = None
    wants_solidarity_credit: StrictBool | None = None
    solidarity_eligible_immigration_status: StrictBool | None = None
    solidarity_refugee_claimant_dec31: StrictBool | None = None
    solidarity_family_allowance_paid_for_user_december: StrictBool | None = None
    solidarity_turned_18_in_december: StrictBool | None = None
    solidarity_lived_alone_all_year: StrictBool | None = None
    solidarity_address_same_as_return: StrictBool | None = None
    solidarity_occupancy: Literal["tenant", "owner", "neither"] | None = None
    solidarity_rl31_dwelling_number: str | None = None
    solidarity_rl31_occupant_number: str | None = None
    solidarity_owner_has_municipal_tax_bill: StrictBool | None = None
    solidarity_owner_roll_number: str | None = None
    solidarity_owners_in_dwelling: Annotated[StrictInt, Field(ge=1, le=50)] | None = None


class TaxReturnInput(StrictModel):
    schema_version: Literal["2025-qc-v1", "qc-return-v2"] = "2025-qc-v1"
    tax_year: StrictInt
    province_dec31: str
    taxpayer: TaxpayerFacts
    slips: list[SlipInput] = Field(default_factory=list)
    inventory: DocumentInventory
    federal_tuition: FederalTuitionInput
    quebec_tuition: QuebecTuitionInput
    rrsp: RrspInput
    instalments: InstalmentInput
    quebec_schedule_b: QuebecScheduleBInput
    student_loan_interest: StudentLoanInterestInput
    scholarships: ScholarshipInput
    resp_eap: RespEapInput
    pandemic_repayment: PandemicRepaymentInput = Field(default_factory=PandemicRepaymentInput)
    additional_return_screens: AdditionalReturnScreenInput
    drug_insurance: DrugInsuranceInput
    refundable_credits: RefundableCreditInput

    @model_validator(mode="after")
    def validate_schema_year(self) -> "TaxReturnInput":
        if self.schema_version == "qc-return-v2" and self.tax_year not in range(2020, 2026):
            raise ValueError("qc-return-v2 supports tax years 2020 through 2025")
        if self.schema_version == "qc-return-v2" and self.tax_year == 2025:
            screens = self.additional_return_screens
            if screens.immigrated_or_emigrated_in_tax_year is not None:
                screens.immigrated_or_emigrated_2025 = screens.immigrated_or_emigrated_in_tax_year
            origins = self.student_loan_interest.federal_unused_by_origin_year
            if origins is not None:
                invalid_origins = sorted(
                    year for year in origins if year not in range(2020, 2025)
                )
                if invalid_origins:
                    raise ValueError(
                        f"2025 federal student-loan origin years must be 2020 through 2024: {invalid_origins}"
                    )
            for year in range(2020, 2025):
                field = f"federal_unused_{year}"
                if origins is not None:
                    setattr(self.student_loan_interest, field, origins.get(year))
            period_migration = {
                "march_to_december": "march_to_december_2025",
                "first_60_days": "first_60_days_2026",
            }
            for slip in self.slips:
                if slip.rrsp_period in period_migration:
                    slip.rrsp_period = period_migration[slip.rrsp_period]
        return self


class CompletenessBlocker(StrictModel):
    code: str
    message: str
    input_paths: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    resolution: str


class LineValue(StrictModel):
    form_id: str
    line_id: str
    value: Decimal | int | str | StrictBool | None = None
    status: LineState
    inputs: list[str] = Field(default_factory=list)
    formula_id: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    rounding_id: str | None = None
    explanation: str = ""


class ScheduleResult(StrictModel):
    schedule_id: str
    lines: dict[str, LineValue] = Field(default_factory=dict)
    blockers: list[CompletenessBlocker] = Field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.blockers


class CarryforwardAmount(StrictModel):
    """A calculated closing balance, kept distinct from an assessed opening balance."""

    amount: NonNegativeMoney
    basis: Literal["proposed_closing"] = "proposed_closing"
    source_line_ids: list[str] = Field(default_factory=list)
    explanation: str


class TaxReturnResult(StrictModel):
    status: Literal["complete", "blocked"]
    coverage_profile_id: str
    ruleset_hash: str
    blockers: list[CompletenessBlocker] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    lines: list[LineValue] = Field(default_factory=list)
    federal_refund_or_balance: Decimal | None = None
    quebec_refund_or_balance: Decimal | None = None
    benefit_estimates: dict[str, Decimal] = Field(default_factory=dict)
    carryforwards: dict[str, CarryforwardAmount] = Field(default_factory=dict)
    missing_documents: list[str] = Field(default_factory=list)
    input_digest: str | None = None

    @model_validator(mode="after")
    def keep_blocked_headlines_empty(self) -> "TaxReturnResult":
        if self.status == "blocked" and (
            self.federal_refund_or_balance is not None
            or self.quebec_refund_or_balance is not None
        ):
            raise ValueError("blocked returns cannot expose refund or balance headlines")
        if self.status == "complete" and self.blockers:
            raise ValueError("complete returns cannot contain completeness blockers")
        if self.status == "complete" and (
            self.federal_refund_or_balance is None
            or self.quebec_refund_or_balance is None
        ):
            raise ValueError("complete returns require both final balances")
        return self

"""Explicit 2020-2024 rules for the supported Quebec salary/student profile."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import re
from types import MappingProxyType

from .models import CompletenessBlocker, LineValue, ScheduleResult, TaxReturnInput
from .gates import _advance_payment_blockers, _resp_eap_blockers, _scholarship_blockers


ZERO = Decimal("0.00")
CENT = Decimal("0.01")
PANDEMIC_BOXES = ("197", "198", "199", "200", "202", "203", "204", "211")


@dataclass(frozen=True)
class AnnualRules:
    year: int
    federal_brackets: tuple[tuple[Decimal, Decimal], ...]
    federal_bpa_max: Decimal
    federal_bpa_min: Decimal
    federal_bpa_phase_start: Decimal
    federal_bpa_phase_end: Decimal
    employment_amount: Decimal
    qpp_ympe: Decimal
    qpp_yampe: Decimal
    qpp_first_additional_rate: Decimal
    ei_max_earnings: Decimal
    ei_rate: Decimal
    ei_max: Decimal
    qpip_max: Decimal
    cwb_rate: Decimal
    cwb_max: Decimal
    cwb_reduction_base: Decimal
    quebec_brackets: tuple[tuple[Decimal, Decimal], ...]
    quebec_bpa: Decimal
    quebec_credit_rate: Decimal
    worker_deduction_cap: Decimal
    living_alone_threshold: Decimal
    living_alone_amount: Decimal
    work_premium_cap: Decimal
    work_premium_rate: Decimal
    drug_exemption: Decimal
    drug_rates: tuple[Decimal, Decimal]
    drug_second_threshold: Decimal
    drug_second_base: Decimal
    drug_cap: Decimal
    drug_annual_max: Decimal


def D(value: str) -> Decimal:
    return Decimal(value)


SCHEDULE_F_THRESHOLDS = MappingProxyType({
    2020: (D("15170"), D("52745")), 2021: (D("15360"), D("53410")),
    2022: (D("15765"), D("54820")), 2023: (D("16780"), D("58350")),
    2024: (D("17630"), D("61315")),
})

DRUG_MONTHLY_MAX_REDUCTIONS = MappingProxyType({
    2020: (D("53.00"), D("54.00")),
    2021: (D("55.17"), D("59.17")),
    2022: (D("59.17"), D("59.17")),
    2023: (D("59.17"), D("60.92")),
    2024: (D("60.92"), D("62.00")),
})


ANNUAL_RULES = MappingProxyType(
    {
        2020: AnnualRules(2020, ((D("48535"), D(".15")), (D("97069"), D(".205")), (D("150473"), D(".26")), (D("214368"), D(".29")), (D("Infinity"), D(".33"))), D("13229"), D("12298"), D("150473"), D("214368"), D("1245"), D("58700"), D("58700"), D(".003"), D("54200"), D(".012"), D("650.40"), D("387.79"), D(".274"), D("2319.14"), D("12308.41"), ((D("44545"), D(".15")), (D("89080"), D(".20")), (D("108390"), D(".24")), (D("Infinity"), D(".2575"))), D("15532"), D(".15"), D("1190"), D("35205"), D("1780"), D("10864"), D(".108"), D("16660"), (D(".0665"), D(".0999")), D("14601"), D("332.50"), D("648"), D("642")),
        2021: AnnualRules(2021, ((D("49020"), D(".15")), (D("98040"), D(".205")), (D("151978"), D(".26")), (D("216511"), D(".29")), (D("Infinity"), D(".33"))), D("13808"), D("12421"), D("151978"), D("216511"), D("1257"), D("61600"), D("61600"), D(".005"), D("56300"), D(".0118"), D("664.34"), D("412.49"), D(".373"), D("3201.09"), D("12385.80"), ((D("45105"), D(".15")), (D("90200"), D(".20")), (D("109755"), D(".24")), (D("Infinity"), D(".2575"))), D("15728"), D(".15"), D("1205"), D("35650"), D("1802"), D("10982"), D(".112"), D("16940"), (D(".0711"), D(".1068")), D("14935"), D("355.50"), D("710"), D("686")),
        2022: AnnualRules(2022, ((D("50197"), D(".15")), (D("100392"), D(".205")), (D("155625"), D(".26")), (D("221708"), D(".29")), (D("Infinity"), D(".33"))), D("14398"), D("12719"), D("155625"), D("221708"), D("1287"), D("64900"), D("64900"), D(".0075"), D("60300"), D(".012"), D("723.60"), D("434.72"), D(".373"), D("3296.57"), D("12589.79"), ((D("46295"), D(".15")), (D("92580"), D(".20")), (D("112655"), D(".24")), (D("Infinity"), D(".2575"))), D("16143"), D(".15"), D("1235"), D("36590"), D("1850"), D("11238"), D(".116"), D("17940"), (D(".0736"), D(".1105")), D("14503"), D("368"), D("710"), D("710")),
        2023: AnnualRules(2023, ((D("53359"), D(".15")), (D("106717"), D(".205")), (D("165430"), D(".26")), (D("235675"), D(".29")), (D("Infinity"), D(".33"))), D("15000"), D("13520"), D("165430"), D("235675"), D("1368"), D("66600"), D("66600"), D(".01"), D("61500"), D(".0127"), D("781.05"), D("449.54"), D(".373"), D("3521.87"), D("13294.87"), ((D("49275"), D(".14")), (D("98540"), D(".19")), (D("119910"), D(".24")), (D("Infinity"), D(".2575"))), D("17183"), D(".14"), D("1315"), D("38945"), D("1969"), D("11842"), D(".116"), D("18910"), (D(".0747"), D(".1122")), D("14671"), D("373.50"), D("731"), D("720.50")),
        2024: AnnualRules(2024, ((D("55867"), D(".15")), (D("111733"), D(".205")), (D("173205"), D(".26")), (D("246752"), D(".29")), (D("Infinity"), D(".33"))), D("15705"), D("14156"), D("173205"), D("246752"), D("1433"), D("68500"), D("73200"), D(".01"), D("63200"), D(".0132"), D("834.24"), D("464.36"), D(".373"), D("3705.38"), D("13829.82"), ((D("51780"), D(".14")), (D("103545"), D(".19")), (D("126000"), D(".24")), (D("Infinity"), D(".2575"))), D("18056"), D(".14"), D("1380"), D("40925"), D("2069"), D("12334"), D(".116"), D("19500"), (D(".0765"), D(".1148")), D("14600"), D("382.50"), D("744"), D("737.50")),
    }
)


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def line(form: str, line_id: str, value: Decimal, source: str, formula: str, *inputs: str) -> LineValue:
    value = money(value)
    return LineValue(form_id=form, line_id=line_id, value=value, status="calculated" if value else "zero", inputs=list(inputs), formula_id=formula, source_ids=[source], rounding_id="money_cents_half_up", explanation=f"{form} line {line_id}: {formula.replace('_', ' ')} for the selected tax year.")


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


_MAIN_LINES = _freeze(json.loads(Path(__file__).with_name("annual_main_lines.json").read_text(encoding="utf-8-sig")))

T1_ALWAYS = frozenset("10100 11900 12100 13000 13010 14700 15000 20600 20700 20800 21200 22215 23200 23300 23400 23500 23600 25700 26000 30000 30800 31200 31205 31210 31260 31900 32300 33500 33800 35000 40400 40600 41600 41700 42000 42900 43500 43700 43800 44000 45000 45100 45300 45350 47600 48200 48400 48500".split())
TP1_ALWAYS = frozenset("97 98 101 111 130 154 199 201 205 214 246 248 254 256 275 279 295 298 299 350 358 359 361 377 377.1 385 389 397 398 399 401 406 413 425 430 431 432 441 446 447 450 451 451.2 452 456 457 465 466 468 470 474 475 476 477 478 479 498 499".split())


def complete_annual_main_lines(year: int, lines: list[LineValue]) -> list[LineValue]:
    """Complete annual membership after explicit profile gates resolved applicability."""

    by_key = {(item.form_id, item.line_id): item for item in lines}
    manifest = _MAIN_LINES[str(year)]
    for form, key, source, always in (("T1", "federal", f"cra_{year}_5005_r", T1_ALWAYS), ("TP1", "quebec", f"rq_{year}_tp1", TP1_ALWAYS)):
        for line_id, label in manifest[key].items():
            existing = by_key.get((form, line_id))
            if existing:
                existing.explanation = f"{form} line {line_id}: {label} {existing.explanation}"
                continue
            if line_id in always:
                raise RuntimeError(f"annual rules omitted required {form} line {line_id} for {year}")
            numeric_id = Decimal(line_id)
            group = "income" if numeric_id < (D("20000") if form == "T1" else D("200")) else "deduction" if numeric_id < (D("30000") if form == "T1" else D("300")) else "credit"
            by_key[(form, line_id)] = LineValue(
                form_id=form,
                line_id=line_id,
                status="not_applicable",
                source_ids=[source],
                explanation=f"{form} line {line_id}: {label} The {group} inventory and explicit profile screens make this line not applicable.",
            )
    rules = ANNUAL_RULES[year]
    taxable = by_key[("T1", "26000")].value
    assert isinstance(taxable, Decimal)
    bracket_floor = ZERO
    bracket_rate = rules.federal_brackets[0][1]
    for ceiling, rate in rules.federal_brackets:
        bracket_rate = rate
        if taxable <= ceiling:
            break
        bracket_floor = ceiling
    bracket_excess = money(taxable - bracket_floor)
    bracket_product = money(bracket_excess * bracket_rate)
    bracket_base = bracket_tax(bracket_floor, rules.federal_brackets)
    starts = {2020: 64, 2021: 68, 2022: 68, 2023: 70, 2024: 76}
    start = starts[year]
    bracket_rows = {
        str(start): taxable,
        str(start + 1): taxable if year == 2020 else bracket_floor,
        str(start + 2): bracket_floor if year == 2020 else bracket_excess,
        str(start + 3): bracket_excess if year == 2020 else bracket_rate,
        str(start + 4): bracket_rate if year == 2020 else bracket_product,
        str(start + 5): bracket_product if year == 2020 else bracket_base,
        str(start + 6): bracket_base if year == 2020 else bracket_tax(taxable, rules.federal_brackets),
    }
    if year == 2020:
        bracket_rows[str(start + 7)] = bracket_tax(taxable, rules.federal_brackets)
    printed: dict[str, Decimal] = {}
    profile_zero_rows = {
        2020: frozenset(),
        2021: frozenset({"128", "132", "134"}),
        2022: frozenset({"128", "132", "134"}),
        2023: frozenset({"130", "134", "136"}),
        2024: frozenset({"136", "140", "142"}),
    }[year]

    def printed_calculation(row_id: str, label: str) -> Decimal | None:
        range_match = re.search(r"Add lines (\d+) to (\d+)", label, re.IGNORECASE)
        if range_match:
            first, last = map(int, range_match.groups())
            return sum((printed.get(str(number), ZERO) for number in range(first, last + 1)), start=ZERO)
        list_match = re.search(r"Add lines ([\d, ]+?)(?:,? and| to) (\d+)", label, re.IGNORECASE)
        if list_match:
            ids = re.findall(r"\d+", list_match.group(1)) + [list_match.group(2)]
            return sum((printed.get(item, ZERO) for item in ids), start=ZERO)
        plus_match = re.search(r"Line (\d+) plus line (\d+)", label, re.IGNORECASE)
        if plus_match:
            return sum((printed.get(item, ZERO) for item in plus_match.groups()), start=ZERO)
        minus_match = re.search(r"Line (\d+) minus line (\d+)", label, re.IGNORECASE)
        if minus_match:
            value = printed.get(minus_match.group(1), ZERO) - printed.get(minus_match.group(2), ZERO)
            return max(value, ZERO) if "negative, enter" in label.lower() else value
        carry_match = re.search(r"(?:amount|subtotal).*from line (\d+)", label, re.IGNORECASE)
        if carry_match:
            return printed.get(carry_match.group(1), ZERO)
        if "Federal non-refundable tax credit rate" in label:
            return D(".15")
        medical_match = re.search(r"less: \$([\d,]+) or the amount from line (\d+)", label)
        if medical_match:
            return min(D(medical_match.group(1).replace(",", "")), printed.get(medical_match.group(2), ZERO))
        if year == 2020 and row_id == "103":
            return min(D("2397"), money(by_key[("T1", "23600")].value * D(".03")))
        if row_id in profile_zero_rows:
            return ZERO
        return None

    for item in manifest["federal_printed_rows"]:
        row_id = str(item["id"])
        value = bracket_rows.get(row_id)
        if value is None:
            candidates = [by_key.get(("T1", canonical)) for canonical in item["canonical_line_ids"]]
            amounts = [candidate.value for candidate in candidates if candidate is not None and isinstance(candidate.value, Decimal)]
            value = amounts[-1] if amounts else ZERO if item["canonical_line_ids"] else printed_calculation(row_id, item["label"])
        if value is None:
            raise RuntimeError(f"annual rules omitted applicable printed T1 row {row_id} for {year}")
        printed[row_id] = money(value)
        by_key[("T1", row_id)] = line("T1", row_id, value, f"cra_{year}_5005_r", "printed_main_form_row")
        by_key[("T1", row_id)].explanation = f"T1 row {row_id}: {item['label']}"
    return list(by_key.values())


def blocker(code: str, message: str, paths: list[str], year: int) -> CompletenessBlocker:
    return CompletenessBlocker(code=code, message=message, input_paths=paths, source_ids=[f"cra_{year}_5005_r", f"rq_{year}_tp1"], resolution="Correct or confirm the annual return facts before calculating.")


def slips(data: TaxReturnInput, kind: str):
    return [item for item in data.slips if item.slip_type.upper() == kind]


def sum_box(data: TaxReturnInput, kind: str, box: str) -> Decimal:
    return money(sum((value for slip in slips(data, kind) if isinstance((value := slip.fields.get(box)), Decimal)), start=ZERO))


def boxes_by_issuer(data: TaxReturnInput, kind: str, box: str) -> dict[str, Decimal]:
    amounts: dict[str, Decimal] = {}
    for slip in slips(data, kind):
        value = slip.fields.get(box)
        if isinstance(value, Decimal):
            amounts[slip.issuer_id] = amounts.get(slip.issuer_id, ZERO) + value
    return {issuer: money(value) for issuer, value in amounts.items()}


def required_money_boxes(slip_type: str, year: int, present_boxes: set[str]) -> set[str]:
    if slip_type == "T4":
        boxes = {"14", "17", "18", "20", "22", "24", "26", "44", "52", "55"}
        return boxes | ({"17A"} if year >= 2024 else set())
    if slip_type == "RL1":
        employment_boxes = {"A", "B" if year < 2024 else "B.A", "C", "D", "E", "F", "G", "H", "I", "211"}
        if year >= 2024:
            employment_boxes.add("B.B")
        employment_trigger_boxes = employment_boxes - {"E"}
        return employment_boxes if present_boxes & employment_trigger_boxes else set()
    if slip_type == "T5":
        return {"13"}
    if slip_type == "RL3":
        return {"D"}
    if slip_type == "T2202":
        return {"24", "25", "26"}
    if slip_type == "RRSP_RECEIPT":
        return {"amount"}
    if slip_type == "RC210":
        return {"10", "11"}
    if slip_type == "RL19":
        return {"A", "B"}
    return set()


def sum_rl1_allocations(data: TaxReturnInput, codes: set[str]) -> Decimal:
    return money(sum((amount for slip in slips(data, "RL1") for code, amount in (slip.rl1_box_o_allocations or {}).items() if code in codes), start=ZERO))


def taxable_scholarships(data: TaxReturnInput) -> Decimal:
    awards = data.scholarships.awards or []
    gross = sum((award.amount or ZERO for award in awards), start=ZERO)
    full_time_exemption = ZERO
    part_time_awards = ZERO
    programs: set[str] = set()
    for award in awards:
        if award.qualifying_student is not True:
            continue
        amount = award.amount or ZERO
        if award.attendance == "full_time":
            full_time_exemption += min(amount, award.intended_enrolment_support or ZERO)
        elif award.attendance == "part_time":
            part_time_awards += amount
            if award.part_time_program_id:
                programs.add(award.part_time_program_id)
    costs = sum((program.eligible_tuition_and_required_materials or ZERO for program in (data.scholarships.part_time_programs or []) if program.program_id in programs), start=ZERO)
    remaining = max(money(gross - full_time_exemption - min(part_time_awards, costs)), ZERO)
    return max(money(remaining - min(remaining, D("500"))), ZERO)


def annual_preflight(data: TaxReturnInput) -> list[CompletenessBlocker]:
    year = data.tax_year
    problems: list[CompletenessBlocker] = []
    if data.schema_version != "qc-return-v2":
        problems.append(blocker("unsupported_schema_version", "Earlier years require qc-return-v2.", ["schema_version"], year))
    if data.province_dec31 != "QC" or data.taxpayer.province_dec31 != "QC":
        problems.append(blocker("unsupported_province", "The annual rules cover Quebec residents.", ["province_dec31", "taxpayer.province_dec31"], year))
    required_true = ("full_year_canada_resident", "full_year_quebec_resident")
    if any(getattr(data.taxpayer, name) is not True for name in required_true):
        problems.append(blocker("unsupported_residency", "Full-year Canadian and Quebec residence is required.", [f"taxpayer.{name}" for name in required_true], year))
    if data.taxpayer.marital_status != "single" or data.taxpayer.dependant_count != 0:
        problems.append(blocker("unsupported_family_status", "This profile covers a single taxpayer without dependants.", ["taxpayer.marital_status", "taxpayer.dependant_count"], year))
    unsupported = [
        name for name in (
            "deceased_return", "bankruptcy_return", "has_self_employment", "has_capital_gains",
            "has_rental_income", "has_foreign_income_or_tax", "has_foreign_property_over_100k",
            "has_crypto_transactions", "has_pension_or_benefit_income", "has_indian_act_exempt_income",
            "has_disability_or_caregiver_claim", "has_employment_expenses", "has_medical_expenses",
            "has_donations", "has_childcare_expenses", "has_moving_expenses", "has_tips_or_other_employment_income",
        ) if getattr(data.taxpayer, name) is not False
    ]
    if unsupported:
        problems.append(blocker("unsupported_situation", "A fact is unknown or outside the supported salary/student profile.", [f"taxpayer.{name}" for name in unsupported], year))
    if data.additional_return_screens.immigrated_or_emigrated_in_tax_year is not False:
        problems.append(blocker("unsupported_part_year_residency", "Immigration or emigration in the tax year needs part-year rules.", ["additional_return_screens.immigrated_or_emigrated_in_tax_year"], year))
    if any(getattr(data.additional_return_screens, name) is not False for name in ("quebec_trust_return", "separate_post_death_return", "quebec_enterprise_registration_or_annual_fee")):
        problems.append(blocker("unsupported_return_screen", "A special Quebec return screen applies.", ["additional_return_screens"], year))
    if any(slip.tax_year != year for slip in data.slips):
        problems.append(blocker("wrong_slip_year", "Every slip must belong to the selected tax year.", ["slips"], year))
    if any(slip.confirmed is not True for slip in data.slips):
        problems.append(blocker("unconfirmed_slip", "Every imported slip must be confirmed.", ["slips"], year))
    supported = {"T4", "RL1", "T5", "RL3", "T4A", "T4E", "T2202", "RRSP_RECEIPT", "RC210", "RL19"}
    if any(slip.slip_type.upper() not in supported for slip in data.slips):
        problems.append(blocker("unsupported_slip", "An imported slip is outside annual coverage.", ["slips"], year))
    allowed_boxes = {
        "T4": {"14", "17", "18", "20", "22", "24", "26", "44", "52", "55", "56", "57", "58", "59", "60"} | ({"17A"} if year >= 2024 else set()),
        "RL1": {"A", "B" if year < 2024 else "B.A", "B.B" if year >= 2024 else "B", "C", "D", "E", "F", "G", "H", "I", "O", "211"},
        "T5": {"13"}, "RL3": {"D"},
        "T4A": {"022", "22", "042", "105", "201", *PANDEMIC_BOXES},
        "T4E": {"14", "15", "17", "18", "22", "23", "26", "30", "33", "36", "37"},
        "T2202": {"24", "25", "26"}, "RRSP_RECEIPT": {"amount"}, "RC210": {"10", "11"},
        "RL19": {"A", "B"},
    }
    ignored_positive = [f"slips.{slip.document_id}.fields.{box}" for slip in data.slips for box, value in slip.fields.items() if box not in allowed_boxes.get(slip.slip_type.upper(), set()) and isinstance(value, Decimal) and value != ZERO]
    if ignored_positive:
        problems.append(blocker("unsupported_positive_slip_box", "A positive slip box has no annual calculation mapping.", ignored_positive, year))
    missing_boxes = [
        f"slips.{slip.document_id}.fields.{box}"
        for slip in data.slips
        for box in sorted(required_money_boxes(slip.slip_type.upper(), year, set(slip.fields)) - set(slip.fields))
    ]
    if missing_boxes:
        problems.append(blocker("missing_slip_box", "Required slip boxes must be entered explicitly, including printed zero amounts.", missing_boxes, year))
    invalid_money_boxes = [
        f"slips.{slip.document_id}.fields.{box}"
        for slip in data.slips
        for box in sorted(required_money_boxes(slip.slip_type.upper(), year, set(slip.fields)) & set(slip.fields))
        if not isinstance(slip.fields[box], Decimal)
    ]
    if invalid_money_boxes:
        problems.append(blocker("invalid_slip_box_type", "Required slip boxes must be numeric amounts.", invalid_money_boxes, year))
    # These evidence gates do not calculate year-specific tax amounts. Preserve
    # annual source references instead of attaching their 2025 citations.
    evidence_gates = [_scholarship_blockers, _resp_eap_blockers]
    if not invalid_money_boxes:
        evidence_gates.append(_advance_payment_blockers)
    for gate in evidence_gates:
        problems.extend(blocker(item.code, item.message, item.input_paths, year) for item in gate(data))
    missing_instalments = [
        f"instalments.{name}"
        for name in ("federal_reviewed", "federal_paid", "quebec_reviewed", "quebec_paid")
        if getattr(data.instalments, name) is None
        or (name.endswith("reviewed") and getattr(data.instalments, name) is not True)
    ]
    if missing_instalments:
        problems.append(blocker("missing_instalment_answers", "Federal and Quebec instalments must be reviewed and entered, including zero.", missing_instalments, year))
    missing_t4_metadata = [
        f"slips.{slip.document_id}.{name}"
        for slip in slips(data, "T4")
        for name in ("cpp_qpp_exempt", "ei_exempt", "ppip_exempt")
        if getattr(slip, name) is None
    ]
    if missing_t4_metadata:
        problems.append(blocker("missing_t4_exemption_answer", "Each T4 box 28 exemption indicator must be entered explicitly.", missing_t4_metadata, year))
    unsupported_t4_exemptions = [
        f"slips.{slip.document_id}.{name}"
        for slip in slips(data, "T4")
        for name in ("cpp_qpp_exempt", "ei_exempt", "ppip_exempt")
        if getattr(slip, name) is True
    ]
    if unsupported_t4_exemptions:
        problems.append(blocker("unsupported_t4_exemption", "T4 box 28 exemptions need branches outside the Quebec salary profile.", unsupported_t4_exemptions, year))
    outside_quebec_t4s = [
        f"slips.{slip.document_id}.province_of_employment"
        for slip in slips(data, "T4")
        if slip.province_of_employment != "QC"
    ]
    if outside_quebec_t4s:
        problems.append(blocker("outside_quebec_employment", "Each T4 must explicitly show Quebec province of employment for the annual Quebec salary rules.", outside_quebec_t4s, year))
    inventory_missing = [name for name in ("income_sources_reviewed", "deductions_reviewed", "credits_reviewed", "cra_records_reviewed", "revenu_quebec_records_reviewed") if getattr(data.inventory, name) is not True]
    if inventory_missing:
        problems.append(blocker("missing_inventory_review", "Annual calculation requires each document inventory section to be reviewed.", [f"inventory.{name}" for name in inventory_missing], year))
    t4_issuers = {slip.issuer_id for slip in slips(data, "T4")}
    rl1_employers = {slip.issuer_id for slip in slips(data, "RL1") if isinstance(slip.fields.get("A"), Decimal)}
    if t4_issuers != rl1_employers:
        problems.append(blocker("missing_slip_counterpart", "Each employment T4 needs its issuer-matched RL-1.", ["slips"], year))
    qpp_pairs = [("17", "B.A" if year >= 2024 else "B")]
    if year >= 2024:
        qpp_pairs.append(("17A", "B.B"))
    if any(boxes_by_issuer(data, "T4", t4_box) != boxes_by_issuer(data, "RL1", rl1_box) for t4_box, rl1_box in qpp_pairs):
        problems.append(blocker(
            "qpp_slip_contribution_mismatch",
            "Issuer-matched T4 and RL-1 QPP contributions must reconcile before either return is calculated.",
            ["slips"],
            year,
        ))
    has_qpp_earnings = bool(sum_box(data, "T4", "14") or sum_box(data, "T4", "17") or sum_box(data, "T4", "17A"))
    qpp_period_facts = (
        data.taxpayer.age_dec31,
        data.taxpayer.received_qpp_disability_pension,
        data.taxpayer.made_qpp_cpt30_election,
    )
    if has_qpp_earnings and any(value is None for value in qpp_period_facts):
        problems.append(blocker(
            "missing_qpp_contribution_period",
            "Schedule 8 contribution months require age, QPP disability-pension, and CPT30 facts.",
            ["taxpayer.age_dec31", "taxpayer.received_qpp_disability_pension", "taxpayer.made_qpp_cpt30_election"],
            year,
        ))
    elif has_qpp_earnings and (
        not 19 <= data.taxpayer.age_dec31 <= 64
        or data.taxpayer.received_qpp_disability_pension
        or data.taxpayer.made_qpp_cpt30_election
    ):
        problems.append(blocker(
            "unsupported_qpp_contributory_period",
            "A nonstandard Schedule 8 contribution period needs month facts outside this salary/student profile.",
            ["taxpayer.age_dec31", "taxpayer.received_qpp_disability_pension", "taxpayer.made_qpp_cpt30_election"],
            year,
        ))
    if {slip.issuer_id for slip in slips(data, "T5")} != {slip.issuer_id for slip in slips(data, "RL3")}:
        problems.append(blocker("missing_slip_counterpart", "Each T5 needs its issuer-matched RL-3.", ["slips"], year))
    scholarship_slip = sum_box(data, "T4A", "105")
    scholarship_awards = money(sum((award.amount or ZERO for award in (data.scholarships.awards or [])), start=ZERO))
    if scholarship_slip != scholarship_awards:
        problems.append(blocker("scholarship_evidence_mismatch", "T4A box 105 must reconcile to categorized scholarship awards.", ["slips", "scholarships.awards"], year))
    resp_slip = sum_box(data, "T4A", "042")
    resp_payments = money(sum((payment.amount or ZERO for payment in (data.resp_eap.payments or [])), start=ZERO))
    if resp_slip != resp_payments:
        problems.append(blocker("resp_evidence_mismatch", "T4A box 042 must reconcile to RESP educational assistance payments.", ["slips", "resp_eap.payments"], year))
    if scholarship_slip != sum_rl1_allocations(data, {"RB", "RZ-RB"}):
        problems.append(blocker("quebec_scholarship_evidence_mismatch", "Scholarship T4A and Quebec RL-1 allocations must reconcile.", ["slips"], year))
    if resp_slip != sum_rl1_allocations(data, {"RU", "RZ-RU"}):
        problems.append(blocker("quebec_resp_evidence_mismatch", "RESP T4A and Quebec RL-1 allocations must reconcile.", ["slips"], year))
    if year < 2024 and (sum_box(data, "T4", "17A") or sum_box(data, "RL1", "B.B")):
        problems.append(blocker("qpp2_not_available", "Second additional QPP did not exist before 2024.", ["slips"], year))
    repayment = data.pandemic_repayment
    slip_repayment = money(sum_box(data, "T4A", "201") + sum_box(data, "T4E", "30"))
    federal_allocations = repayment.federal_claim_allocations_by_tax_year or {}
    has_repayment = bool(slip_repayment or repayment.eligible_repayment_amount or federal_allocations or repayment.quebec_claim_amount)
    if has_repayment:
        missing_repayment = [name for name in ("repayment_year", "benefit_receipt_year", "eligible_repayment_amount") if getattr(repayment, name) is None]
        if repayment.reviewed is not True or missing_repayment:
            problems.append(blocker("missing_pandemic_repayment_allocation", "Pandemic repayments require reviewed benefit-year, repayment-year, eligible amount, and annual claim allocations.", ["pandemic_repayment"], year))
        else:
            eligible = repayment.eligible_repayment_amount or ZERO
            if slip_repayment and slip_repayment != eligible:
                problems.append(blocker("pandemic_repayment_evidence_mismatch", "The eligible pandemic repayment must reconcile to T4A box 201 and T4E box 30 evidence.", ["slips", "pandemic_repayment.eligible_repayment_amount"], year))
            if sum(federal_allocations.values(), start=ZERO) > eligible or (repayment.quebec_claim_amount or ZERO) > eligible:
                problems.append(blocker("pandemic_repayment_claim_exceeds_evidence", "Pandemic repayment claims exceed the reviewed eligible repayment.", ["pandemic_repayment"], year))
            permitted_claim_years = (
                {repayment.benefit_receipt_year, repayment.repayment_year}
                if repayment.repayment_year in {2021, 2022}
                else {repayment.repayment_year}
            )
            invalid_claim_years = [claim_year for claim_year in federal_allocations if claim_year not in permitted_claim_years]
            if invalid_claim_years:
                problems.append(blocker("invalid_pandemic_repayment_claim_year", "Only repayments made in 2021 or 2022 may be allocated to the benefit-receipt year; later repayments belong to the repayment year.", ["pandemic_repayment.federal_claim_allocations_by_tax_year"], year))
            if repayment.quebec_claim_amount and repayment.repayment_year != year:
                problems.append(blocker("invalid_quebec_pandemic_repayment_year", "The Quebec repayment deduction belongs to the repayment-year return.", ["pandemic_repayment.repayment_year", "pandemic_repayment.quebec_claim_amount"], year))
    loan = data.student_loan_interest
    origins = loan.federal_unused_by_origin_year or {}
    invalid_origins = sorted(origin for origin in origins if origin not in range(year - 5, year))
    if invalid_origins:
        problems.append(blocker("student_loan_origin_outside_claim_window", f"Federal student-loan origins {invalid_origins} fall outside the preceding five years.", ["student_loan_interest.federal_unused_by_origin_year"], year))
    available_loan = money((loan.federal_current_year_paid or ZERO) + sum(origins.values(), start=ZERO))
    if (loan.federal_claim_amount or ZERO) > available_loan:
        problems.append(blocker("student_loan_claim_exceeds_available", "The federal student-loan claim exceeds current and eligible unused interest.", ["student_loan_interest.federal_claim_amount"], year))
    if data.rrsp.has_contributions:
        missing = [name for name in ("deduction_limit", "deduction_requested") if getattr(data.rrsp, name) is None]
        if missing:
            problems.append(blocker("missing_assessed_rrsp_balance", "RRSP claims require the assessed deduction limit and requested deduction.", [f"rrsp.{name}" for name in missing], year))
        available = money((data.rrsp.prior_unused_contributions or ZERO) + (data.rrsp.contribution_receipts or ZERO))
        if (data.rrsp.deduction_requested or ZERO) > min(available, data.rrsp.deduction_limit or ZERO):
            problems.append(blocker("rrsp_claim_exceeds_available", "RRSP deduction exceeds receipts, prior assessed contributions, or the assessed limit.", ["rrsp.deduction_requested"], year))
        receipt_periods = {"march_to_december": ZERO, "first_60_days": ZERO}
        for receipt in slips(data, "RRSP_RECEIPT"):
            amount = receipt.fields.get("amount")
            if receipt.rrsp_period in receipt_periods and isinstance(amount, Decimal):
                receipt_periods[receipt.rrsp_period] += amount
        expected_periods = {
            "march_to_december": data.rrsp.march_to_december_contributions or ZERO,
            "first_60_days": data.rrsp.first_60_days_contributions or ZERO,
        }
        if any(money(receipt_periods[key]) != money(value) for key, value in expected_periods.items()):
            problems.append(blocker("rrsp_receipt_period_mismatch", "RRSP receipt periods do not reconcile to the entered period totals.", ["slips", "rrsp.march_to_december_contributions", "rrsp.first_60_days_contributions"], year))
    if data.rrsp.has_prior_unused_contributions and data.rrsp.prior_unused_contributions is None:
        problems.append(blocker("missing_assessed_rrsp_contributions", "Prior unused RRSP contributions require the assessed opening balance.", ["rrsp.prior_unused_contributions"], year))
    if data.rrsp.has_hbp_or_llp_activity is not False:
        problems.append(blocker("unsupported_hbp_llp", "HBP or LLP activity requires additional annual Schedule 7 branches.", ["rrsp.has_hbp_or_llp_activity"], year))
    if data.federal_tuition.has_prior_unused and data.federal_tuition.prior_unused_amount is None:
        problems.append(blocker("missing_assessed_federal_tuition", "Prior federal tuition must come from an assessed opening balance.", ["federal_tuition.prior_unused_amount"], year))
    federal_current = current_tuition(data)
    entered_current = data.federal_tuition.t2202_eligible_fees
    if (federal_current and data.federal_tuition.has_current_tuition is not True) or (
        entered_current is not None and money(entered_current) != federal_current
    ):
        problems.append(blocker(
            "federal_tuition_evidence_mismatch",
            "The current-tuition answer and entered eligible fees must reconcile to confirmed T2202 evidence.",
            ["slips", "federal_tuition.has_current_tuition", "federal_tuition.t2202_eligible_fees"],
            year,
        ))
    if data.federal_tuition.wants_transfer is True and data.federal_tuition.transfer_amount is None:
        problems.append(blocker("missing_federal_tuition_transfer", "A requested federal tuition transfer needs an explicit amount.", ["federal_tuition.transfer_amount"], year))
    if data.federal_tuition.wants_transfer is not True and (data.federal_tuition.transfer_amount or ZERO) > ZERO:
        problems.append(blocker("federal_tuition_transfer_election_mismatch", "A positive federal transfer amount requires an affirmative transfer election.", ["federal_tuition.wants_transfer", "federal_tuition.transfer_amount"], year))
    if data.federal_tuition.wants_canada_training_credit is not True and (data.federal_tuition.canada_training_credit_claim or ZERO) > ZERO:
        problems.append(blocker("training_credit_election_mismatch", "A positive Canada training credit claim requires an affirmative election.", ["federal_tuition.wants_canada_training_credit", "federal_tuition.canada_training_credit_claim"], year))
    if data.quebec_tuition.has_prior_unused and (data.quebec_tuition.prior_unused_at_8_percent is None or data.quebec_tuition.prior_unused_at_20_percent is None):
        problems.append(blocker("missing_assessed_quebec_tuition", "Prior Quebec tuition pools require assessed opening balances.", ["quebec_tuition"], year))
    quebec_current = money(data.quebec_tuition.eligible_tuition_or_exam_receipts or ZERO)
    if quebec_current and data.quebec_tuition.has_current_tuition is not True:
        problems.append(blocker(
            "quebec_tuition_evidence_mismatch",
            "Positive Quebec tuition receipts require an affirmative current-tuition answer.",
            ["quebec_tuition.has_current_tuition", "quebec_tuition.eligible_tuition_or_exam_receipts"],
            year,
        ))
    if quebec_current and data.quebec_tuition.institution_outside_quebec is None:
        problems.append(blocker(
            "missing_quebec_tuition_institution_location",
            "Current Quebec tuition requires the institution-location answer used by Schedule T.",
            ["quebec_tuition.institution_outside_quebec"],
            year,
        ))
    if data.quebec_tuition.wants_transfer is True and data.quebec_tuition.transfer_amount is None:
        problems.append(blocker("missing_quebec_tuition_transfer", "A requested Quebec tuition-credit transfer needs an explicit amount.", ["quebec_tuition.transfer_amount"], year))
    if data.quebec_tuition.wants_transfer is not True and (data.quebec_tuition.transfer_amount or ZERO) > ZERO:
        problems.append(blocker("quebec_tuition_transfer_election_mismatch", "A positive Quebec transfer amount requires an affirmative transfer election.", ["quebec_tuition.wants_transfer", "quebec_tuition.transfer_amount"], year))
    if data.federal_tuition.wants_canada_training_credit:
        ctc_claim = data.federal_tuition.canada_training_credit_claim
        ctc_limit = data.federal_tuition.canada_training_credit_limit
        if ctc_claim is None or ctc_limit is None:
            problems.append(blocker("missing_assessed_training_credit_limit", "A Canada training credit claim requires the assessed limit and elected claim.", ["federal_tuition.canada_training_credit_limit", "federal_tuition.canada_training_credit_claim"], year))
        elif ctc_claim > min(ctc_limit, money(federal_current * D(".50"))):
            problems.append(blocker("training_credit_claim_exceeds_available", "The Canada training credit claim exceeds the assessed limit or one-half of current eligible Canadian tuition.", ["federal_tuition.canada_training_credit_claim"], year))
        if data.taxpayer.age_dec31 is not None and not 26 <= data.taxpayer.age_dec31 <= 65:
            problems.append(blocker("ineligible_canada_training_credit", "The Canada training credit requires age 26 to 65 at year end.", ["taxpayer.age_dec31"], year))
    if data.taxpayer.has_student_loan_interest:
        if data.student_loan_interest.reviewed is not True or data.student_loan_interest.qualifying_government_loans_confirmed is not True:
            problems.append(blocker("missing_student_loan_evidence", "Student-loan interest claims require reviewed qualifying government-loan evidence.", ["student_loan_interest"], year))
        quebec_available = money((loan.quebec_prior_unused or ZERO) + (loan.quebec_current_year_paid or ZERO))
        if (loan.quebec_claim_amount or ZERO) > quebec_available:
            problems.append(blocker("quebec_student_loan_claim_exceeds_available", "The Quebec student-loan claim exceeds current and assessed unused interest.", ["student_loan_interest.quebec_claim_amount"], year))
    drug = data.drug_insurance
    if drug.reviewed is not True or drug.group_plan_months is None or drug.eligible_student_months is None or drug.other_exemption_applies is None:
        problems.append(blocker("missing_drug_insurance_facts", "Schedule K needs reviewed month-by-month coverage and exemptions.", ["drug_insurance"], year))
    if drug.other_exemption_applies:
        problems.append(blocker("unsupported_drug_insurance_exemption", "Another Schedule K exemption needs a branch outside this profile.", ["drug_insurance.other_exemption_applies"], year))
    if drug.group_plan_months and drug.group_plan_source not in {"self", "parent"}:
        problems.append(blocker("missing_group_plan_source", "Group-plan months require the membership source.", ["drug_insurance.group_plan_source"], year))
    credits = data.refundable_credits
    if any(getattr(credits, name) is not True for name in ("work_premium_answers_reviewed", "solidarity_answers_reviewed", "canada_workers_benefit_answers_reviewed", "rl19_advance_payments_reviewed")):
        problems.append(blocker("missing_refundable_credit_review", "Annual refundable-credit questions must be reviewed.", ["refundable_credits"], year))
    if credits.wants_solidarity_credit:
        problems.append(blocker("unsupported_solidarity_credit", "A positive solidarity-credit claim requires annual Schedule D calculation.", ["refundable_credits.wants_solidarity_credit"], year))
    if credits.rl19_has_other_advance_boxes or credits.adapted_work_premium_eligible or (credits.work_premium_supplement_months or 0) > 0 or credits.request_tax_shield:
        problems.append(blocker("unsupported_refundable_credit_branch", "An additional refundable-credit branch applies outside this profile.", ["refundable_credits"], year))
    cwb_facts = ("cwb_incarcerated_90_days", "cwb_foreign_officer_exempt")
    if any(getattr(credits, name) is None for name in cwb_facts) or data.taxpayer.was_full_time_student_more_than_13_weeks is None or data.taxpayer.age_dec31 is None:
        problems.append(blocker("missing_cwb_eligibility", "The annual CWB eligibility facts must be answered.", ["taxpayer.age_dec31", "taxpayer.was_full_time_student_more_than_13_weeks", *[f"refundable_credits.{name}" for name in cwb_facts]], year))
    work_facts = ("work_premium_eligible_status", "quebec_work_premium_full_time_student", "transferred_schedule_s_amount", "family_allowance_received_for_self", "designated_as_dependent_child", "incarcerated_over_183_days")
    if any(getattr(credits, name) is None for name in work_facts):
        problems.append(blocker("missing_work_premium_eligibility", "The annual work-premium eligibility facts must be answered.", [f"refundable_credits.{name}" for name in work_facts], year))
    return problems


def bracket_tax(income: Decimal, brackets: tuple[tuple[Decimal, Decimal], ...]) -> Decimal:
    tax = ZERO
    floor = ZERO
    for ceiling, rate in brackets:
        taxable = min(income, ceiling) - floor
        if taxable > ZERO:
            tax += taxable * rate
        if income <= ceiling:
            break
        floor = ceiling
    return money(tax)


def basic_personal_amount(net_income: Decimal, rules: AnnualRules) -> Decimal:
    if net_income <= rules.federal_bpa_phase_start:
        return rules.federal_bpa_max
    if net_income >= rules.federal_bpa_phase_end:
        return rules.federal_bpa_min
    reduction = (rules.federal_bpa_max - rules.federal_bpa_min) * (net_income - rules.federal_bpa_phase_start) / (rules.federal_bpa_phase_end - rules.federal_bpa_phase_start)
    return money(rules.federal_bpa_max - reduction)


def qpp_amounts(data: TaxReturnInput, rules: AnnualRules, slip_type: str = "T4") -> tuple[Decimal, Decimal, Decimal, Decimal]:
    if slip_type == "T4":
        pensionable = min(sum_box(data, "T4", "26") or sum_box(data, "T4", "14"), rules.qpp_yampe)
        actual_first = sum_box(data, "T4", "17")
        actual_second = sum_box(data, "T4", "17A")
    else:
        pensionable = min(sum_box(data, "RL1", "G") or sum_box(data, "RL1", "A"), rules.qpp_yampe)
        actual_first = sum_box(data, "RL1", "B.A" if rules.year >= 2024 else "B")
        actual_second = sum_box(data, "RL1", "B.B")
    first_earnings = min(max(pensionable - D("3500"), ZERO), rules.qpp_ympe - D("3500"))
    second_earnings = max(pensionable - rules.qpp_ympe, ZERO)
    required_base = money(first_earnings * D(".054"))
    required_first = money(first_earnings * rules.qpp_first_additional_rate)
    required_second = money(second_earnings * D(".04")) if rules.year >= 2024 else ZERO
    ratio = D(".054") / (D(".054") + rules.qpp_first_additional_rate)
    actual_base = money(actual_first * ratio)
    base_credit = min(required_base, actual_base)
    enhanced = min(required_first, max(actual_first - base_credit, ZERO)) + min(required_second, actual_second)
    overpayment = max(money(actual_first + actual_second - required_base - required_first - required_second), ZERO)
    return base_credit, money(enhanced), overpayment, pensionable


def loan_claim(data: TaxReturnInput) -> Decimal:
    loan = data.student_loan_interest
    if loan.federal_claim_amount is not None:
        return money(loan.federal_claim_amount)
    return ZERO


def current_tuition(data: TaxReturnInput) -> Decimal:
    by_school: dict[str, Decimal] = {}
    for slip in slips(data, "T2202"):
        value = slip.fields.get("26")
        if isinstance(value, Decimal):
            by_school[slip.issuer_id] = by_school.get(slip.issuer_id, ZERO) + value
    return money(sum((amount for amount in by_school.values() if amount > D("100")), start=ZERO))


def calculate_annual_federal(data: TaxReturnInput, rules: AnnualRules) -> ScheduleResult:
    source = f"cra_{rules.year}_5005_r"
    employment = sum_box(data, "T4", "14")
    ei_benefits = money(sum((max((s.fields.get("14") if isinstance(s.fields.get("14"), Decimal) else ZERO) - (s.fields.get("18") if isinstance(s.fields.get("18"), Decimal) else ZERO), ZERO) for s in slips(data, "T4E")), start=ZERO))
    pandemic = money(sum((sum((s.fields.get(box) if isinstance(s.fields.get(box), Decimal) else ZERO for box in PANDEMIC_BOXES), start=ZERO) for s in slips(data, "T4A")), start=ZERO))
    resp = sum_box(data, "T4A", "042")
    scholarship = taxable_scholarships(data)
    interest = sum_box(data, "T5", "13")
    total_income = money(employment + ei_benefits + pandemic + resp + scholarship + interest)
    repayment = money((data.pandemic_repayment.federal_claim_allocations_by_tax_year or {}).get(rules.year, ZERO))
    rpp = sum_box(data, "T4", "20")
    union = sum_box(data, "T4", "44")
    rrsp = money(data.rrsp.deduction_requested or ZERO) if data.rrsp.has_contributions else ZERO
    qpp_base, qpp_enhanced, qpp_overpayment, pensionable = qpp_amounts(data, rules)
    deductions = money(rpp + union + rrsp + qpp_enhanced + repayment)
    net_before_repayment = max(money(total_income - deductions), ZERO)
    crb = sum_box(data, "T4A", "202")
    social_benefit_repayment = min(crb, money(max(net_before_repayment - D("38000"), ZERO) * D(".50"))) if rules.year <= 2022 else ZERO
    net_income = max(money(net_before_repayment - social_benefit_repayment), ZERO)
    federal_tax = bracket_tax(net_income, rules.federal_brackets)
    bpa = basic_personal_amount(net_income, rules)
    ei_actual = sum_box(data, "T4", "18")
    ei_earnings = min(sum_box(data, "T4", "24") or employment, rules.ei_max_earnings)
    ei_required = ZERO if ei_earnings <= D("2000") else min(money(ei_earnings * rules.ei_rate), rules.ei_max)
    ei_credit = min(ei_actual, ei_required)
    ei_overpayment = max(money(ei_actual - ei_required), ZERO)
    qpip = min(sum_box(data, "T4", "55"), rules.qpip_max)
    employment_credit = min(employment, rules.employment_amount)
    student_interest = loan_claim(data)
    tuition_current = current_tuition(data) if data.federal_tuition.has_current_tuition else ZERO
    tuition_prior = money(data.federal_tuition.prior_unused_amount or ZERO) if data.federal_tuition.has_prior_unused else ZERO
    ctc = money(data.federal_tuition.canada_training_credit_claim or ZERO) if data.federal_tuition.wants_canada_training_credit else ZERO
    current_after_ctc = max(money(tuition_current - ctc), ZERO)
    tuition_available = money(current_after_ctc + tuition_prior)
    before_tuition = money(bpa + qpp_base + ei_credit + qpip + employment_credit + student_interest)
    tuition_income_equivalent = money(federal_tax / D(".15"))
    tax_room = max(money(tuition_income_equivalent - before_tuition), ZERO)
    prior_tuition_claim = min(tuition_prior, tax_room)
    current_tuition_claim = min(current_after_ctc, max(money(tax_room - prior_tuition_claim), ZERO))
    tuition_claim = money(prior_tuition_claim + current_tuition_claim)
    unused_tuition = money(tuition_available - tuition_claim)
    maximum_transfer = max(money(min(current_after_ctc, D("5000")) - current_tuition_claim), ZERO)
    transfer = money(data.federal_tuition.transfer_amount or ZERO) if data.federal_tuition.wants_transfer else ZERO
    calculation_blockers: list[CompletenessBlocker] = []
    if transfer > maximum_transfer:
        calculation_blockers.append(blocker(
            "federal_tuition_transfer_exceeds_available",
            "The federal tuition transfer exceeds the current-year amount available after the student's claim.",
            ["federal_tuition.transfer_amount"],
            rules.year,
        ))
    tuition_carryforward = max(money(unused_tuition - transfer), ZERO)
    credit_base = money(before_tuition + tuition_claim)
    nrtc = money(credit_base * D(".15"))
    basic_tax = max(money(federal_tax - nrtc), ZERO)
    disqualified_cwb = any((
        data.taxpayer.age_dec31 is None or data.taxpayer.age_dec31 < 19,
        data.taxpayer.was_full_time_student_more_than_13_weeks is True,
        data.refundable_credits.cwb_incarcerated_90_days is True,
        data.refundable_credits.cwb_foreign_officer_exempt is True,
    ))
    gross_cwb = min(money(max(employment + scholarship - D("2400"), ZERO) * rules.cwb_rate), rules.cwb_max)
    cwb = ZERO if disqualified_cwb else max(money(gross_cwb - max(net_income - rules.cwb_reduction_base, ZERO) * D(".20")), ZERO)
    advanced = money((data.refundable_credits.advanced_cwb_paid or ZERO) + (data.refundable_credits.advanced_cwb_disability_paid or ZERO)) if rules.year >= 2023 else ZERO
    advanced_repayment = min(cwb, advanced)
    payable = money(basic_tax + social_benefit_repayment + advanced_repayment)
    withholding = money(sum_box(data, "T4", "22") + sum_box(data, "T4A", "22") + sum_box(data, "T4A", "022") + sum_box(data, "T4E", "22"))
    abatement = money(basic_tax * D(".165"))
    credits = money(withholding + abatement + ei_overpayment + qpp_overpayment + cwb + ctc + (data.instalments.federal_paid or ZERO))
    difference = money(payable - credits)
    refund, balance = (abs(difference), ZERO) if difference < ZERO else (ZERO, difference)
    values = {
        "10100": (employment, "employment_income"), "11900": (ei_benefits, "employment_insurance_benefits"),
        "12100": (interest, "interest_income"), "13000": (pandemic + resp, "other_income"), "13010": (scholarship, "taxable_scholarships"),
        "14700": (ZERO, "benefits_total"), "15000": (total_income, "total_income"), "20600": (sum_box(data, "T4", "52"), "pension_adjustment"), "20700": (rpp, "rpp_deduction"),
        "20800": (rrsp, "rrsp_deduction"), "21200": (union, "union_dues"),
        "22215": (qpp_enhanced, "enhanced_qpp_deduction"), "23200": (repayment if rules.year == 2020 or rules.year >= 2023 else ZERO, "benefit_repayment"),
        "23300": (deductions, "total_deductions"), "23400": (net_before_repayment, "net_income_before_adjustments"),
        "23500": (social_benefit_repayment, "social_benefit_repayment"), "23600": (net_income, "net_income"),
        "25700": (ZERO, "taxable_income_deductions"), "26000": (net_income, "taxable_income"),
        "30000": (bpa, "basic_personal_amount"), "30800": (qpp_base, "qpp_base_credit"),
        "31200": (ei_credit, "ei_credit"), "31205": (qpip, "ppip_credit"),
        "31210": (ZERO, "all_employment_in_quebec"), "31260": (employment_credit, "canada_employment_amount"), "31900": (student_interest, "student_loan_interest"),
        "32300": (tuition_claim, "tuition_claim"), "33500": (credit_base, "nonrefundable_credit_base"),
        "33800": (nrtc, "credits_at_15_percent"), "35000": (nrtc, "total_nonrefundable_credits"),
        "40400": (federal_tax, "federal_tax"), "42900": (basic_tax, "basic_federal_tax"),
        "40600": (basic_tax, "federal_tax_after_credits"), "41600": (ZERO, "other_federal_credits"), "41700": (basic_tax, "federal_tax_after_other_credits"), "41500": (advanced_repayment, "advanced_cwb_repayment"),
        "42000": (payable, "net_federal_tax"), "43500": (payable, "total_payable"),
        "43700": (withholding, "tax_deducted"), "43800": (ZERO, "no_tax_transfer"), "44000": (abatement, "quebec_abatement"),
        "45000": (ei_overpayment, "ei_overpayment"), "45100": (ei_overpayment, "net_ei_overpayment"),
        "45300": (cwb, "canada_workers_benefit"), "45350": (ctc, "canada_training_credit"),
        "47600": (data.instalments.federal_paid or ZERO, "federal_instalments"), "48200": (credits, "total_credits"),
        "48400": (refund, "refund"), "48500": (balance, "balance_owing"),
    }
    if rules.year in (2021, 2022):
        values["23210"] = (repayment, "covid_benefit_repayment")
    if rules.year >= 2022:
        values["43850"] = (withholding, "tax_after_transfer")
    values = {key: item for key, item in values.items() if key in _MAIN_LINES[str(rules.year)]["federal"]}
    lines = {key: line("T1", key, value, source, formula) for key, (value, formula) in values.items()}
    if data.rrsp.has_contributions or data.rrsp.has_prior_unused_contributions:
        prior_rrsp = money(data.rrsp.prior_unused_contributions or ZERO)
        first_period = money(data.rrsp.march_to_december_contributions or ZERO)
        second_period = money(data.rrsp.first_60_days_contributions or ZERO)
        available_rrsp = money(prior_rrsp + first_period + second_period)
        unused_rrsp = money(available_rrsp - rrsp)
        s7 = f"cra_{rules.year}_schedule_7"
        for key, value, formula in (
            ("1", prior_rrsp, "prior_unused_contributions"), ("2", first_period, "march_to_december_contributions"),
            ("3", second_period, "first_60_days_contributions"), ("4", first_period + second_period, "current_contributions"),
            ("5", available_rrsp, "available_contributions"), ("10", available_rrsp, "available_to_deduct"),
            ("11", data.rrsp.deduction_limit or ZERO, "assessed_deduction_limit"), ("17", min(available_rrsp, data.rrsp.deduction_limit or ZERO), "maximum_deduction"),
            ("18", rrsp, "requested_deduction"), ("20", rrsp, "rrsp_deduction"), ("23", unused_rrsp, "unused_contributions"),
        ):
            lines[f"S7:{key}"] = line("T1-S7", key, value, s7, formula)
    if tuition_current or tuition_prior or ctc:
        s11 = f"cra_{rules.year}_schedule_11_qc"
        if rules.year == 2020:
            schedule_11_values = (
                ("1", tuition_prior, "prior_unused_tuition"), ("2", tuition_current, "current_canadian_tuition"),
                ("6", current_after_ctc, "current_canadian_tuition_after_ctc"), ("8", current_after_ctc, "current_tuition_available"),
                ("9", tuition_available, "total_tuition_available"), ("10", tuition_income_equivalent, "taxable_income_or_tax_equivalent"),
                ("11", before_tuition, "nonrefundable_credits_before_tuition"), ("12", tax_room, "tuition_tax_room"),
                ("13", prior_tuition_claim, "prior_tuition_claim"), ("14", max(money(tax_room - prior_tuition_claim), ZERO), "current_tuition_room"),
                ("15", current_tuition_claim, "current_tuition_claim"), ("16", tuition_claim, "tuition_claim"),
                ("17", tuition_available, "total_tuition_available_copy"), ("18", tuition_claim, "tuition_claim_copy"),
                ("19", unused_tuition, "unused_tuition"), ("24", tuition_carryforward, "tuition_carryforward"),
            )
            if data.federal_tuition.wants_canada_training_credit:
                schedule_11_values += (
                    ("3", money(tuition_current * D(".50")), "half_current_tuition"),
                    ("4", money(data.federal_tuition.canada_training_credit_limit or ZERO), "assessed_training_credit_limit"),
                    ("5", ctc, "training_credit_claim"),
                )
            if data.federal_tuition.wants_transfer:
                schedule_11_values += (
                    ("20", min(current_after_ctc, D("5000")), "current_tuition_transfer_base"),
                    ("21", current_tuition_claim, "current_tuition_claim_copy"),
                    ("22", maximum_transfer, "maximum_transferable_tuition"),
                    ("23", transfer, "federal_tuition_transferred"),
                )
        else:
            schedule_11_values = (
                ("1", tuition_prior, "prior_unused_tuition"), ("2", tuition_current, "current_canadian_tuition"),
                ("7", current_after_ctc, "current_canadian_tuition_after_ctc"), ("9", current_after_ctc, "current_tuition_available"),
                ("10", tuition_available, "total_tuition_available"), ("11", tuition_income_equivalent, "taxable_income_or_tax_equivalent"),
                ("12", before_tuition, "nonrefundable_credits_before_tuition"), ("13", tax_room, "tuition_tax_room"),
                ("14", prior_tuition_claim, "prior_tuition_claim"), ("15", max(money(tax_room - prior_tuition_claim), ZERO), "current_tuition_room"),
                ("16", current_tuition_claim, "current_tuition_claim"), ("17", tuition_claim, "tuition_claim"),
                ("18", tuition_available, "total_tuition_available_copy"), ("19", tuition_claim, "tuition_claim_copy"),
                ("20", unused_tuition, "unused_tuition"), ("25", tuition_carryforward, "tuition_carryforward"),
            )
            if data.federal_tuition.wants_canada_training_credit:
                maximum_ctc = min(money(tuition_current * D(".50")), money(data.federal_tuition.canada_training_credit_limit or ZERO))
                schedule_11_values += (
                    ("3", money(tuition_current * D(".50")), "half_current_tuition"),
                    ("4", money(data.federal_tuition.canada_training_credit_limit or ZERO), "assessed_training_credit_limit"),
                    ("5", maximum_ctc, "maximum_training_credit"),
                    ("6", ctc, "training_credit_claim"),
                )
            if data.federal_tuition.wants_transfer:
                schedule_11_values += (
                    ("21", min(current_after_ctc, D("5000")), "current_tuition_transfer_base"),
                    ("22", current_tuition_claim, "current_tuition_claim_copy"),
                    ("23", maximum_transfer, "maximum_transferable_tuition"),
                    ("24", transfer, "federal_tuition_transferred"),
                )
        for key, value, formula in schedule_11_values:
            lines[f"S11:{key}"] = line("T1-S11", key, value, s11, formula)
        lines["S11:32005"] = LineValue(
            form_id="T1-S11", line_id="32005", value=False, status="calculated",
            inputs=["taxpayer.has_disability_or_caregiver_claim"], formula_id="no_disability_enrolment_exception",
            source_ids=[s11], explanation="The Schedule 11 disability or impairment enrolment exception does not apply.",
        )
        lines["S11:32010"] = line("T1-S11", "32010", min(sum_box(data, "T2202", "24"), D("12")), s11, "part_time_enrolment_months")
        lines["S11:32020"] = line("T1-S11", "32020", min(sum_box(data, "T2202", "25"), D("12")), s11, "full_time_enrolment_months")
    if gross_cwb or cwb or advanced:
        s6 = f"cra_{rules.year}_schedule_6_qc"
        lines["S6:20"] = line("T1-S6", "20", gross_cwb, s6, "gross_cwb")
        lines["S6:28"] = line("T1-S6", "28", cwb, s6, "canada_workers_benefit")
        if rules.year >= 2023:
            lines["S6:48"] = line("T1-S6", "48", advanced, s6, "advanced_cwb_paid")
            lines["S6:49"] = line("T1-S6", "49", advanced_repayment, s6, "advanced_cwb_repayment")
    s8_source = f"cra_{rules.year}_schedule_8_qc"
    first_earnings = min(max(pensionable - D("3500"), ZERO), rules.qpp_ympe - D("3500"))
    required_base = money(first_earnings * D(".054"))
    required_first = money(first_earnings * rules.qpp_first_additional_rate)
    actual_first_total = sum_box(data, "T4", "17")
    actual_base = money(actual_first_total * D(".054") / (D(".054") + rules.qpp_first_additional_rate))
    actual_enhanced = money(actual_first_total - actual_base)
    if rules.year < 2024:
        schedule_lines = {
            "A": D("12"), "1": rules.qpp_ympe, "2": pensionable,
            "3": min(rules.qpp_ympe, pensionable), "4": D("3500"), "5": first_earnings,
            "6": actual_first_total, "7": actual_base, "8": actual_enhanced,
            "9": required_base, "10": required_first, "11": money(required_base + required_first),
            "12": actual_first_total, "13": money(required_base + required_first), "14": qpp_overpayment,
        }
    else:
        second_earnings = max(pensionable - rules.qpp_ympe, ZERO)
        actual_second = sum_box(data, "T4", "17A")
        required_second = money(second_earnings * D(".04"))
        base_difference = money(actual_base - required_base)
        first_difference = money(actual_enhanced - required_first)
        second_difference = money(actual_second - required_second)
        total_difference = money(base_difference + first_difference + second_difference)
        schedule_lines = {
            "A": D("12"), "B": rules.qpp_yampe, "C": rules.qpp_ympe, "D": D("3500"), "E": rules.qpp_yampe - rules.qpp_ympe,
            "1": pensionable, "2": min(pensionable, rules.qpp_yampe), "3": rules.qpp_ympe,
            "4": second_earnings, "5": min(pensionable, rules.qpp_ympe), "6": D("3500"), "7": first_earnings,
            "8": actual_first_total, "9": actual_base, "10": actual_enhanced,
            "11": required_base, "12": required_first, "13": money(required_base + required_first),
            "14": actual_second, "15": required_second, "16": actual_base, "17": required_base,
            "18": base_difference, "19": actual_enhanced, "20": required_first,
            "21": first_difference, "22": money(base_difference + first_difference),
            "23": actual_second, "24": required_second, "25": second_difference, "26": total_difference,
        }
        if total_difference > ZERO:
            schedule_lines.update({"27": qpp_base, "28": required_first, "29": required_second, "30": qpp_enhanced})
        else:
            schedule_lines.update({"31": qpp_base, "42": qpp_enhanced})
    lines.update({f"S8:{key}": line("T1-S8", key, value, s8_source, "annual_qpp_schedule") for key, value in schedule_lines.items()})
    return ScheduleResult(schedule_id="T1", lines=lines, blockers=calculation_blockers)


def drug_premium(data: TaxReturnInput, net_income: Decimal, rules: AnnualRules) -> tuple[Decimal, dict[str, LineValue]]:
    source = f"rq_{rules.year}_schedule_k"
    months = set(data.drug_insurance.group_plan_months or set()) | set(data.drug_insurance.eligible_student_months or set())
    if net_income <= rules.drug_exemption or months == set(range(1, 13)):
        return ZERO, {"K:90": line("TP1-K", "90", ZERO, source, "full_year_or_low_income_exemption")}
    income_used = money(net_income - rules.drug_exemption)
    first = min(income_used, D("5000"))
    second = min(max(income_used - D("5000"), ZERO), rules.drug_second_threshold - D("5000"))
    amount = money(first * rules.drug_rates[0] + second * rules.drug_rates[1])
    if income_used > rules.drug_second_threshold:
        amount = rules.drug_cap
    preliminary = min(amount, rules.drug_cap)
    first_half_months = len(months & set(range(1, 7)))
    second_half_months = len(months & set(range(7, 13)))
    exempt_months = first_half_months + second_half_months
    line85 = money(preliminary * D(str(exempt_months)) / D("12"))
    line86 = max(money(preliminary - line85), ZERO)
    first_half_rate, second_half_rate = DRUG_MONTHLY_MAX_REDUCTIONS[rules.year]
    line88 = money(D(str(first_half_months)) * first_half_rate + D(str(second_half_months)) * second_half_rate)
    line89 = max(money(rules.drug_annual_max - line88), ZERO)
    premium = min(line86, line89)
    values = {
        "48": (income_used, "income_used"), "83": (preliminary, "premium_cap"),
        "84": (preliminary, "premium_cap_copy"), "60": (D(str(first_half_months)), "first_half_exempt_months"),
        "61": (D(str(second_half_months)), "second_half_exempt_months"), "62": (D(str(exempt_months)), "total_exempt_months"),
        "85": (line85, "premium_exempt_month_proration"), "86": (line86, "premium_after_month_proration"),
        "87": (rules.drug_annual_max, "annual_maximum_premium"), "88": (line88, "monthly_maximum_reduction"),
        "89": (line89, "annual_maximum_after_month_reduction"), "90": (premium, "annual_premium"),
    }
    return premium, {f"K:{key}": line("TP1-K", key, value, source, formula) for key, (value, formula) in values.items()}


def calculate_annual_quebec(data: TaxReturnInput, rules: AnnualRules, federal: ScheduleResult) -> ScheduleResult:
    source = f"rq_{rules.year}_tp1"
    employment = sum_box(data, "RL1", "A")
    interest = sum_box(data, "RL3", "D")
    employment_insurance = money(sum_box(data, "T4E", "14") - sum_box(data, "T4E", "18"))
    pandemic = sum_box(data, "T4A", "197") + sum_box(data, "T4A", "198") + sum_box(data, "T4A", "199") + sum_box(data, "T4A", "200") + sum_box(data, "T4A", "202") + sum_box(data, "T4A", "203") + sum_box(data, "T4A", "204") + sum_box(data, "T4A", "211")
    scholarship_income = sum_rl1_allocations(data, {"RB", "RZ-RB"})
    resp_income = sum_rl1_allocations(data, {"RU", "RZ-RU"})
    other_income = money(pandemic + scholarship_income + resp_income)
    total_income = money(employment + employment_insurance + interest + other_income)
    worker = min(money(max(employment - sum_box(data, "RL1", "211"), ZERO) * D(".06")), rules.worker_deduction_cap)
    rpp = sum_box(data, "RL1", "D")
    rrsp = money(data.rrsp.deduction_requested or ZERO) if data.rrsp.has_contributions else ZERO
    _, enhanced, qpp_overpayment, _ = qpp_amounts(data, rules, "RL1")
    pandemic_repayment = money(data.pandemic_repayment.quebec_claim_amount or ZERO)
    deductions = money(worker + rpp + rrsp + enhanced + pandemic_repayment)
    net_income = max(money(total_income - deductions), ZERO)
    taxable_income = max(money(net_income - scholarship_income), ZERO)
    gross_tax = bracket_tax(taxable_income, rules.quebec_brackets)
    living = ZERO
    if data.quebec_schedule_b.eligible_for_living_alone_amount:
        living = max(money(rules.living_alone_amount - max(net_income - rules.living_alone_threshold, ZERO) * D(".1875")), ZERO)
    personal_base = money(rules.quebec_bpa + living)
    basic_credit = money(personal_base * rules.quebec_credit_rate)
    loan = money(data.student_loan_interest.quebec_claim_amount or ZERO)
    loan_credit = money(loan * D(".20"))
    union = sum_box(data, "RL1", "F")
    union_credit = money(union * D(".10"))
    current_fees = money(data.quebec_tuition.eligible_tuition_or_exam_receipts or ZERO) if data.quebec_tuition.has_current_tuition else ZERO
    federal_ctc = federal.lines["45350"].value
    assert isinstance(federal_ctc, Decimal)
    prior_tuition_20 = money(data.quebec_tuition.prior_unused_at_20_percent or ZERO)
    prior_tuition_8 = money(data.quebec_tuition.prior_unused_at_8_percent or ZERO)
    available_tuition_20 = money(prior_tuition_20 * D(".20"))
    current_fees_after_ctc = max(money(current_fees - federal_ctc), ZERO)
    transfer_credit = money(data.quebec_tuition.transfer_amount or ZERO) if data.quebec_tuition.wants_transfer else ZERO
    transfer_credit_base = money(current_fees_after_ctc * D(".08"))
    transfer_tax_room = max(money(gross_tax - basic_credit - union_credit), ZERO)
    maximum_transfer_credit = max(money(transfer_credit_base - transfer_tax_room), ZERO)
    calculation_blockers: list[CompletenessBlocker] = []
    if transfer_credit > maximum_transfer_credit:
        calculation_blockers.append(blocker(
            "quebec_tuition_transfer_exceeds_available",
            "The Quebec tuition-credit transfer exceeds the current-year amount available after the student's tax requirement.",
            ["quebec_tuition.transfer_amount"],
            rules.year,
        ))
    transferred_fees = money(transfer_credit * D("12.5"))
    current_fees_after_transfer = max(money(current_fees_after_ctc - transferred_fees), ZERO)
    available_tuition_8_fees = money(current_fees_after_transfer + prior_tuition_8)
    available_tuition_8 = money(available_tuition_8_fees * D(".08"))
    tuition_room = max(money(gross_tax - basic_credit - loan_credit - union_credit), ZERO)
    claimed_tuition_20 = min(available_tuition_20, tuition_room)
    claimed_tuition_8 = min(available_tuition_8, max(money(tuition_room - claimed_tuition_20), ZERO))
    tuition = money(claimed_tuition_20 + claimed_tuition_8)
    unused_tuition_20 = money((available_tuition_20 - claimed_tuition_20) * D("5"))
    unused_tuition_8 = money((available_tuition_8 - claimed_tuition_8) * D("12.5"))
    credits = money(basic_credit + loan_credit + union_credit + tuition)
    tax_after = max(money(gross_tax - credits), ZERO)
    drug, schedule_k = drug_premium(data, net_income, rules)
    rc = data.refundable_credits
    eligible_work = all((rc.work_premium_eligible_status is True, rc.transferred_schedule_s_amount is False, rc.family_allowance_received_for_self is False, rc.designated_as_dependent_child is False, rc.incarcerated_over_183_days is False, rc.quebec_work_premium_full_time_student is False))
    gross_work = money(max(min(employment, rules.work_premium_cap) - D("2400"), ZERO) * rules.work_premium_rate)
    work_reduction = money(max(net_income - rules.work_premium_cap, ZERO) * D(".10"))
    work_premium = max(money(gross_work - work_reduction), ZERO) if eligible_work else ZERO
    qpip_paid = sum_box(data, "RL1", "H")
    qpip_earnings = sum_box(data, "RL1", "I") or employment
    qpip_overpayment = qpip_paid if qpip_earnings < D("2000") else max(money(qpip_paid - rules.qpip_max), ZERO)
    f_threshold, f_upper = SCHEDULE_F_THRESHOLDS[rules.year]
    f_income = max(money(total_income - employment - scholarship_income), ZERO)
    if f_income <= f_threshold:
        health_fund = ZERO
    elif f_income <= f_upper:
        health_fund = min(money((f_income - f_threshold) * D(".01")), D("150"))
    else:
        health_fund = min(money(D("150") + (f_income - f_upper) * D(".01")), D("1000"))
    payable = money(tax_after + drug + health_fund + (rc.rl19_box_a or ZERO) + (rc.rl19_box_b or ZERO))
    qc_withheld = money(sum_box(data, "RL1", "E") + sum_box(data, "T4E", "23"))
    paid = money(qc_withheld + (data.instalments.quebec_paid or ZERO) + qpp_overpayment + qpip_overpayment + work_premium)
    difference = money(payable - paid)
    refund, balance = (abs(difference), ZERO) if difference < ZERO else (ZERO, ZERO if difference < D("2") else difference)
    paid_qpp = sum_box(data, "RL1", "B.A" if rules.year >= 2024 else "B")
    values = {
        "97": (qpip_paid, "qpip_premium"), "98": (paid_qpp, "qpp_contribution"),
        "98.2": (sum_box(data, "RL1", "B.B"), "second_qpp_contribution"), "101": (employment, "employment_income"),
        "111": (employment_insurance, "employment_insurance_benefits"), "130": (interest, "interest_income"), "154": (other_income, "other_income"), "199": (total_income, "total_income"),
        "201": (worker, "worker_deduction"), "205": (rpp, "rpp_deduction"), "214": (rrsp, "rrsp_deduction"),
        "246": (pandemic_repayment, "pandemic_benefit_repayment"), "248": (enhanced, "enhanced_qpp_deduction"), "254": (deductions, "total_deductions"),
        "256": (net_income, "income_after_deductions"), "275": (net_income, "net_income"), "279": (net_income, "adjusted_net_income"), "295": (scholarship_income, "scholarship_deduction"), "298": (scholarship_income, "taxable_income_deductions"), "299": (taxable_income, "taxable_income"),
        "350": (rules.quebec_bpa, "basic_personal_amount"), "358": (ZERO, "no_income_replacement_adjustment"), "359": (rules.quebec_bpa, "adjusted_basic_personal_amount"),
        "361": (living, "living_alone_amount"), "377": (personal_base, "personal_credit_base"), "377.1": (basic_credit, "personal_credit"),
        "385": (loan, "student_loan_interest"), "389": (loan_credit, "student_loan_credit_20_percent"),
        "397": (union_credit, "union_dues_credit"), "398": (tuition, "tuition_credit"), "399": (credits, "nonrefundable_credits"),
        "401": (gross_tax, "quebec_tax"), "406": (credits, "nonrefundable_credit_copy"), "413": (tax_after, "tax_after_credits"),
        "425": (ZERO, "no_other_tax_credits"), "430": (tax_after, "tax_after_other_credits"), "431": (ZERO, "no_spousal_transfer"),
        "432": (tax_after, "income_tax"), "441": (money((rc.rl19_box_a or ZERO) + (rc.rl19_box_b or ZERO)), "advance_work_premium_payments"), "446": (health_fund, "health_services_fund"), "447": (drug, "drug_insurance_premium"),
        "450": (payable, "tax_and_contributions"), "451": (qc_withheld, "tax_withheld"), "451.2": (qc_withheld, "tax_withheld_after_schedule_q"), "452": (qpp_overpayment, "qpp_overpayment"),
        "456": (work_premium, "work_premium"), "457": (qpip_overpayment, "qpip_overpayment"),
        "465": (paid, "payments_and_credits"), "466": (data.instalments.quebec_paid or ZERO, "quebec_instalments"), "468": (paid, "total_payments"), "470": (difference, "difference"),
        "474": (refund, "negative_difference"), "475": (balance, "positive_difference"), "476": (ZERO, "refund_transfer"), "477": (refund, "refund_before_transfer"), "478": (refund, "refund"), "479": (balance, "balance_owing"),
        "498": (balance, "balance_owing_copy"), "499": (ZERO, "no_interest_or_penalty"),
    }
    values = {key: item for key, item in values.items() if key in _MAIN_LINES[str(rules.year)]["quebec"]}
    lines = {key: line("TP1", key, value, source, formula) for key, (value, formula) in values.items()}
    schedule_sources = {
        "B:34": (living, "living_alone_amount", "b"),
        "M:46": (money(data.student_loan_interest.quebec_prior_unused or ZERO), "prior_student_loan_interest", "m"),
        "M:52": (money(data.student_loan_interest.quebec_current_year_paid or ZERO), "current_student_loan_interest", "m"),
        "M:54": (money((data.student_loan_interest.quebec_prior_unused or ZERO) + (data.student_loan_interest.quebec_current_year_paid or ZERO)), "available_student_loan_interest", "m"),
        "M:60": (loan, "student_loan_claim", "m"),
        "M:62": (money((data.student_loan_interest.quebec_prior_unused or ZERO) + (data.student_loan_interest.quebec_current_year_paid or ZERO) - loan), "student_loan_carryforward", "m"),
        "P:76": (gross_work, "gross_work_premium", "p"), "P:83": (work_reduction, "work_premium_reduction", "p"),
        "P:90": (work_premium, "work_premium", "p"),
        "T:34": (prior_tuition_20, "prior_20_percent_tuition_fees", "t"),
        "T:38": (claimed_tuition_20, "claimed_20_percent_tuition_credit", "t"),
        "T:40": (unused_tuition_20, "unused_20_percent_tuition_fees", "t"),
        "T:40.5": (D("1") if data.quebec_tuition.institution_outside_quebec else ZERO, "institution_outside_quebec", "t"),
        "T:40.6": (current_fees, "current_tuition_fees", "t"),
        "T:40.7": (federal_ctc, "canada_training_credit_refund", "t"),
        "T:41": (current_fees_after_ctc, "current_fees_after_training_credit", "t"),
        "T:42": (transferred_fees, "transferred_tuition_fee_equivalent", "t"),
        "T:43": (current_fees_after_transfer, "current_fees_after_transfer", "t"),
        "T:44": (prior_tuition_8, "prior_8_percent_tuition_fees", "t"),
        "T:44.1": (available_tuition_8_fees, "available_8_percent_tuition_fees", "t"),
        "T:45": (available_tuition_8, "available_8_percent_tuition_credit", "t"),
        "T:46": (claimed_tuition_8, "claimed_8_percent_tuition_credit", "t"),
        "T:47": (money(available_tuition_8 - claimed_tuition_8), "unused_8_percent_tuition_credit", "t"),
        "T:48": (unused_tuition_8, "unused_8_percent_tuition_fees", "t"),
    }
    if data.quebec_tuition.wants_transfer:
        schedule_sources.update({
            "T:51": (current_fees_after_ctc, "current_fees_available_for_transfer", "t"),
            "T:52": (transfer_credit_base, "current_tuition_transfer_credit_base", "t"),
            "T:53": (gross_tax, "quebec_tax_before_credits", "t"),
            "T:54": (ZERO, "medical_expense_credit_base", "t"),
            "T:56": (ZERO, "medical_expense_credit", "t"),
            "T:58": (money(basic_credit + union_credit), "other_nonrefundable_credits", "t"),
            "T:60": (money(basic_credit + union_credit), "credits_before_tuition_transfer", "t"),
            "T:62": (transfer_tax_room, "tax_requirement_before_tuition", "t"),
            "T:66": (maximum_transfer_credit, "maximum_transferable_tuition_credit", "t"),
            "T:68": (transfer_credit, "tuition_credit_transferred", "t"),
        })
    lines.update({key: line(f"TP1-{key[0]}", key.split(":", 1)[1], value, f"rq_{rules.year}_schedule_{schedule}", formula) for key, (value, formula, schedule) in schedule_sources.items()})
    lines.update(schedule_k)
    f_source = f"rq_{rules.year}_schedule_f"
    lines["F:10"] = line("TP1-F", "10", total_income, f_source, "total_income")
    lines["F:18"] = line("TP1-F", "18", money(total_income - employment), f_source, "income_after_employment_exclusion")
    lines["F:30"] = line("TP1-F", "30", scholarship_income, f_source, "scholarship_exclusion")
    lines["F:70"] = line("TP1-F", "70", f_income, f_source, "income_subject_to_contribution")
    lines["F:82"] = line("TP1-F", "82", health_fund, f_source, "health_services_fund_contribution")
    if rules.year >= 2024:
        lines["U:23"] = line("TP1-U", "23", enhanced, f"rq_{rules.year}_schedule_u", "enhanced_qpp_deduction")
    return ScheduleResult(schedule_id="TP1", lines=lines, blockers=calculation_blockers)

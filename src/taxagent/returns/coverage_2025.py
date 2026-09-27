"""2025 T1 and TP-1 printed-line coverage for the bounded engine.

Membership and printed-row completion are maintained against the published
2025 CRA 5005-R E and Revenu Quebec TP-1.D-V forms and LINE_LABELS_2025.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from .models import CompletenessBlocker, LineValue, TaxReturnInput


ZERO = Decimal("0.00")
CENT = Decimal("0.01")
T1_SOURCE = "cra_2025_5005_r"
TP1_SOURCE = "rq_2025_tp1"
ROUNDING_ID = "cra_2025_money_cents_half_up"

T1_INCOME = frozenset(
    "10100 10105 10120 10130 10400 11300 11400 11410 11500 11600 11700 11701 11900 11905 12000 12010 12100 12200 12500 12599 12600 12700 12799 12800 12900 12905 12906 13000 13010 13499 13500 13699 13700 13899 13900 14099 14100 14299 14300 14400 14500 14600 14700 15000".split()
)
T1_DEDUCTIONS = frozenset(
    "20600 20700 20800 20805 20810 21000 21200 21300 21400 21500 21699 21700 21900 21999 22000 22100 22200 22215 22300 22400 22900 23100 23200 23300 23400 23500 23600 24400 24900 25000 25100 25200 25300 25395 25400 25500 25600 25700 26000".split()
)
T1_CREDITS = frozenset(
    "30000 30100 30300 30400 30425 30450 30499 30500 30800 31000 31200 31217 31205 31210 31215 31220 31240 31260 31270 31285 31300 31400 31600 31800 31900 32300 32400 32600 33099 33199 33200 33500 33800 34900 34990 35000 40424 40400 40425 40427 42900 40500 40600 40900 41000 41200 41300 41400 41600 41700 41500 41800 42000 42120 42200 42800 43500 43700 43800 43850 44000 45000 45100 45200 45300 45350 45355 45400 45600 45700 46800 46900 47555 47556 47600 48200 48400 48500".split()
)
T1_PRINTED = tuple(str(number) for number in range(71, 173))
T1_ALWAYS = frozenset(
    "10100 14700 15000 23300 23400 23500 23600 25700 26000 30000 33500 33800 35000 40400 42900 40600 41600 41700 42000 43500 43850 45100 48200 48400 48500".split()
)

TP1_INCOME = frozenset(
    "96 96.1 96.2 97 98 98.1 98.2 100 102 101 105 165 106 107 110 111 114 119 122 123 166 167 128 130 168 136 139 142 147 149 148 169 153 154 164 199".split()
)
TP1_DEDUCTIONS = frozenset(
    "201 205 206 207 212 214 215 225 228 231 233 234 236 241 245 246 248.1 248 249 250 252 254 256 260 275 277 276 278 279 286 287 289.1 289 290 291 292 293 295 296 297 298 299".split()
)
TP1_CREDITS = frozenset(
    "350 358 359 361 367 376 377 377.1 378 381 385 388 389 390.1 390 391 392 393 395 396 397.1 397 398 398.1 399 403 401 404 405 406 413 414 415 422 424 425 430 431 432 438 439 441 442 443 444 445 446 449 447 450 451 451.1 451.2 451.3 452 453 454 455 456 457 458 459 460 461 462 463 465 466 468 470 474 475 476 477 478 479 480 481".split()
)
TP1_ALWAYS = frozenset(
    "199 254 256 275 279 298 299 350 358 359 377 377.1 388 389 399 401 406 413 425 430 432 446 447 450 451.2 465 468 470 474 475 478 479".split()
)


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _line(
    form_id: str,
    line_id: str,
    value: Decimal,
    formula_id: str,
    inputs: tuple[str, ...] = (),
    preserve_exact: bool = False,
) -> LineValue:
    if not preserve_exact:
        value = _money(value)
    return LineValue(
        form_id=form_id,
        line_id=line_id,
        value=value,
        status="zero" if value == ZERO else "calculated",
        inputs=list(inputs),
        formula_id=formula_id,
        source_ids=[T1_SOURCE if form_id == "T1" else TP1_SOURCE],
        rounding_id=ROUNDING_ID,
        explanation=f"{form_id} line {line_id}: official 2025 main-form calculation row.",
    )


def _na(form_id: str, line_id: str, group: str) -> LineValue:
    special_reasons = {
        ("TP1", "438"): "The enterprise-registration screen confirms that no annual registration fee applies.",
        ("TP1", "480"): "An accelerated-refund filing election is outside this no-submission preparation packet.",
        ("TP1", "481"): "An enclosed payment is a filing field outside this no-submission preparation packet.",
    }
    return LineValue(
        form_id=form_id,
        line_id=line_id,
        status="not_applicable",
        source_ids=[T1_SOURCE if form_id == "T1" else TP1_SOURCE],
        explanation=special_reasons.get(
            (form_id, line_id),
            f"The {group} inventory was reviewed and no fact made this line applicable.",
        ),
    )


def _blocked(form_id: str, line_id: str, group: str) -> LineValue:
    return LineValue(
        form_id=form_id,
        line_id=line_id,
        status="blocked",
        source_ids=[T1_SOURCE if form_id == "T1" else TP1_SOURCE],
        explanation=f"Applicability is unknown until the {group} inventory is reviewed.",
    )


def _has_positive(value: object) -> bool:
    return isinstance(value, (Decimal, int)) and not isinstance(value, bool) and value != 0


def _slip_has(data: TaxReturnInput, slip_type: str, *boxes: str) -> bool:
    return any(
        slip.slip_type == slip_type
        and any(_has_positive(slip.fields.get(box)) for box in boxes)
        for slip in data.slips
    )


def _known_applicable(
    data: TaxReturnInput,
    form_id: str,
    line_id: str,
    current: dict[tuple[str, str], LineValue],
) -> bool:
    existing = current.get((form_id, line_id))
    if existing is not None and _has_positive(existing.value):
        return True
    forms = {line.form_id for line in current.values()}
    employed = any(slip.slip_type == "T4" for slip in data.slips)
    qc_employed = any(slip.slip_type == "RL1" and "A" in slip.fields for slip in data.slips)
    if form_id == "T1":
        checks = {
            "20600": _slip_has(data, "T4", "52") or _slip_has(data, "T4A", "034"),
            "20700": _slip_has(data, "T4", "20") or _slip_has(data, "T4A", "032"),
            "20800": "T1-S7" in forms,
            "21200": _slip_has(data, "T4", "44"),
            "21900": data.taxpayer.has_moving_expenses is True,
            "10400": data.taxpayer.has_tips_or_other_employment_income is True,
            "22215": "T1-S8" in forms and employed,
            "30800": "T1-S8" in forms and employed,
            "31200": employed,
            "31205": _slip_has(data, "T4", "55"),
            "31210": employed,
            "31260": employed,
            "31900": data.taxpayer.has_student_loan_interest is True,
            "32300": data.federal_tuition.has_current_tuition is True
            or data.federal_tuition.has_prior_unused is True,
            "43800": data.taxpayer.full_year_quebec_resident is True
            and _slip_has(data, "T4", "22"),
            "45000": employed,
            "45300": "T1-S6" in forms,
            "45350": data.federal_tuition.wants_canada_training_credit is True,
            "47600": bool(data.instalments.federal_paid),
        }
        return checks.get(line_id, False)
    checks = {
        "97": _slip_has(data, "RL1", "H"),
        "98": _slip_has(data, "RL1", "B.A"),
        "98.1": _slip_has(data, "RL1", "G"),
        "98.2": _slip_has(data, "RL1", "B.B"),
        "101": qc_employed,
        "106": data.taxpayer.has_tips_or_other_employment_income is True,
        "107": data.taxpayer.has_tips_or_other_employment_income is True,
        "130": _slip_has(data, "RL3", "D"),
        "153": any(
            slip.slip_type == "RL1" and bool(slip.rl1_box_o_allocations)
            for slip in data.slips
        ),
        "154": any(
            slip.slip_type == "RL1" and bool(slip.rl1_box_o_allocations)
            for slip in data.slips
        ),
        "201": qc_employed,
        "205": _slip_has(data, "RL1", "D"),
        "214": "TP1-S7" in forms or bool(data.rrsp.deduction_requested),
        "228": data.taxpayer.has_moving_expenses is True,
        "248": "TP1-U" in forms and qc_employed,
        "295": bool(data.scholarships.awards),
        "361": "TP1-B" in forms,
        "385": "TP1-M" in forms,
        "397.1": _slip_has(data, "RL1", "F"),
        "397": _slip_has(data, "RL1", "F"),
        "398": data.quebec_tuition.has_current_tuition is True
        or data.quebec_tuition.has_prior_unused is True,
        "441": bool(data.refundable_credits.rl19_box_a or data.refundable_credits.rl19_box_b),
        "452": "T1-S8" in forms and qc_employed,
        "453": bool(data.instalments.quebec_paid),
        "456": "TP1-P" in forms,
        "457": _slip_has(data, "RL1", "H"),
    }
    return checks.get(line_id, False)


def _group(data: TaxReturnInput, form_id: str, line_id: str) -> tuple[str, bool]:
    if (form_id, line_id) in {("T1", "21900"), ("TP1", "228")}:
        return "moving-expense", data.taxpayer.has_moving_expenses is not None
    if (form_id, line_id) in {("T1", "10400"), ("TP1", "106"), ("TP1", "107")}:
        return (
            "tips-or-other-employment-income",
            data.taxpayer.has_tips_or_other_employment_income is not None,
        )
    if line_id in (T1_INCOME if form_id == "T1" else TP1_INCOME):
        return "income", data.inventory.income_sources_reviewed is True
    if line_id in (T1_DEDUCTIONS if form_id == "T1" else TP1_DEDUCTIONS):
        return "deduction", data.inventory.deductions_reviewed is True
    return "credit", data.inventory.credits_reviewed is True


def _amount(lines: dict[tuple[str, str], LineValue], form_id: str, line_id: str) -> Decimal:
    line = lines.get((form_id, line_id))
    if line is None:
        return ZERO
    return line.value if isinstance(line.value, Decimal) else ZERO


def _derive_named(
    form_id: str,
    line_id: str,
    lines: dict[tuple[str, str], LineValue],
) -> LineValue | None:
    if (form_id, line_id) in lines:
        return lines[(form_id, line_id)]
    if form_id == "T1" and line_id == "14700":
        return _line("T1", "14700", sum((_amount(lines, "T1", item) for item in ("14400", "14500", "14600")), start=ZERO), "benefits_total", ("14400", "14500", "14600"))
    if form_id == "T1" and line_id == "41600":
        return _line("T1", "41600", sum((_amount(lines, "T1", item) for item in ("41000", "41200", "41400")), start=ZERO), "federal_other_credits_total", ("41000", "41200", "41400"))
    if form_id == "TP1" and line_id == "358":
        return _line("TP1", "358", ZERO, "no_income_replacement_adjustment")
    if form_id == "TP1" and line_id == "279":
        return _line("TP1", "279", _amount(lines, "TP1", "275") + _amount(lines, "TP1", "276"), "adjusted_net_income_subtotal", ("275", "276"))
    return None


def _complete_named(
    data: TaxReturnInput,
    current: dict[tuple[str, str], LineValue],
) -> tuple[dict[tuple[str, str], LineValue], list[CompletenessBlocker]]:
    completed = dict(current)
    blockers: list[CompletenessBlocker] = []
    manifests = (
        ("T1", T1_INCOME | T1_DEDUCTIONS | T1_CREDITS, T1_ALWAYS),
        ("TP1", TP1_INCOME | TP1_DEDUCTIONS | TP1_CREDITS, TP1_ALWAYS),
    )
    completed.pop(("TP1", "154.code"), None)
    if ("TP1", "153") not in completed and ("TP1", "154.code") in current:
        completed[("TP1", "153")] = current[("TP1", "154.code")].model_copy(
            update={"line_id": "153"}
        )
    for form_id, manifest, always in manifests:
        for line_id in manifest:
            key = (form_id, line_id)
            if line_id in always:
                derived = _derive_named(form_id, line_id, completed)
                if derived is None:
                    completed[key] = _blocked(form_id, line_id, "required calculation")
                    blockers.append(
                        CompletenessBlocker(
                            code="missing_main_form_calculation",
                            message=f"{form_id} line {line_id} is always required but has no calculation.",
                            input_paths=[],
                            source_ids=[T1_SOURCE if form_id == "T1" else TP1_SOURCE],
                            resolution="Implement the official main-form calculation before completing the return.",
                        )
                    )
                else:
                    completed[key] = derived
                continue
            group, reviewed = _group(data, form_id, line_id)
            if _known_applicable(data, form_id, line_id, current):
                if key not in completed:
                    completed[key] = _blocked(form_id, line_id, group)
                    blockers.append(
                        CompletenessBlocker(
                            code="missing_applicable_main_form_calculation",
                            message=f"{form_id} line {line_id} applies but has no calculation.",
                            source_ids=[T1_SOURCE if form_id == "T1" else TP1_SOURCE],
                            resolution="Implement the applicable official line calculation.",
                        )
                    )
            elif reviewed:
                completed[key] = _na(form_id, line_id, group)
            else:
                completed[key] = _blocked(form_id, line_id, group)
                if not any(blocker.code == f"unknown_{group}_applicability" for blocker in blockers):
                    blockers.append(
                        CompletenessBlocker(
                            code=f"unknown_{group}_applicability",
                            message=f"Main-form {group} applicability has not been established.",
                            input_paths=[
                                {
                                    "moving-expense": "taxpayer.has_moving_expenses",
                                    "tips-or-other-employment-income": "taxpayer.has_tips_or_other_employment_income",
                                }.get(
                                    group,
                                    f"inventory.{group}_sources_reviewed"
                                    if group == "income"
                                    else f"inventory.{group}s_reviewed",
                                )
                            ],
                            source_ids=[T1_SOURCE, TP1_SOURCE],
                            resolution=f"Review the complete {group} inventory.",
                        )
                    )
    return completed, blockers


def _federal_printed_rows(lines: dict[tuple[str, str], LineValue]) -> dict[tuple[str, str], LineValue]:
    value = lambda line_id: _amount(lines, "T1", line_id)
    taxable = value("26000")
    brackets = (
        (Decimal("253414"), Decimal("0.33"), Decimal("58399.85")),
        (Decimal("177882"), Decimal("0.29"), Decimal("36495.57")),
        (Decimal("114750"), Decimal("0.26"), Decimal("20081.25")),
        (Decimal("57375"), Decimal("0.205"), Decimal("8319.38")),
        (ZERO, Decimal("0.145"), ZERO),
    )
    floor, rate, base = next(item for item in brackets if taxable > item[0] or item[0] == ZERO)
    rows: dict[str, Decimal] = {
        "71": taxable,
        "72": floor,
        "73": max(taxable - floor, ZERO),
        "74": rate,
        "76": base,
    }
    rows["75"] = _money(rows["73"] * rate)
    rows["77"] = _money(rows["75"] + rows["76"])
    for row, named in {
        "78": "30000", "79": "30100", "80": "30300", "81": "30400", "82": "30425", "83": "30450", "84": "30500",
        "87": "30800", "88": "31000", "89": "31200", "90": "31217", "91": "31205", "92": "31210", "93": "31215", "94": "31220", "95": "31240", "96": "31260", "97": "31270", "98": "31285", "99": "31300",
        "101": "31400", "103": "31600", "104": "31800", "106": "31900", "107": "32300", "108": "32400", "109": "32600", "111": "33099", "115": "33199", "120": "34900", "121": "34990",
        "124": "40424", "126": "35000", "127": "40425", "128": "40427", "133": "40500", "139": "41000", "140": "41200", "141": "41400", "144": "41500", "145": "41800", "147": "42000", "148": "42120", "149": "42200", "150": "42800",
        "152": "43500", "153": "43700", "154": "43800", "156": "44000", "157": "45000", "158": "31210", "160": "45200", "161": "45300", "162": "45350", "163": "45355", "164": "45400", "165": "45600", "166": "45700", "167": "46900", "168": "47555", "169": "47556", "170": "47600",
    }.items():
        rows[row] = value(named)
    rows.update(
        {
            "85": sum((rows[str(i)] for i in range(78, 85)), start=ZERO),
            "86": ZERO,
            "100": sum((rows[str(i)] for i in range(87, 100)), start=ZERO),
        }
    )
    rows["86"] = rows["85"]
    rows["102"] = rows["86"] + rows["100"] + rows["101"]
    rows["105"] = rows["102"] + rows["103"] + rows["104"]
    rows["110"] = sum((rows[str(i)] for i in range(105, 110)), start=ZERO)
    rows["112"] = _money(value("23600") * Decimal("0.03"))
    rows["113"] = min(Decimal("2834.00"), rows["112"])
    rows["114"] = max(rows["111"] - rows["113"], ZERO)
    rows["116"] = rows["114"] + rows["115"]
    rows["117"] = rows["110"] + rows["116"]
    rows["118"] = Decimal("0.145")
    rows["119"] = _money(rows["117"] * rows["118"])
    rows["122"] = rows["119"] + rows["120"] + rows["121"]
    rows["123"] = rows["77"]
    rows["125"] = rows["123"] + rows["124"]
    rows["129"] = rows["126"] + rows["127"] + rows["128"]
    rows["130"] = max(rows["125"] - rows["129"], ZERO)
    rows["131"] = ZERO
    rows["132"] = rows["130"] + rows["131"]
    rows["134"] = rows["132"] - rows["133"]
    rows["135"] = ZERO
    rows["136"] = rows["134"] + rows["135"]
    rows["137"] = ZERO
    rows["138"] = max(rows["136"] - rows["137"], ZERO)
    rows["142"] = rows["139"] + rows["140"] + rows["141"]
    rows["143"] = max(rows["138"] - rows["142"], ZERO)
    rows["146"] = rows["143"] + rows["144"] + rows["145"]
    rows["151"] = rows["147"] + rows["148"] + rows["149"] + rows["150"]
    rows["155"] = rows["153"] - rows["154"]
    rows["159"] = max(rows["157"] - rows["158"], ZERO)
    rows["171"] = rows["155"] + rows["156"] + sum((rows[str(i)] for i in range(159, 171)), start=ZERO)
    rows["172"] = rows["152"] - rows["171"]
    return {
        ("T1", line_id): _line(
            "T1",
            line_id,
            rows[line_id],
            f"t1_printed_row_{line_id}",
            preserve_exact=line_id in {"74", "118"},
        )
        for line_id in T1_PRINTED
    }


def complete_main_form_coverage(
    data: TaxReturnInput,
    lines: Iterable[LineValue],
) -> tuple[list[LineValue], list[CompletenessBlocker]]:
    """Return exact main-form membership plus schedules, with no silent omissions."""

    current = {(line.form_id, line.line_id): line for line in lines}
    schedules = [line for line in current.values() if line.form_id not in {"T1", "TP1"}]
    completed, blockers = _complete_named(data, current)
    if not any(
        line.status == "blocked" and line.line_id in T1_ALWAYS
        for line in completed.values()
        if line.form_id == "T1"
    ):
        completed.update(_federal_printed_rows(completed))
    else:
        completed.update({("T1", row): _blocked("T1", row, "required calculation") for row in T1_PRINTED})
    main = [
        completed[("T1", line_id)]
        for line_id in sorted(T1_INCOME | T1_DEDUCTIONS | T1_CREDITS, key=lambda item: (len(item), item))
    ]
    main.extend(completed[("T1", row)] for row in T1_PRINTED)
    main.extend(
        completed[("TP1", line_id)]
        for line_id in sorted(TP1_INCOME | TP1_DEDUCTIONS | TP1_CREDITS, key=lambda item: (float(item) if item.replace('.', '', 1).isdigit() else 9999, item))
    )
    return [*main, *schedules], blockers

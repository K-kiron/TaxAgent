"""Run golden scenarios against the live reasoner and report a two-layer grade."""

from __future__ import annotations

import sys

from ..agent.reasoner import Reasoner
from ..agent.render import render_markdown
from .graders import ScenarioResult, grade
from .scenarios import GOLDEN_SCENARIOS
from .schemas import GoldenScenario


def run(scenarios: list[GoldenScenario] | None = None) -> list[ScenarioResult]:
    scenarios = scenarios or GOLDEN_SCENARIOS
    reasoner = Reasoner()
    results: list[ScenarioResult] = []
    for scn in scenarios:
        try:
            rec, _cards = reasoner.answer(scn.user_message, tax_year=scn.tax_year)
            md = render_markdown(rec)
            res = grade(scn, rec, md)
        except Exception as exc:  # keep the suite going; record the failure
            res = ScenarioResult(scenario_id=scn.scenario_id, error=f"{type(exc).__name__}: {exc}")
        results.append(res)
    return results


def _print_report(results: list[ScenarioResult]) -> int:
    print("\n=== TaxAgent golden eval ===")
    failures = 0
    for r in results:
        verdict = "PASS" if r.passed else "FAIL"
        if not r.passed:
            failures += 1
        print(f"[{verdict}] {r.scenario_id}\n        {r.summary()}")
        if not r.passed and not r.error:
            for c in r.structural + r.safety:
                if not c.passed:
                    print(f"        - failed check: {c.name} {c.detail}")
        if r.needs_judge:
            print(
                f"        - ⚠ smoke needs LLM-judge review "
                f"(exclude_hits={r.smoke_exclude_violations})"
            )
    print(f"\n{len(results) - failures}/{len(results)} scenarios passed.\n")
    return failures


def main() -> int:
    results = run()
    return _print_report(results)


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from taxagent.web import local_app


def _schema() -> dict:
    response = TestClient(local_app.app, base_url="http://127.0.0.1:8056").get("/api/schema")
    assert response.status_code == 200
    return response.json()


def _run_node(script: str) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    handle = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
    try:
        with handle:
            handle.write(script)
        completed = subprocess.run([node, handle.name], text=True, capture_output=True, check=False)
    finally:
        Path(handle.name).unlink(missing_ok=True)
    assert completed.returncode == 0, completed.stderr


def _dom_stub() -> str:
    return """
class Element {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.textContent = "";
    this.value = "";
    this.disabled = false;
    this.hidden = false;
    this.checked = false;
    this.className = "";
    this.dataset = {};
    this.listeners = {};
    this.classList = { add() {}, remove() {} };
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = [...children]; }
  addEventListener(event, callback) { this.listeners[event] = callback; }
  remove() {}
  click() {
    if (this.listeners.click) this.listeners.click({ target: this });
    if (this.listeners.change) this.listeners.change({ target: this });
  }
}
const elements = new Map();
function elementFor(selector) {
  if (!elements.has(selector)) elements.set(selector, new Element(selector));
  return elements.get(selector);
}
global.window = { __TAXAGENT_SKIP_BOOT__: true, confirm: () => true };
global.document = {
  querySelector: elementFor,
  querySelectorAll: () => [],
  createElement: (tag) => new Element(tag),
  createTextNode: (text) => {
    const textNode = new Element("#text");
    textNode.textContent = text;
    return textNode;
  },
  body: new Element("body"),
};
global.Option = function Option(text, value) {
  const option = new Element("option");
  option.textContent = text;
  option.value = value;
  return option;
};
global.URL = { createObjectURL: () => "blob:test", revokeObjectURL() {} };
function collectText(element) {
  return [element.textContent, ...element.children.map((child) => collectText(child))].join(" ");
}
function findByText(element, text) {
  if (element.textContent === text) return element;
  for (const child of element.children) {
    const found = findByText(child, text);
    if (found) return found;
  }
  return null;
}
"""


def _workspace(schema: dict) -> dict:
    years = {}
    for year in range(2020, 2026):
        data = json.loads(json.dumps(schema["blank_input"]))
        data["tax_year"] = year
        years[str(year)] = {
            "tax_year": year,
            "input": data,
            "evidence": {},
            "unresolved_candidates": [],
            "duplicate_candidates": [],
            "missing_facts": [
                {
                    "path": "slips",
                    "code": "missing_imported_slips",
                    "label": f"Import slips for {year}.",
                }
            ],
            "carryforwards": {
                "assessed_opening_balances": {},
                "proposed_closing_balances": {},
                "conflicts": [],
                "downstream_invalidated": False,
            },
            "ready_to_calculate": False,
        }
    return {
        "schema_version": "batch-workspace-v1",
        "years": years,
        "unassigned_candidates": [],
        "duplicate_candidates": [],
        "excluded_candidates": [],
        "source_candidates": {},
        "file_errors": [],
        "active_years": [],
        "corrections": [],
        "decisions": [],
        "carryforward_choices": [],
        "correction_audit": [],
    }


def test_missing_fact_groups_show_every_actionable_fact_without_boolean_guessing():
    schema = _schema()
    js_path = Path("src/taxagent/web/static/local.js").resolve()
    workspace = _workspace(schema)
    workspace["years"]["2025"]["missing_facts"] = [
        {"path": f"taxpayer.generated_missing_{index}", "code": "future_required_fact", "label": f"Future fact {index}"}
        for index in range(1, 11)
    ]

    script = textwrap.dedent(
        f"""
        const assert = require("assert");
        {_dom_stub()}
        const ui = require({json.dumps(str(js_path))});
        ui.state.schema = {json.dumps(schema)};
        ui.activateBatchWorkspace({json.dumps(workspace)}, "2025");
        ui.renderMissingFacts();
        const visible = collectText(elementFor("#missing-facts"));
        assert.match(visible, /Future fact 1/);
        assert.match(visible, /Future fact 10/);
        assert.doesNotMatch(visible, /additional related fields/);
        assert.doesNotMatch(visible, /Unknown Yes No/);
        """
    )
    _run_node(script)


def test_no_current_student_loan_action_preserves_prior_balances():
    schema = _schema()
    js_path = Path("src/taxagent/web/static/local.js").resolve()
    workspace = _workspace(schema)
    workspace["years"]["2025"]["missing_facts"] = [
        {"path": "taxpayer.has_student_loan_interest", "code": "missing_student_loan_interest_answers", "label": "Student-loan interest decision"},
        {"path": "student_loan_interest.reviewed", "code": "missing_student_loan_interest_answers", "label": "Review student-loan interest"},
        {"path": "student_loan_interest.federal_current_year_paid", "code": "missing_student_loan_interest_answers", "label": "Federal current-year interest"},
        {"path": "student_loan_interest.federal_unused_2020", "code": "missing_student_loan_interest_answers", "label": "Federal 2020 carryforward"},
        {"path": "student_loan_interest.quebec_current_year_paid", "code": "missing_student_loan_interest_answers", "label": "Quebec current-year interest"},
    ]
    workspace["years"]["2025"]["input"]["student_loan_interest"]["federal_unused_2020"] = "125.00"
    workspace["years"]["2025"]["input"]["student_loan_interest"]["quebec_prior_unused"] = "75.00"

    script = textwrap.dedent(
        f"""
        const assert = require("assert");
        {_dom_stub()}
        const ui = require({json.dumps(str(js_path))});
        ui.state.schema = {json.dumps(schema)};
        ui.activateBatchWorkspace({json.dumps(workspace)}, "2025");
        ui.renderMissingFacts();
        const button = findByText(elementFor("#missing-facts"), "No current-year qualifying student-loan interest paid");
        assert.ok(button);
        assert.equal(ui.state.input.taxpayer.has_student_loan_interest, null);
        button.click();
        assert.equal(ui.state.input.student_loan_interest.reviewed, true);
        assert.equal(ui.state.input.student_loan_interest.federal_current_year_paid, "0.00");
        assert.equal(ui.state.input.student_loan_interest.quebec_current_year_paid, "0.00");
        assert.equal(ui.state.input.student_loan_interest.federal_claim_amount, null);
        assert.equal(ui.state.input.student_loan_interest.federal_unused_2020, "125.00");
        assert.equal(ui.state.input.student_loan_interest.quebec_prior_unused, "75.00");
        assert.equal(ui.state.input.taxpayer.has_student_loan_interest, null);
        assert.equal(ui.state.input.refundable_credits.work_premium_answers_reviewed, null);
        """
    )
    _run_node(script)


def test_no_current_or_prior_student_loan_action_uses_correct_origin_year_map():
    schema = _schema()
    js_path = Path("src/taxagent/web/static/local.js").resolve()
    workspace = _workspace(schema)
    data = workspace["years"]["2023"]["input"]
    data["schema_version"] = "qc-return-v2"
    data["student_loan_interest"]["federal_unused_by_origin_year"] = {}
    workspace["years"]["2023"]["missing_facts"] = [
        {"path": "student_loan_interest.federal_unused_by_origin_year", "code": "missing_student_loan_interest_answers", "label": "Federal prior unused map"},
        {"path": "student_loan_interest.quebec_prior_unused", "code": "missing_student_loan_interest_answers", "label": "Quebec prior unused"},
    ]
    workspace["years"]["2023"]["input"]["inventory"]["no_income_sources"] = True

    script = textwrap.dedent(
        f"""
        const assert = require("assert");
        {_dom_stub()}
        const ui = require({json.dumps(str(js_path))});
        ui.state.schema = {json.dumps(schema)};
        ui.activateBatchWorkspace({json.dumps(workspace)}, "2023");
        ui.renderMissingFacts();
        const button = findByText(elementFor("#missing-facts"), "No current-year or prior unused qualifying student-loan interest");
        assert.ok(button);
        button.click();
        assert.deepEqual(ui.state.input.student_loan_interest.federal_unused_by_origin_year, {{
          "2018": "0.00",
          "2019": "0.00",
          "2020": "0.00",
          "2021": "0.00",
          "2022": "0.00",
        }});
        assert.equal(Object.prototype.hasOwnProperty.call(ui.state.input.student_loan_interest, "federal_unused_2024"), true);
        assert.equal(ui.state.input.student_loan_interest.federal_unused_2024, null);
        assert.equal(ui.state.input.student_loan_interest.quebec_prior_unused, "0.00");
        """
    )
    _run_node(script)


def test_no_current_or_prior_student_loan_action_preserves_positive_origin_map():
    schema = _schema()
    js_path = Path("src/taxagent/web/static/local.js").resolve()
    workspace = _workspace(schema)
    data = workspace["years"]["2024"]["input"]
    data["schema_version"] = "qc-return-v2"
    data["student_loan_interest"]["federal_unused_by_origin_year"] = {"2021": "350.00"}
    data["student_loan_interest"]["quebec_prior_unused"] = "90.00"
    workspace["years"]["2024"]["missing_facts"] = [
        {"path": "student_loan_interest.federal_unused_by_origin_year", "code": "missing_student_loan_interest_answers", "label": "Federal prior unused map"},
        {"path": "student_loan_interest.quebec_prior_unused", "code": "missing_student_loan_interest_answers", "label": "Quebec prior unused"},
    ]
    workspace["years"]["2024"]["input"]["inventory"]["no_income_sources"] = True

    script = textwrap.dedent(
        f"""
        const assert = require("assert");
        {_dom_stub()}
        const ui = require({json.dumps(str(js_path))});
        ui.state.schema = {json.dumps(schema)};
        ui.activateBatchWorkspace({json.dumps(workspace)}, "2024");
        ui.renderMissingFacts();
        const button = findByText(elementFor("#missing-facts"), "No current-year or prior unused qualifying student-loan interest");
        assert.ok(button);
        button.click();
        assert.deepEqual(ui.state.input.student_loan_interest.federal_unused_by_origin_year, {{ "2021": "350.00" }});
        assert.equal(ui.state.input.student_loan_interest.quebec_prior_unused, "90.00");
        assert.equal(ui.state.input.taxpayer.has_student_loan_interest, null);
        assert.equal(ui.state.input.student_loan_interest.qualifying_government_loans_confirmed, null);
        const visible = collectText(elementFor("#missing-facts"));
        assert.match(visible, /Federal prior unused map/);
        assert.match(visible, /Quebec prior unused/);
        """
    )
    _run_node(script)


def test_apply_selected_profile_facts_adjusts_age_and_preserves_existing_answers():
    schema = _schema()
    js_path = Path("src/taxagent/web/static/local.js").resolve()
    workspace = _workspace(schema)
    for year in ["2023", "2024", "2025"]:
        workspace["years"][year]["missing_facts"] = [
            {"path": "taxpayer.age_dec31", "code": "missing_coverage_answer", "label": "Age"}
        ]
        workspace["years"][year]["input"]["inventory"]["no_income_sources"] = True
    source = workspace["years"]["2025"]["input"]
    source["taxpayer"]["age_dec31"] = 30
    source["taxpayer"]["marital_status"] = "single"
    source["taxpayer"]["dependant_count"] = 0
    source["taxpayer"]["full_year_quebec_resident"] = True
    source["taxpayer"]["was_full_time_student_more_than_13_weeks"] = True
    source["drug_insurance"]["eligible_student_months"] = [1, 2, 3]
    workspace["years"]["2024"]["input"]["taxpayer"]["marital_status"] = "married"

    script = textwrap.dedent(
        f"""
        const assert = require("assert");
        {_dom_stub()}
        const ui = require({json.dumps(str(js_path))});
        ui.state.schema = {json.dumps(schema)};
        ui.activateBatchWorkspace({json.dumps(workspace)}, "2025");
        ui.state.batchResult = {{
          status: "complete",
          results: {{
            "2023": {{ status: "complete" }},
            "2024": {{ status: "complete" }},
            "2025": {{ status: "complete" }},
          }},
        }};
        const changed = ui.applySelectedProfileFactsToActiveYears([
          "taxpayer.age_dec31",
          "taxpayer.marital_status",
          "taxpayer.dependant_count",
        ], {{ overwrite: false }});
        assert.deepEqual(changed.sort(), ["2023", "2024"]);
        assert.equal(ui.state.workspace.years["2024"].input.taxpayer.age_dec31, 29);
        assert.equal(ui.state.workspace.years["2023"].input.taxpayer.age_dec31, 28);
        assert.equal(ui.state.workspace.years["2024"].input.taxpayer.marital_status, "married");
        assert.equal(ui.state.workspace.years["2023"].input.taxpayer.marital_status, "single");
        assert.equal(ui.state.workspace.years["2024"].input.taxpayer.full_year_quebec_resident, null);
        assert.equal(ui.state.workspace.years["2024"].input.taxpayer.was_full_time_student_more_than_13_weeks, null);
        assert.equal(ui.state.workspace.years["2024"].input.drug_insurance.eligible_student_months, null);
        assert.equal(ui.state.batchResult.results["2023"], undefined);
        assert.equal(ui.state.batchResult.results["2024"], undefined);
        assert.equal(ui.state.batchResult.results["2025"], undefined);
        """
    )
    _run_node(script)

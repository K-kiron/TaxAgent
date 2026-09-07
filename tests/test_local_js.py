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
    client = TestClient(local_app.app, base_url="http://127.0.0.1:8056")
    response = client.get("/api/schema")
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
        completed = subprocess.run(
            [node, handle.name],
            text=True,
            capture_output=True,
            check=False,
        )
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
    this.classList = { add() {}, remove() {} };
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = [...children]; }
  addEventListener(type, handler) {
    this.listeners = this.listeners || {};
    this.listeners[type] = this.listeners[type] || [];
    this.listeners[type].push(handler);
  }
  dispatch(type, event = {}) {
    for (const handler of (this.listeners?.[type] || [])) handler({ target: this, ...event });
  }
  remove() {}
  click() { this.dispatch("click"); }
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
"""


def _batch_workspace(schema: dict) -> dict:
    return {
        "schema_version": "batch-workspace-v1",
        "years": {
            str(year): {
                "tax_year": year,
                "input": {**json.loads(json.dumps(schema["blank_input"])), "tax_year": year, "slips": []},
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
            for year in range(2020, 2026)
        },
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


def _t4_slip(candidate_id: str, year: int, amount: str) -> dict:
    return {
        "slip_type": "T4",
        "document_id": candidate_id,
        "issuer_id": "Example Employer",
        "tax_year": year,
        "province_of_employment": "QC",
        "cpp_qpp_exempt": False,
        "ei_exempt": False,
        "ppip_exempt": False,
        "rrsp_period": None,
        "rl1_box_o_allocations": None,
        "confirmed": True,
        "fields": {"14": amount},
    }


def _candidate(candidate_id: str, year: int | None = None, amount: str = "45000.00") -> dict:
    return {
        "candidate_id": candidate_id,
        "document_id": "doc-1",
        "slip_type": "T4",
        "tax_year": year,
        "issuer_id": "Example Employer",
        "decision": "review_required",
        "reason": "candidate_requires_review",
        "review_reasons": ["low_confidence"],
        "candidate": {
            "candidate_id": candidate_id,
            "document_id": "doc-1",
            "slip_type": "T4",
            "tax_year": year,
            "issuer_id": "Example Employer",
            "decision": "review_required",
            "review_reasons": ["low_confidence"],
            "fields": {
                "14": {
                    "value": amount,
                    "confidence": 0.61,
                    "raw_text": "Box 14",
                    "page": 1,
                    "bbox": [1, 2, 3, 4],
                    "review_required": True,
                }
            },
        },
    }


def test_json_import_validation_is_transactional_and_clears_accepted_old_result():
    schema = _schema()
    js_path = Path("src/taxagent/web/static/local.js").resolve()
    old_schema = json.loads(json.dumps(schema["blank_input"]))
    del old_schema["scholarships"]
    del old_schema["resp_eap"]

    script = textwrap.dedent(
        f"""
        const assert = require("assert");
        {_dom_stub()}
        (async () => {{
        const ui = require({json.dumps(str(js_path))});
        const schema = {json.dumps(schema)};
        const oldSchema = {json.dumps(old_schema)};
        ui.state.schema = schema;
        ui.state.input = JSON.parse(JSON.stringify(ui.state.schema.blank_input));
        ui.state.result = {{ status: "complete", federal_refund_or_balance: "1.00", lines: [] }};
        ui.state.responseSources = {{ old_source: {{ url: "https://example.test", title: "old" }} }};

        for (const payload of [{{}}, {{ slips: [] }}, oldSchema]) {{
          const before = ui.state.input;
          const resultBefore = ui.state.result;
          const normalized = ui.normalizeImportedInput(payload);
          assert.equal(normalized.ok, false);
          assert.strictEqual(ui.state.input, before);
          assert.strictEqual(ui.state.result, resultBefore);
        }}

        const accepted = {{
          target: {{
            value: "selected",
            files: [{{
              name: "taxagent_2025_qc_input.json",
              type: "application/json",
              size: 100,
              text: async () => JSON.stringify({{ input: schema.blank_input }}),
            }}],
          }},
        }};
        await ui.importJson(accepted);
        assert.equal(ui.state.dirty, true);
        assert.equal(ui.state.result, null);
        assert.deepEqual(ui.state.responseSources, {{}});
        assert.equal(elementFor("#save-result").disabled, true);
        assert.equal(elementFor("#print-packet").disabled, true);
        assert.match(elementFor("#calculation-state").textContent, /Calculate to validate/);
        }})().catch((error) => {{
          console.error(error);
          process.exit(1);
        }});
        """
    )
    _run_node(script)


def test_calculate_ignores_stale_responses_and_recovers_from_service_errors():
    schema = _schema()
    js_path = Path("src/taxagent/web/static/local.js").resolve()
    script = textwrap.dedent(
        f"""
        const assert = require("assert");
        {_dom_stub()}
        (async () => {{
        const ui = require({json.dumps(str(js_path))});
        const schema = {json.dumps(schema)};
        ui.state.schema = schema;
        ui.state.input = JSON.parse(JSON.stringify(ui.state.schema.blank_input));

        let release;
        global.fetch = () => new Promise((resolve) => {{
          release = () => resolve({{
            ok: true,
            json: async () => ({{
              result: {{ status: "complete", blockers: [], lines: [], federal_refund_or_balance: "9.99" }},
              sources: {{}},
            }}),
          }});
        }});
        const stale = ui.calculate();
        ui.markDirty();
        release();
        await stale;
        assert.equal(ui.state.result, null);
        assert.equal(elementFor("#save-result").disabled, true);

        global.fetch = async () => {{ throw new Error("server down"); }};
        await ui.calculate();
        assert.equal(ui.state.result.status, "blocked");
        assert.equal(ui.state.result.blockers[0].code, "local_service_error");
        assert.match(elementFor("#calculation-state").textContent, /usable response/);

        global.fetch = async () => ({{
          ok: true,
          json: async () => ({{
            result: {{ status: "complete", blockers: [], lines: [], federal_refund_or_balance: "10.00" }},
            sources: {{}},
          }}),
        }});
        await ui.calculate();
        assert.equal(ui.state.result.status, "complete");
        assert.equal(ui.state.dirty, false);
        assert.equal(elementFor("#save-result").disabled, false);
        }})().catch((error) => {{
          console.error(error);
          process.exit(1);
        }});
        """
    )
    _run_node(script)


def test_result_warnings_are_visible_and_exported():
    schema = _schema()
    js_path = Path("src/taxagent/web/static/local.js").resolve()
    script = textwrap.dedent(
        f"""
        const assert = require("assert");
        {_dom_stub()}
        function collectText(element) {{
          return [element.textContent, ...element.children.map((child) => collectText(child))].join(" ");
        }}
        const ui = require({json.dumps(str(js_path))});
        ui.state.schema = {json.dumps(schema)};
        ui.renderResult({{
          sources: {{}},
          result: {{
            status: "complete",
            federal_refund_or_balance: "3055.21",
            quebec_refund_or_balance: "1199.84",
            warnings: ["The Quebec headline is the prepared-return amount before QPIP assessment adjustment."],
            blockers: [],
            lines: [],
          }},
        }});

        const visible = collectText(elementFor("#results"));
        assert.match(visible, /Federal prepared refund/);
        assert.match(visible, /Preparation warnings/);
        assert.match(visible, /QPIP assessment adjustment/);

        const packet = ui.reviewPacket();
        assert.match(packet, /Warnings/);
        assert.match(packet, /QPIP assessment adjustment/);
        """
    )
    _run_node(script)


def test_quebec_work_premium_student_hint_links_official_definition():
    schema = _schema()
    js_path = Path("src/taxagent/web/static/local.js").resolve()
    script = textwrap.dedent(
        f"""
        const assert = require("assert");
        {_dom_stub()}
        function collectText(element) {{
          return [element.textContent, ...element.children.map((child) => collectText(child))].join(" ");
        }}
        function collectAnchors(element, anchors = []) {{
          if (element.tag === "a") anchors.push(element);
          for (const child of element.children) collectAnchors(child, anchors);
          return anchors;
        }}
        const ui = require({json.dumps(str(js_path))});
        ui.state.schema = {json.dumps(schema)};
        ui.state.input = JSON.parse(JSON.stringify(ui.state.schema.blank_input));
        ui.renderFacts();

        const visible = collectText(elementFor("#facts-form"));
        assert.match(visible, /separate Quebec definition/);
        assert.match(visible, /term began during 2025/);
        const links = collectAnchors(elementFor("#facts-form"));
        assert.ok(links.some((link) => link.href === "https://www.revenuquebec.ca/en/definitions/full-time-student/"));
        """
    )
    _run_node(script)


def test_batch_workspace_restore_tracks_only_years_with_work():
    schema = _schema()
    js_path = Path("src/taxagent/web/static/local.js").resolve()
    workspace = {
        "schema_version": "batch-workspace-v1",
        "years": {
            str(year): {
                "tax_year": year,
                "input": {**json.loads(json.dumps(schema["blank_input"])), "tax_year": year, "slips": []},
                "evidence": {},
                "unresolved_candidates": [],
                "duplicate_candidates": [],
                "missing_facts": [{"path": "slips", "code": "missing_imported_slips", "label": f"Import slips for {year}."}],
                "carryforwards": {
                    "assessed_opening_balances": {},
                    "proposed_closing_balances": {},
                    "conflicts": [],
                    "downstream_invalidated": False,
                },
                "ready_to_calculate": False,
            }
            for year in range(2020, 2026)
        },
        "unassigned_candidates": [],
        "duplicate_candidates": [],
    }
    workspace["years"]["2024"]["input"]["slips"] = [
        {
            "slip_type": "T4",
            "document_id": "c-2024",
            "issuer_id": "Example",
            "tax_year": 2024,
            "province_of_employment": "QC",
            "cpp_qpp_exempt": False,
            "ei_exempt": False,
            "ppip_exempt": False,
            "rrsp_period": None,
            "rl1_box_o_allocations": None,
            "confirmed": True,
            "fields": {"14": "45000.00"},
        }
    ]
    workspace["years"]["2024"]["missing_facts"] = []

    script = textwrap.dedent(
        f"""
        const assert = require("assert");
        {_dom_stub()}
        const ui = require({json.dumps(str(js_path))});
        ui.state.schema = {json.dumps(schema)};
        const restored = ui.normalizeImportedWorkspace({json.dumps(workspace)});
        assert.equal(restored.ok, true);
        ui.activateBatchWorkspace(restored.workspace, "2025");
        assert.deepEqual(ui.state.activeYears, ["2024"]);
        assert.equal(ui.state.selectedYear, "2024");

        ui.state.selectedYear = "2025";
        ui.state.input = ui.state.workspace.years["2025"].input;
        const calculatePayload = ui.activeWorkspaceForCalculation();
        assert.deepEqual(ui.state.activeYears, ["2024"]);
        assert.deepEqual(calculatePayload.years["2025"].unresolved_candidates, []);
        assert.equal(calculatePayload.years["2025"].ready_to_calculate, false);
        """
    )
    _run_node(script)


def test_batch_pdf_import_keeps_valid_files_and_marks_errors():
    schema = _schema()
    js_path = Path("src/taxagent/web/static/local.js").resolve()
    workspace = {
        "schema_version": "batch-workspace-v1",
        "years": {
            str(year): {
                "tax_year": year,
                "input": {**json.loads(json.dumps(schema["blank_input"])), "tax_year": year, "slips": []},
                "evidence": {},
                "unresolved_candidates": [],
                "duplicate_candidates": [],
                "missing_facts": [{"path": "slips", "code": "missing_imported_slips", "label": f"Import slips for {year}."}],
                "carryforwards": {
                    "assessed_opening_balances": {},
                    "proposed_closing_balances": {},
                    "conflicts": [],
                    "downstream_invalidated": False,
                },
                "ready_to_calculate": False,
            }
            for year in range(2020, 2026)
        },
        "unassigned_candidates": [],
        "duplicate_candidates": [],
    }
    workspace["years"]["2025"]["input"]["slips"] = [
        {
            "slip_type": "T4",
            "document_id": "cand-1",
            "issuer_id": "Example",
            "tax_year": 2025,
            "province_of_employment": "QC",
            "cpp_qpp_exempt": False,
            "ei_exempt": False,
            "ppip_exempt": False,
            "rrsp_period": None,
            "rl1_box_o_allocations": None,
            "confirmed": True,
            "fields": {"14": "45000.00"},
        }
    ]
    workspace["years"]["2025"]["missing_facts"] = []

    script = textwrap.dedent(
        f"""
        const assert = require("assert");
        {_dom_stub()}
        class FakeFormData {{
          constructor() {{ this.items = []; }}
          append(name, file, filename) {{ this.items.push([name, filename]); }}
        }}
        global.FormData = FakeFormData;
        const ui = require({json.dumps(str(js_path))});
        ui.state.schema = {json.dumps(schema)};
        ui.state.input = JSON.parse(JSON.stringify(ui.state.schema.blank_input));
        (async () => {{
        global.fetch = async () => {{
          throw new Error("permission encrypted PDF rejected");
        }};
        await ui.importPdfs([
          {{ name: "t4.pdf", type: "application/pdf", size: 100 }},
          {{ name: "notes.txt", type: "text/plain", size: 10 }},
        ]);
        assert.equal(ui.state.batchFiles.length, 2);
        assert.match(ui.state.batchFiles[0].status, /Import failed/);
        assert.match(ui.state.batchFiles[1].status, /PDF files only/);
        assert.ok(ui.state.batchPdfUrls["t4.pdf"]);

        global.fetch = async () => ({{
          ok: true,
          json: async () => ({{
            import_result: {{ documents: [{{ document_id: "doc-1", filename: "t4.pdf", status: "processed" }}] }},
            workspace: {json.dumps(workspace)},
          }}),
        }});
        await ui.importPdfs([{{ name: "other.pdf", type: "application/pdf", size: 200 }}]);
        assert.equal(ui.state.mode, "batch");
        assert.equal(ui.state.activeYears.includes("2025"), true);
        assert.equal(ui.state.batchPdfUrls["doc-1"], ui.state.batchPdfUrls["t4.pdf"]);
        }})().catch((error) => {{
          console.error(error);
          process.exit(1);
        }});
        """
    )
    _run_node(script)


def test_review_actions_post_contract_and_replace_authoritative_workspace():
    schema = _schema()
    js_path = Path("src/taxagent/web/static/local.js").resolve()
    workspace = _batch_workspace(schema)
    workspace["years"]["2025"]["unresolved_candidates"] = [_candidate("cand-1", 2025)]
    workspace["years"]["2025"]["missing_facts"] = []
    reconciled = json.loads(json.dumps(workspace))
    reconciled["years"]["2025"]["unresolved_candidates"] = []
    reconciled["years"]["2025"]["input"]["slips"] = [_t4_slip("cand-1", 2025, "47000.00")]
    reconciled["years"]["2025"]["evidence"] = {
        "cand-1": {
            "candidate_id": "cand-1",
            "document_id": "doc-1",
            "slip_type": "T4",
            "tax_year": 2025,
            "issuer_id": "Corrected Employer",
            "fields": {
                "14": {
                    "value": "45000.00",
                    "accepted_value": "47000.00",
                    "raw_text": "Box 14",
                    "page": 1,
                }
            },
        }
    }
    reconciled["active_years"] = [2025]
    reconciled["corrections"] = [
        {
            "candidate_id": "cand-1",
            "reason": "Corrected extracted PDF candidate before calculation.",
            "issuer_id": "Corrected Employer",
            "fields": {"14": "47000.00"},
        }
    ]
    reconciled["decisions"] = [
        {"candidate_id": "cand-1", "action": "accept", "reason": "Accepted after local PDF review."}
    ]

    script = textwrap.dedent(
        f"""
        const assert = require("assert");
        {_dom_stub()}
        const ui = require({json.dumps(str(js_path))});
        ui.state.schema = {json.dumps(schema)};
        ui.activateBatchWorkspace({json.dumps(workspace)}, "2025");
        ui.queueCorrection("cand-1", {{ issuer_id: "Corrected Employer", fields: {{ "14": "47000.00" }} }});
        ui.queueDecision("cand-1", "accept");
        const preflightPayload = ui.reviewRequestPayload();
        assert.deepEqual(preflightPayload.active_years, [2025]);
        assert.deepEqual(preflightPayload.corrections[0].fields, {{ "14": "47000.00" }});
        assert.equal(preflightPayload.decisions[0].action, "accept");

        let posted;
        global.fetch = async (url, options) => {{
          posted = {{ url, body: JSON.parse(options.body) }};
          return {{ ok: true, json: async () => ({json.dumps(reconciled)}) }};
        }};
        (async () => {{
          const applied = await ui.applyReviewActions();
          assert.equal(applied, true);
          assert.equal(posted.url, ui.state.schema.batch_pdf.reconcile_endpoint);
          assert.deepEqual(posted.body.active_years, [2025]);
          assert.equal(posted.body.workspace.years["2025"].unresolved_candidates.length, 1);
          assert.equal(ui.state.workspace.years["2025"].input.slips[0].fields["14"], "47000.00");
          assert.deepEqual(ui.state.pendingReviewActions, {{ corrections: [], decisions: [], carryforward_choices: [] }});
        }})().catch((error) => {{
          console.error(error);
          process.exit(1);
        }});
        """
    )
    _run_node(script)


def test_review_actions_are_retained_when_backend_rejects_them():
    schema = _schema()
    js_path = Path("src/taxagent/web/static/local.js").resolve()
    workspace = _batch_workspace(schema)
    workspace["unassigned_candidates"] = [_candidate("unknown-year", None)]

    script = textwrap.dedent(
        f"""
        const assert = require("assert");
        {_dom_stub()}
        const ui = require({json.dumps(str(js_path))});
        ui.state.schema = {json.dumps(schema)};
        ui.activateBatchWorkspace({json.dumps(workspace)}, "2025");
        ui.queueDecision("unknown-year", "accept");
        const before = ui.state.workspace;
        global.fetch = async () => ({{
          ok: false,
          json: async () => ({{
            detail: {{
              code: "invalid_schema",
              errors: [{{ path: "workspace", message: "review action references an unknown candidate" }}],
            }},
          }}),
        }});
        (async () => {{
          const applied = await ui.applyReviewActions();
          assert.equal(applied, false);
          assert.strictEqual(ui.state.workspace, before);
          assert.equal(ui.state.pendingReviewActions.decisions.length, 1);
          assert.equal(ui.state.pendingReviewActions.decisions[0].candidate_id, "unknown-year");
        }})().catch((error) => {{
          console.error(error);
          process.exit(1);
        }});
        """
    )
    _run_node(script)


def test_batch_calculate_applies_pending_review_and_refreshes_workspace_from_response():
    schema = _schema()
    js_path = Path("src/taxagent/web/static/local.js").resolve()
    workspace = _batch_workspace(schema)
    workspace["years"]["2024"]["unresolved_candidates"] = [_candidate("cand-2024", 2024, "41000.00")]
    workspace["years"]["2024"]["missing_facts"] = []
    reconciled = json.loads(json.dumps(workspace))
    reconciled["years"]["2024"]["unresolved_candidates"] = []
    reconciled["years"]["2024"]["input"]["slips"] = [_t4_slip("cand-2024", 2024, "41000.00")]
    reconciled["years"]["2024"]["ready_to_calculate"] = True
    reconciled["active_years"] = [2024]
    calculated = json.loads(json.dumps(reconciled))
    calculated["years"]["2024"]["input"]["slips"][0]["fields"]["14"] = "42000.00"
    calculated["years"]["2024"]["carryforwards"]["proposed_closing_balances"] = {
        "federal_tuition_unused_fees": {"amount": "123.00"}
    }
    result = {
        "schema_version": "batch-calculation-v1",
        "status": "complete",
        "duplicate_candidates": [],
        "results": {
            "2024": {
                "status": "complete",
                "federal_refund_or_balance": "88.00",
                "quebec_refund_or_balance": "44.00",
                "warnings": [],
                "lines": [],
                "carryforwards": {"federal_tuition_unused_fees": {"amount": "123.00"}},
            }
        },
        "workspace": calculated,
    }

    script = textwrap.dedent(
        f"""
        const assert = require("assert");
        {_dom_stub()}
        const ui = require({json.dumps(str(js_path))});
        ui.state.schema = {json.dumps(schema)};
        ui.activateBatchWorkspace({json.dumps(workspace)}, "2024");
        ui.queueDecision("cand-2024", "accept");
        const posts = [];
        global.fetch = async (url, options) => {{
          posts.push({{ url, body: JSON.parse(options.body) }});
          if (url === ui.state.schema.batch_pdf.reconcile_endpoint) {{
            return {{ ok: true, json: async () => ({json.dumps(reconciled)}) }};
          }}
          return {{ ok: true, json: async () => ({json.dumps(result)}) }};
        }};
        (async () => {{
          await ui.calculate();
          assert.deepEqual(posts.map((post) => post.url), [ui.state.schema.batch_pdf.reconcile_endpoint, ui.state.schema.batch_pdf.calculate_endpoint]);
          assert.deepEqual(posts[1].body.active_years, [2024]);
          assert.equal(ui.state.workspace.years["2024"].input.slips[0].fields["14"], "42000.00");
          assert.equal(ui.state.batchResult.results["2024"].federal_refund_or_balance, "88.00");
          assert.equal(ui.state.dirty, false);
        }})().catch((error) => {{
          console.error(error);
          process.exit(1);
        }});
        """
    )
    _run_node(script)


def test_carryforward_choices_are_posted_with_source_amount_conflicts():
    schema = _schema()
    js_path = Path("src/taxagent/web/static/local.js").resolve()
    workspace = _batch_workspace(schema)
    workspace["years"]["2025"]["input"]["inventory"]["no_income_sources"] = True
    workspace["years"]["2025"]["missing_facts"] = []
    workspace["years"]["2025"]["carryforwards"]["conflicts"] = [
        {
            "key": "federal_student_loan_interest_unused_2021",
            "assessed_amount": "100.00",
            "proposed_amount": "125.00",
            "resolved_selection": None,
        }
    ]

    script = textwrap.dedent(
        f"""
        const assert = require("assert");
        {_dom_stub()}
        function collectText(element) {{
          return [element.textContent, ...element.children.map((child) => collectText(child))].join(" ");
        }}
        const ui = require({json.dumps(str(js_path))});
        ui.state.schema = {json.dumps(schema)};
        ui.activateBatchWorkspace({json.dumps(workspace)}, "2025");
        ui.renderMissingFacts();
        const visible = collectText(elementFor("#missing-facts"));
        assert.match(visible, /Assessed opening balance/);
        assert.match(visible, /\\$100\\.00/);
        assert.match(visible, /\\$125\\.00/);
        ui.queueCarryforwardChoice(2025, "federal_student_loan_interest_unused_2021", "proposed");
        const payload = ui.reviewRequestPayload();
        assert.deepEqual(payload.carryforward_choices, [{{
          tax_year: 2025,
          key: "federal_student_loan_interest_unused_2021",
          selection: "proposed",
          reason: "Used the preceding year's proposed closing balance.",
        }}]);
        """
    )
    _run_node(script)


def test_upstream_input_change_clears_downstream_batch_amounts():
    schema = _schema()
    js_path = Path("src/taxagent/web/static/local.js").resolve()
    workspace = _batch_workspace(schema)
    workspace["years"]["2024"]["input"]["slips"] = [_t4_slip("cand-2024", 2024, "40000.00")]
    workspace["years"]["2025"]["input"]["slips"] = [_t4_slip("cand-2025", 2025, "50000.00")]
    workspace["years"]["2024"]["missing_facts"] = []
    workspace["years"]["2025"]["missing_facts"] = []

    script = textwrap.dedent(
        f"""
        const assert = require("assert");
        {_dom_stub()}
        const ui = require({json.dumps(str(js_path))});
        ui.state.schema = {json.dumps(schema)};
        ui.activateBatchWorkspace({json.dumps(workspace)}, "2024");
        ui.state.batchResult = {{
          status: "complete",
          results: {{
            "2024": {{ status: "complete", federal_refund_or_balance: "100.00" }},
            "2025": {{ status: "complete", federal_refund_or_balance: "200.00" }},
          }},
        }};
        ui.state.workspace.years["2024"].input.slips[0].fields["14"] = "41000.00";
        ui.markDirty();
        assert.equal(ui.state.batchResult.results["2024"], undefined);
        assert.equal(ui.state.batchResult.results["2025"], undefined);
        assert.match(elementFor("#calculation-state").textContent, /Recalculate/);
        """
    )
    _run_node(script)


def test_imported_slip_controls_queue_candidate_corrections_and_exclusion():
    schema = _schema()
    js_path = Path("src/taxagent/web/static/local.js").resolve()
    workspace = _batch_workspace(schema)
    t4 = _t4_slip("cand-t4", 2025, "50000.00")
    t4["province_of_employment"] = None
    t4["cpp_qpp_exempt"] = None
    t4["ei_exempt"] = None
    t4["ppip_exempt"] = None
    t2202 = {
        "slip_type": "T2202",
        "document_id": "cand-t2202",
        "issuer_id": "Example University",
        "tax_year": 2025,
        "province_of_employment": None,
        "cpp_qpp_exempt": None,
        "ei_exempt": None,
        "ppip_exempt": None,
        "rrsp_period": None,
        "rl1_box_o_allocations": None,
        "confirmed": True,
        "fields": {"26": "4200.00"},
    }
    workspace["years"]["2025"]["input"]["slips"] = [t4, t2202]
    workspace["years"]["2025"]["missing_facts"] = []
    workspace["source_candidates"] = {
        "cand-t4": {
            "candidate_id": "cand-t4",
            "document_id": "cand-t4",
            "slip_type": "T4",
            "tax_year": 2025,
            "issuer_id": "Example Employer",
            "fields": {"14": {"value": "50000.00"}},
            "metadata": {},
        },
        "cand-t2202": {
            "candidate_id": "cand-t2202",
            "document_id": "cand-t2202",
            "slip_type": "T2202",
            "tax_year": 2025,
            "issuer_id": "Example University",
            "fields": {"26": {"value": "4200.00"}},
            "metadata": {},
        },
    }
    reconciled = json.loads(json.dumps(workspace))
    reconciled["corrections"] = [
        {
            "candidate_id": "cand-t4",
            "reason": "Corrected extracted PDF candidate before calculation.",
            "metadata": {"province_of_employment": "QC", "cpp_qpp_exempt": False},
        },
        {
            "candidate_id": "cand-t2202",
            "reason": "Corrected extracted PDF candidate before calculation.",
            "fields": {"24": "0", "25": "8"},
        },
    ]
    reconciled["decisions"] = [{"candidate_id": "cand-t4", "action": "exclude", "reason": "Excluded after local PDF review."}]

    script = textwrap.dedent(
        f"""
        const assert = require("assert");
        {_dom_stub()}
        function walk(element, out = []) {{
          out.push(element);
          for (const child of element.children || []) walk(child, out);
          return out;
        }}
        function findControl(root, candidateId, group, key) {{
          const match = walk(root).find((element) =>
            element.dataset?.candidateId === candidateId &&
            element.dataset?.correctionGroup === group &&
            element.dataset?.correctionKey === key
          );
          assert.ok(match, `missing control ${{candidateId}} ${{group}} ${{key}}`);
          return match;
        }}
        const ui = require({json.dumps(str(js_path))});
        ui.state.schema = {json.dumps(schema)};
        ui.activateBatchWorkspace({json.dumps(workspace)}, "2025");
        ui.renderSlips();
        const slipsRoot = elementFor("#slips");
        const visible = walk(slipsRoot).map((element) => element.textContent).join(" ");
        assert.match(visible, /Imported from batch PDF/);
        assert.match(visible, /Use source correction controls/);

        const province = findControl(slipsRoot, "cand-t4", "metadata", "province_of_employment");
        province.value = "QC";
        province.dispatch("input");
        const cpp = findControl(slipsRoot, "cand-t4", "metadata", "cpp_qpp_exempt");
        assert.equal(cpp.tag, "select");
        cpp.value = "false";
        cpp.dispatch("change");
        const box24 = findControl(slipsRoot, "cand-t2202", "fields", "24");
        box24.value = "0";
        box24.dispatch("input");
        const box25 = findControl(slipsRoot, "cand-t2202", "fields", "25");
        box25.value = "8";
        box25.dispatch("input");
        const remove = walk(slipsRoot).find((element) => element.dataset?.action === "exclude-imported-slip" && element.dataset?.candidateId === "cand-t4");
        assert.ok(remove);
        remove.click();

        const payload = ui.reviewRequestPayload();
        assert.equal(payload.corrections.find((item) => item.candidate_id === "cand-t4").metadata.province_of_employment, "QC");
        assert.equal(payload.corrections.find((item) => item.candidate_id === "cand-t4").metadata.cpp_qpp_exempt, false);
        assert.deepEqual(payload.corrections.find((item) => item.candidate_id === "cand-t2202").fields, {{ "24": "0", "25": "8" }});
        assert.equal(payload.decisions.find((item) => item.candidate_id === "cand-t4").action, "exclude");
        assert.equal(ui.state.input.slips.length, 2);

        let posted;
        global.fetch = async (url, options) => {{
          posted = {{ url, body: JSON.parse(options.body) }};
          return {{ ok: true, json: async () => ({json.dumps(reconciled)}) }};
        }};
        (async () => {{
          const applied = await ui.applyReviewActions();
          assert.equal(applied, true);
          assert.equal(posted.url, ui.state.schema.batch_pdf.reconcile_endpoint);
          assert.equal(posted.body.corrections.find((item) => item.candidate_id === "cand-t4").metadata.cpp_qpp_exempt, false);
          assert.deepEqual(posted.body.corrections.find((item) => item.candidate_id === "cand-t2202").fields, {{ "24": "0", "25": "8" }});
          assert.deepEqual(ui.state.workspace.corrections[0].metadata, {{ province_of_employment: "QC", cpp_qpp_exempt: false }});
          assert.deepEqual(ui.state.pendingReviewActions, {{ corrections: [], decisions: [], carryforward_choices: [] }});
        }})().catch((error) => {{
          console.error(error);
          process.exit(1);
        }});
        """
    )
    _run_node(script)


def test_missing_fact_slip_controls_queue_candidate_corrections_without_mutating_tax_input():
    schema = _schema()
    js_path = Path("src/taxagent/web/static/local.js").resolve()
    workspace = _batch_workspace(schema)
    t4 = _t4_slip("cand-t4", 2025, "50000.00")
    t4["province_of_employment"] = None
    t4["cpp_qpp_exempt"] = None
    t2202 = {
        "slip_type": "T2202",
        "document_id": "cand-t2202",
        "issuer_id": "Example University",
        "tax_year": 2025,
        "province_of_employment": None,
        "cpp_qpp_exempt": None,
        "ei_exempt": None,
        "ppip_exempt": None,
        "rrsp_period": None,
        "rl1_box_o_allocations": None,
        "confirmed": True,
        "fields": {"26": "4200.00"},
    }
    workspace["years"]["2025"]["input"]["slips"] = [t4, t2202]
    workspace["years"]["2025"]["missing_facts"] = [
        {"path": "slips.cand-t4.province_of_employment", "code": "missing_slip_metadata", "label": "T4 province of employment"},
        {"path": "slips.cand-t4.cpp_qpp_exempt", "code": "missing_slip_metadata", "label": "T4 CPP/QPP exempt"},
        {"path": "slips.1.fields.24", "code": "missing_slip_box", "label": "T2202 eligible tuition amount"},
        {"path": "slips.cand-t2202.fields.25", "code": "missing_slip_box", "label": "T2202 part-time months"},
    ]
    workspace["source_candidates"] = {
        "cand-t4": {
            "candidate_id": "cand-t4",
            "document_id": "cand-t4",
            "slip_type": "T4",
            "tax_year": 2025,
            "issuer_id": "Example Employer",
            "fields": {"14": {"value": "50000.00"}},
            "metadata": {},
        },
        "cand-t2202": {
            "candidate_id": "cand-t2202",
            "document_id": "cand-t2202",
            "slip_type": "T2202",
            "tax_year": 2025,
            "issuer_id": "Example University",
            "fields": {"26": {"value": "4200.00"}},
            "metadata": {},
        },
    }

    script = textwrap.dedent(
        f"""
        const assert = require("assert");
        {_dom_stub()}
        function walk(element, out = []) {{
          out.push(element);
          for (const child of element.children || []) walk(child, out);
          return out;
        }}
        function findControl(root, candidateId, group, key) {{
          const match = walk(root).find((element) =>
            element.dataset?.candidateId === candidateId &&
            element.dataset?.correctionGroup === group &&
            element.dataset?.correctionKey === key
          );
          assert.ok(match, `missing control ${{candidateId}} ${{group}} ${{key}}`);
          return match;
        }}
        const ui = require({json.dumps(str(js_path))});
        ui.state.schema = {json.dumps(schema)};
        ui.activateBatchWorkspace({json.dumps(workspace)}, "2025");
        ui.renderMissingFacts();
        const missingRoot = elementFor("#missing-facts");
        const province = findControl(missingRoot, "cand-t4", "metadata", "province_of_employment");
        province.value = "QC";
        province.dispatch("input");
        const cpp = findControl(missingRoot, "cand-t4", "metadata", "cpp_qpp_exempt");
        assert.equal(cpp.tag, "select");
        cpp.value = "false";
        cpp.dispatch("change");
        const box24 = findControl(missingRoot, "cand-t2202", "fields", "24");
        box24.value = "0";
        box24.dispatch("input");
        const box25 = findControl(missingRoot, "cand-t2202", "fields", "25");
        box25.value = "8";
        box25.dispatch("input");

        const corrections = ui.reviewRequestPayload().corrections;
        assert.equal(corrections.find((item) => item.candidate_id === "cand-t4").metadata.province_of_employment, "QC");
        assert.equal(corrections.find((item) => item.candidate_id === "cand-t4").metadata.cpp_qpp_exempt, false);
        assert.deepEqual(corrections.find((item) => item.candidate_id === "cand-t2202").fields, {{ "24": "0", "25": "8" }});
        assert.equal(ui.state.input.slips[0].province_of_employment, null);
        assert.equal(ui.state.input.slips[0].cpp_qpp_exempt, null);
        assert.equal(Object.prototype.hasOwnProperty.call(ui.state.input, "province_of_employment"), false);
        """
    )
    _run_node(script)

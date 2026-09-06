from __future__ import annotations

import json
import shutil
import subprocess
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
    completed = subprocess.run(
        [node, "-e", script],
        text=True,
        capture_output=True,
        check=False,
    )
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
  addEventListener() {}
  remove() {}
  click() {}
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

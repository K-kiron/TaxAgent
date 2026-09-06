"use strict";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const booleanLabels = {
  full_year_canada_resident: "Full-year Canadian resident in 2025",
  full_year_quebec_resident: "Full-year Quebec resident in 2025",
  deceased_return: "This is a deceased taxpayer return",
  bankruptcy_return: "Bankruptcy return",
  has_self_employment: "Self-employment income",
  has_capital_gains: "Capital gains or losses",
  has_rental_income: "Rental income",
  has_foreign_income_or_tax: "Foreign income or foreign tax",
  has_foreign_property_over_100k: "Foreign property over $100,000",
  has_crypto_transactions: "Crypto transactions",
  has_pension_or_benefit_income: "Pension or benefit income",
  has_indian_act_exempt_income: "Indian Act exempt income",
  has_disability_or_caregiver_claim: "Disability or caregiver claim",
  has_employment_expenses: "Employment expenses",
  has_medical_expenses: "Medical expenses",
  has_donations: "Donations",
  has_childcare_expenses: "Childcare expenses",
  has_moving_expenses: "Moving expenses",
  has_tips_or_other_employment_income: "Tips or other employment income not already on T4/RL-1 slips",
  has_student_loan_interest: "Qualifying government student-loan interest",
  received_qpp_disability_pension: "QPP disability pension",
  made_qpp_cpt30_election: "CPT30 election for QPP/CPP contributions",
  was_full_time_student_more_than_13_weeks: "Full-time student for more than 13 weeks",
  immigrated_or_emigrated_2025: "Immigrated to or emigrated from Canada in 2025",
  quebec_trust_return: "Filing a Quebec trust income tax return",
  separate_post_death_return: "Filing a separate return after death",
  quebec_enterprise_registration_or_annual_fee: "Quebec enterprise registration or annual registration fee applies",
};

const unsupportedFields = [
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
  "received_qpp_disability_pension",
  "made_qpp_cpt30_election",
];

const additionalReturnScreenFields = [
  "immigrated_or_emigrated_2025",
  "quebec_trust_return",
  "separate_post_death_return",
  "quebec_enterprise_registration_or_annual_fee",
];

const slipHints = {
  T4: ["14", "17", "17A", "18", "20", "22", "24", "26", "44", "52", "55"],
  T4A: ["040", "042", "105", "22"],
  RL1: ["A", "B.A", "B.B", "C", "D", "E", "F", "G", "H", "I", "O", "211"],
  T5: ["13"],
  RL3: ["D"],
  T2202: ["24", "25", "26"],
  RRSP_RECEIPT: ["amount"],
  RC210: ["10", "11"],
  RL19: ["A", "B", "C", "D", "G", "H"],
};

const rl1BoxOCodes = [
  ["RB", "RB - scholarship, bursary, or award"],
  ["RZ-RB", "RZ-RB - scholarship, bursary, or award"],
  ["RU", "RU - RESP educational assistance payment"],
  ["RZ-RU", "RZ-RU - RESP educational assistance payment"],
];

const scholarshipCategories = [
  ["ordinary_postsecondary", "Ordinary post-secondary scholarship, bursary, or award"],
  ["artist_project_grant", "Artist project grant (blocks)"],
  ["research_grant", "Research grant (blocks)"],
  ["apprenticeship_grant", "Apprenticeship grant (blocks)"],
  ["employment_or_business_award", "Employment or business award (blocks)"],
  ["elementary_or_secondary_award", "Elementary or secondary school award (blocks)"],
  ["disability_treatment_exception", "Disability-treatment exception (blocks)"],
];

const attendanceOptions = [
  ["full_time", "Full-time qualifying student"],
  ["part_time", "Part-time qualifying student"],
  ["nonqualifying", "Not a qualifying student"],
];

const state = {
  schema: null,
  input: null,
  dirty: false,
  sampleLoaded: false,
  result: null,
  responseSources: {},
  pdfUrls: [],
  inputRevision: 0,
  latestCalculateRequest: 0,
};

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function getPath(root, path) {
  return path.split(".").reduce((current, part) => (current == null ? undefined : current[part]), root);
}

function setPath(root, path, value) {
  const parts = path.split(".");
  let current = root;
  for (const part of parts.slice(0, -1)) current = current[part];
  current[parts[parts.length - 1]] = value;
}

function markDirty() {
  state.dirty = true;
  state.inputRevision += 1;
  state.result = null;
  state.responseSources = {};
  $("#save-result").disabled = true;
  $("#print-packet").disabled = true;
  $("#calculation-state").textContent = "Inputs changed. Recalculate before exporting results.";
  $("#problems").replaceChildren();
  $("#results").replaceChildren();
}

function bumpInputRevision() {
  state.inputRevision += 1;
  state.latestCalculateRequest += 1;
}

function revokePdf(index) {
  if (state.pdfUrls[index]) URL.revokeObjectURL(state.pdfUrls[index]);
  state.pdfUrls[index] = null;
}

function revokeAllPdfs() {
  state.pdfUrls.forEach((url) => {
    if (url) URL.revokeObjectURL(url);
  });
  state.pdfUrls = [];
}

function setBanner(message) {
  const banner = $("#banner");
  banner.hidden = !message;
  banner.textContent = message || "";
}

function fieldWrap(labelText, control, hint) {
  const wrap = node("label", "field");
  const label = node("span", "label", labelText);
  wrap.append(label, control);
  if (hint) wrap.append(typeof hint === "string" ? node("span", "hint", hint) : hint);
  return wrap;
}

function linkHint(text, href, linkText) {
  const hint = node("span", "hint", `${text} `);
  const link = document.createElement("a");
  link.href = href;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = linkText;
  hint.append(link);
  return hint;
}

function textInput(path, label, hint) {
  const input = document.createElement("input");
  input.value = getPath(state.input, path) ?? "";
  input.addEventListener("input", () => {
    setPath(state.input, path, input.value.trim() || null);
    markDirty();
  });
  return fieldWrap(label, input, hint);
}

function numberInput(path, label, hint) {
  const input = document.createElement("input");
  input.type = "number";
  input.step = "1";
  input.value = getPath(state.input, path) ?? "";
  input.addEventListener("input", () => {
    setPath(state.input, path, input.value === "" ? null : Number(input.value));
    markDirty();
  });
  return fieldWrap(label, input, hint);
}

function moneyInput(path, label, hint) {
  const input = document.createElement("input");
  input.inputMode = "decimal";
  input.value = getPath(state.input, path) ?? "";
  input.addEventListener("input", () => {
    setPath(state.input, path, input.value.trim() || null);
    markDirty();
  });
  return fieldWrap(label, input, hint);
}

function monthInput(path, label, hint) {
  const input = document.createElement("input");
  const current = getPath(state.input, path);
  input.placeholder = "1,2,3";
  input.value = Array.isArray(current) ? current.join(",") : "";
  input.addEventListener("input", () => {
    const raw = input.value.trim();
    if (!raw) {
      setPath(state.input, path, null);
    } else {
      const months = raw
        .split(",")
        .map((part) => Number(part.trim()))
        .filter((value) => Number.isInteger(value));
      setPath(state.input, path, months);
    }
    markDirty();
  });
  return fieldWrap(label, input, hint);
}

function choiceInput(path, label, options, hint) {
  const select = document.createElement("select");
  select.append(new Option("Unknown", ""));
  for (const [value, text] of options) select.append(new Option(text, value));
  select.value = getPath(state.input, path) ?? "";
  select.addEventListener("change", () => {
    setPath(state.input, path, select.value || null);
    markDirty();
  });
  return fieldWrap(label, select, hint);
}

function provinceSelect() {
  const select = document.createElement("select");
  select.append(new Option("Unknown", ""));
  select.append(new Option("Quebec", "QC"));
  select.value = state.input.province_dec31 === "QC" && state.input.taxpayer.province_dec31 === "QC" ? "QC" : "";
  select.addEventListener("change", () => {
    const next = select.value || null;
    state.input.province_dec31 = next || "";
    state.input.taxpayer.province_dec31 = next;
    markDirty();
  });
  return fieldWrap(
    "Province on December 31",
    select,
    "This release supports Quebec returns. The single answer is written to both return province fields.",
  );
}

function boolSelect(path, label, hint) {
  const select = document.createElement("select");
  [
    ["", "Unknown"],
    ["true", "Yes"],
    ["false", "No"],
  ].forEach(([value, text]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = text;
    select.append(option);
  });
  const current = getPath(state.input, path);
  select.value = current === true ? "true" : current === false ? "false" : "";
  select.addEventListener("change", () => {
    const next = select.value === "" ? null : select.value === "true";
    setPath(state.input, path, next);
    markDirty();
  });
  return fieldWrap(label, select, hint);
}

function formatHeadlineMoney(raw, jurisdiction) {
  if (raw === null || raw === undefined || raw === "") return `${jurisdiction}: not calculated`;
  const amount = Number(raw);
  if (!Number.isFinite(amount)) return `${jurisdiction}: ${String(raw)}`;
  const money = Math.abs(amount).toLocaleString("en-CA", { style: "currency", currency: "CAD" });
  return amount >= 0 ? `${jurisdiction} prepared refund: ${money}` : `${jurisdiction} prepared balance owing: ${money}`;
}

function formatLineValue(value) {
  if (value === true) return "Yes";
  if (value === false) return "No";
  if (value === null || value === undefined) return "";
  return String(value);
}

function detailList(title, items) {
  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = title;
  details.append(summary);
  if (items?.length) {
    const list = document.createElement("ul");
    items.forEach((item) => list.append(node("li", null, item)));
    details.append(list);
  } else {
    details.append(node("p", "muted", "None supplied."));
  }
  return details;
}

function checkbox(path, label) {
  const wrap = node("label", "checkbox-line");
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = getPath(state.input, path) === true;
  input.addEventListener("change", () => {
    setPath(state.input, path, input.checked);
    markDirty();
  });
  wrap.append(input, node("span", null, label));
  return wrap;
}

function renderLinks(container, links) {
  container.replaceChildren();
  for (const link of links) {
    const a = document.createElement("a");
    a.href = link.url;
    a.target = "_blank";
    a.rel = "noreferrer";
    a.textContent = link.label;
    container.append(a);
  }
}

function renderScope() {
  const form = $("#scope-form");
  form.replaceChildren();
  form.append(
    provinceSelect(),
    numberInput("tax_year", "Tax year", "This release supports 2025 only."),
    boolSelect("taxpayer.full_year_canada_resident", booleanLabels.full_year_canada_resident),
    boolSelect("taxpayer.full_year_quebec_resident", booleanLabels.full_year_quebec_resident),
    numberInput("taxpayer.age_dec31", "Age on December 31", "Employment calculations are supported for ages 19 to 64; age 18 is blocked pending QPP prorating."),
    choiceInput("taxpayer.marital_status", "Marital status", [["single", "Single"], ["married", "Married"], ["common_law", "Common-law"], ["separated", "Separated"], ["divorced", "Divorced"], ["widowed", "Widowed"]], "Only single returns are calculated in this release."),
    numberInput("taxpayer.dependant_count", "Dependants", "Supported profile: zero."),
    boolSelect(
      "taxpayer.was_full_time_student_more_than_13_weeks",
      booleanLabels.was_full_time_student_more_than_13_weeks,
      "Federal Canada workers benefit uses this threshold.",
    ),
    boolSelect(
      "taxpayer.has_student_loan_interest",
      booleanLabels.has_student_loan_interest,
      "Answer Yes only for qualifying government student-loan interest.",
    ),
  );

  const group = node("div", "field full");
  group.append(
    node("h3", null, "Unsupported situation declaration"),
    node("p", "muted", "Check anything that applies, or confirm that none of these apply. Unknown answers block calculation."),
  );
  const none = node("label", "checkbox-line");
  const noneInput = document.createElement("input");
  noneInput.type = "checkbox";
  noneInput.checked = unsupportedFields.every((field) => state.input.taxpayer[field] === false);
  none.append(noneInput, node("span", null, "I reviewed this list and none of these situations apply."));
  noneInput.addEventListener("change", (event) => {
    if (event.target.checked) {
      unsupportedFields.forEach((field) => {
        state.input.taxpayer[field] = false;
      });
      renderScope();
      markDirty();
    }
  });
  group.append(none);
  for (const field of unsupportedFields) {
    const line = node("label", "checkbox-line");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = state.input.taxpayer[field] === true;
    input.addEventListener("change", () => {
      state.input.taxpayer[field] = input.checked ? true : null;
      markDirty();
    });
    line.append(input, node("span", null, booleanLabels[field]));
    group.append(line);
  }
  form.append(group);

  const filingGroup = node("div", "field full");
  filingGroup.append(
    node("h3", null, "Additional T1 and TP-1 filing screens"),
    node("p", "muted", "These printed-return situations require lines outside the supported salary/student profile. Answer each one, or confirm that none apply."),
  );
  const noneFiling = node("label", "checkbox-line");
  const noneFilingInput = document.createElement("input");
  noneFilingInput.type = "checkbox";
  noneFilingInput.checked = additionalReturnScreenFields.every(
    (field) => state.input.additional_return_screens[field] === false,
  );
  noneFiling.append(noneFilingInput, node("span", null, "I reviewed these filing screens and none apply."));
  noneFilingInput.addEventListener("change", (event) => {
    if (event.target.checked) {
      additionalReturnScreenFields.forEach((field) => {
        state.input.additional_return_screens[field] = false;
      });
      renderScope();
      markDirty();
    }
  });
  filingGroup.append(noneFiling);
  for (const field of additionalReturnScreenFields) {
    filingGroup.append(
      boolSelect(`additional_return_screens.${field}`, booleanLabels[field]),
    );
  }
  form.append(filingGroup);
}

function renderInventory() {
  const form = $("#inventory-form");
  form.replaceChildren();
  form.append(
    checkbox("inventory.income_sources_reviewed", "I checked employment, bank, school, and other possible issuers."),
    checkbox("inventory.deductions_reviewed", "I reviewed deduction evidence and limits."),
    checkbox("inventory.credits_reviewed", "I reviewed credit evidence and eligibility."),
    checkbox("inventory.cra_records_reviewed", "I checked CRA My Account for 2025 slips and NOA limits."),
    checkbox("inventory.revenu_quebec_records_reviewed", "I checked Revenu Quebec My Account for 2025 slips."),
    boolSelect("inventory.no_income_sources", "No income sources", "Choose No when slips are present."),
  );
}

function newSlip(type = "T4") {
  const slip = {
    slip_type: type,
    document_id: "",
    issuer_id: "",
    tax_year: 2025,
    province_of_employment: type === "T4" ? "QC" : null,
    cpp_qpp_exempt: null,
    ei_exempt: null,
    ppip_exempt: null,
    rrsp_period: null,
    rl1_box_o_allocations: null,
    confirmed: null,
    fields: {},
  };
  return slip;
}

function renderSlips() {
  const list = $("#slips");
  list.replaceChildren();
  if (state.input.slips.length === 0) {
    list.append(node("p", "muted", "No slips entered yet."));
    return;
  }
  state.input.slips.forEach((slip, index) => {
    const card = node("article", "slip-card");
    const title = node("div", "slip-title");
    title.append(node("h3", null, `Slip ${index + 1}`));
    const remove = node("button", "ghost", "Remove");
    remove.type = "button";
    remove.addEventListener("click", () => {
      revokePdf(index);
      state.input.slips.splice(index, 1);
      state.pdfUrls.splice(index, 1);
      renderSlips();
      markDirty();
    });
    title.append(remove);
    card.append(title);

    const fields = node("div", "grid-form");
    const typeSelect = document.createElement("select");
    for (const type of state.schema.supported_slips) {
      const option = document.createElement("option");
      option.value = type;
      option.textContent = type;
      typeSelect.append(option);
    }
    typeSelect.value = slip.slip_type;
    typeSelect.addEventListener("change", () => {
      slip.slip_type = typeSelect.value;
      if (slip.slip_type === "T4" && !slip.province_of_employment) slip.province_of_employment = "QC";
      if (slip.slip_type !== "T4") {
        slip.cpp_qpp_exempt = null;
        slip.ei_exempt = null;
        slip.ppip_exempt = null;
      }
      if (slip.slip_type !== "RRSP_RECEIPT") slip.rrsp_period = null;
      if (slip.slip_type !== "RL1") slip.rl1_box_o_allocations = null;
      renderSlips();
      markDirty();
    });
    fields.append(fieldWrap("Slip type", typeSelect));
    fields.append(slipTextInput(slip, "document_id", "Document reference"));
    fields.append(slipTextInput(slip, "issuer_id", "Issuer or payer"));
    fields.append(slipNumberInput(slip, "tax_year", "Slip tax year"));
    fields.append(slipTextInput(slip, "province_of_employment", "Province of employment", "Required for T4; use QC for this release."));
    if (slip.slip_type === "T4") {
      fields.append(slipBoolSelect(slip, "cpp_qpp_exempt", "T4 box 28 CPP/QPP exempt"));
      fields.append(slipBoolSelect(slip, "ei_exempt", "T4 box 28 EI exempt"));
      fields.append(slipBoolSelect(slip, "ppip_exempt", "T4 box 28 PPIP exempt"));
    }
    if (slip.slip_type === "RRSP_RECEIPT") {
      fields.append(
        slipChoiceInput(slip, "rrsp_period", "RRSP receipt period", [
          ["march_to_december_2025", "March to December 2025"],
          ["first_60_days_2026", "First 60 days of 2026"],
        ]),
      );
    }
    fields.append(slipBoolSelect(slip, "confirmed", "Confirmed against source document"));
    card.append(fields);

    const evidence = node("div", "field full");
    evidence.append(
      node("span", "label", "Local PDF evidence preview"),
      node(
        "span",
        "hint",
        "Read the slip and enter the boxes yourself. This app does not upload, OCR, or extract PDF boxes.",
      ),
    );
    const pdfLabel = node("label", "file-button");
    pdfLabel.append(node("span", null, "Choose PDF"));
    const pdfInput = document.createElement("input");
    pdfInput.type = "file";
    pdfInput.accept = "application/pdf,.pdf";
    pdfInput.addEventListener("change", () => {
      const file = pdfInput.files?.[0];
      revokePdf(index);
      if (!file) {
        renderSlips();
        return;
      }
      if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
        setBanner("Only local PDF files can be previewed beside a slip.");
        pdfInput.value = "";
        renderSlips();
        return;
      }
      state.pdfUrls[index] = URL.createObjectURL(file);
      renderSlips();
    });
    pdfLabel.append(pdfInput);
    evidence.append(pdfLabel);
    if (state.pdfUrls[index]) {
      const frame = document.createElement("iframe");
      frame.className = "pdf-preview";
      frame.title = `Local PDF preview for slip ${index + 1}`;
      frame.src = state.pdfUrls[index];
      evidence.append(frame);
    }
    card.append(evidence);

    const table = node("table", "field-table");
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    ["Box / field", "Entered value", ""].forEach((heading) => headRow.append(node("th", null, heading)));
    thead.append(headRow);
    const tbody = document.createElement("tbody");
    for (const [key, value] of Object.entries(slip.fields || {})) {
      const row = document.createElement("tr");
      const keyInput = document.createElement("input");
      keyInput.value = key;
      keyInput.addEventListener("change", () => {
        const nextKey = keyInput.value.trim();
        if (!nextKey || nextKey === key) return;
        slip.fields[nextKey] = slip.fields[key];
        delete slip.fields[key];
        renderSlips();
        markDirty();
      });
      const valueInput = document.createElement("input");
      valueInput.value = value ?? "";
      valueInput.addEventListener("input", () => {
        slip.fields[key] = valueInput.value.trim();
        markDirty();
      });
      const removeField = node("button", "ghost", "Remove");
      removeField.type = "button";
      removeField.addEventListener("click", () => {
        delete slip.fields[key];
        renderSlips();
        markDirty();
      });
      row.append(wrapCell(keyInput), wrapCell(valueInput), wrapCell(removeField));
      tbody.append(row);
    }
    table.append(thead, tbody);
    card.append(table);
    const addField = node("button", null, "Add box");
    addField.type = "button";
    addField.addEventListener("click", () => {
      const candidates = slipHints[slip.slip_type] || ["amount"];
      const key = candidates.find((candidate) => !(candidate in slip.fields)) || `field_${Object.keys(slip.fields).length + 1}`;
      slip.fields[key] = "";
      renderSlips();
      markDirty();
    });
    card.append(addField);
    if (slip.slip_type === "RL1") {
      renderRl1BoxOAllocations(card, slip);
    }
    list.append(card);
  });
}

function renderRl1BoxOAllocations(card, slip) {
  const section = node("div", "field full");
  section.append(
    node("span", "label", "RL-1 box O code allocations"),
    node(
      "span",
      "hint",
      "Use RB/RZ-RB for scholarships and RU/RZ-RU for RESP educational assistance payments. Totals must match the T4A and fact entries from the same issuer.",
    ),
  );
  const allocations = slip.rl1_box_o_allocations || {};
  const table = node("table", "field-table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["Code", "Amount", ""].forEach((heading) => headRow.append(node("th", null, heading)));
  thead.append(headRow);
  const tbody = document.createElement("tbody");
  for (const [code, amount] of Object.entries(allocations)) {
    const row = document.createElement("tr");
    const codeSelect = document.createElement("select");
    for (const [value, text] of rl1BoxOCodes) codeSelect.append(new Option(text, value));
    codeSelect.value = code;
    codeSelect.addEventListener("change", () => {
      const next = codeSelect.value;
      if (next === code) return;
      slip.rl1_box_o_allocations = slip.rl1_box_o_allocations || {};
      slip.rl1_box_o_allocations[next] = slip.rl1_box_o_allocations[code];
      delete slip.rl1_box_o_allocations[code];
      renderSlips();
      markDirty();
    });
    const amountInput = document.createElement("input");
    amountInput.inputMode = "decimal";
    amountInput.value = amount ?? "";
    amountInput.addEventListener("input", () => {
      slip.rl1_box_o_allocations = slip.rl1_box_o_allocations || {};
      slip.rl1_box_o_allocations[code] = amountInput.value.trim() || null;
      markDirty();
    });
    const remove = node("button", "ghost", "Remove");
    remove.type = "button";
    remove.addEventListener("click", () => {
      delete slip.rl1_box_o_allocations[code];
      if (Object.keys(slip.rl1_box_o_allocations).length === 0) slip.rl1_box_o_allocations = null;
      renderSlips();
      markDirty();
    });
    row.append(wrapCell(codeSelect), wrapCell(amountInput), wrapCell(remove));
    tbody.append(row);
  }
  table.append(thead, tbody);
  section.append(table);
  const add = node("button", null, "Add RL-1 box O allocation");
  add.type = "button";
  add.addEventListener("click", () => {
    slip.rl1_box_o_allocations = slip.rl1_box_o_allocations || {};
    const code = rl1BoxOCodes.find(([candidate]) => !(candidate in slip.rl1_box_o_allocations))?.[0] || "RB";
    slip.rl1_box_o_allocations[code] = "";
    renderSlips();
    markDirty();
  });
  section.append(add);
  card.append(section);
}

function wrapCell(child) {
  const td = document.createElement("td");
  td.append(child);
  return td;
}

function slipTextInput(slip, key, label, hint) {
  const input = document.createElement("input");
  input.value = slip[key] ?? "";
  input.addEventListener("input", () => {
    slip[key] = input.value.trim() || null;
    markDirty();
  });
  return fieldWrap(label, input, hint);
}

function slipNumberInput(slip, key, label) {
  const input = document.createElement("input");
  input.type = "number";
  input.step = "1";
  input.value = slip[key] ?? "";
  input.addEventListener("input", () => {
    slip[key] = input.value === "" ? null : Number(input.value);
    markDirty();
  });
  return fieldWrap(label, input);
}

function slipBoolSelect(slip, key, label) {
  const select = document.createElement("select");
  [
    ["", "Unknown"],
    ["true", "Yes"],
    ["false", "No"],
  ].forEach(([value, text]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = text;
    select.append(option);
  });
  select.value = slip[key] === true ? "true" : slip[key] === false ? "false" : "";
  select.addEventListener("change", () => {
    slip[key] = select.value === "" ? null : select.value === "true";
    markDirty();
  });
  return fieldWrap(label, select);
}

function slipChoiceInput(slip, key, label, options) {
  const select = document.createElement("select");
  select.append(new Option("Unknown", ""));
  for (const [value, text] of options) select.append(new Option(text, value));
  select.value = slip[key] ?? "";
  select.addEventListener("change", () => {
    slip[key] = select.value || null;
    markDirty();
  });
  return fieldWrap(label, select);
}

function sectionCard(title, hint) {
  const section = node("section", "form-card full");
  section.append(node("h3", null, title));
  if (hint) section.append(node("p", "muted", hint));
  return section;
}

function declareNoScholarships() {
  state.input.scholarships.reviewed = true;
  state.input.scholarships.awards = [];
  state.input.scholarships.part_time_programs = [];
  renderFacts();
  markDirty();
}

function addScholarshipAward() {
  const awards = Array.isArray(state.input.scholarships.awards) ? state.input.scholarships.awards : [];
  awards.push({
    award_id: `award-${awards.length + 1}`,
    issuer_id: "",
    amount: null,
    category: null,
    qualifying_student: null,
    attendance: null,
    intended_enrolment_support: null,
    part_time_program_id: null,
  });
  state.input.scholarships.awards = awards;
  renderFacts();
  markDirty();
}

function addScholarshipProgram() {
  const programs = Array.isArray(state.input.scholarships.part_time_programs)
    ? state.input.scholarships.part_time_programs
    : [];
  programs.push({
    program_id: `program-${programs.length + 1}`,
    eligible_tuition_and_required_materials: null,
  });
  state.input.scholarships.part_time_programs = programs;
  renderFacts();
  markDirty();
}

function renderScholarships() {
  const section = sectionCard(
    "Scholarships, bursaries, and awards",
    "Use this only for ordinary post-secondary awards that reconcile by issuer to T4A box 105 and RL-1 box O code RB/RZ-RB. Other award categories are recognized so the calculator can block them.",
  );
  section.append(checkbox("scholarships.reviewed", "I reviewed T4A/RL-1 scholarship, bursary, and award receipts."));
  const none = node("button", "ghost", "I reviewed these receipts and have no scholarship awards to report");
  none.type = "button";
  none.addEventListener("click", declareNoScholarships);
  section.append(none);

  const awards = state.input.scholarships.awards;
  if (!Array.isArray(awards) || awards.length === 0) {
    section.append(node("p", "muted", "No scholarship award rows entered."));
  } else {
    awards.forEach((award, index) => {
      const card = node("article", "slip-card");
      const title = node("div", "slip-title");
      title.append(node("h4", null, `Award ${index + 1}`));
      const remove = node("button", "ghost", "Remove");
      remove.type = "button";
      remove.addEventListener("click", () => {
        awards.splice(index, 1);
        renderFacts();
        markDirty();
      });
      title.append(remove);
      card.append(title);
      const fields = node("div", "grid-form");
      fields.append(
        textInput(`scholarships.awards.${index}.award_id`, "Award reference"),
        textInput(`scholarships.awards.${index}.issuer_id`, "Issuer", "Must match the T4A/RL-1 issuer for reconciliation."),
        moneyInput(`scholarships.awards.${index}.amount`, "Award amount"),
        choiceInput(`scholarships.awards.${index}.category`, "Award category", scholarshipCategories),
        boolSelect(`scholarships.awards.${index}.qualifying_student`, "Qualifying student for the award"),
        choiceInput(`scholarships.awards.${index}.attendance`, "Attendance category", attendanceOptions),
        moneyInput(`scholarships.awards.${index}.intended_enrolment_support`, "Amount intended to support enrolment"),
        textInput(
          `scholarships.awards.${index}.part_time_program_id`,
          "Part-time program reference",
          "Required only for part-time awards; match a program cost pool below.",
        ),
      );
      card.append(fields);
      section.append(card);
    });
  }
  const add = node("button", null, "Add scholarship award");
  add.type = "button";
  add.addEventListener("click", addScholarshipAward);
  section.append(add);

  const programsTitle = node("h4", null, "Part-time program cost pools");
  section.append(programsTitle);
  section.append(
    node(
      "p",
      "muted",
      "If a scholarship award is for part-time attendance, enter each program cost pool once and reference its ID on the award row.",
    ),
  );
  const programs = state.input.scholarships.part_time_programs;
  if (!Array.isArray(programs) || programs.length === 0) {
    section.append(node("p", "muted", "No part-time program cost pools entered."));
  } else {
    programs.forEach((program, index) => {
      const card = node("article", "slip-card");
      const title = node("div", "slip-title");
      title.append(node("h4", null, `Program ${index + 1}`));
      const remove = node("button", "ghost", "Remove");
      remove.type = "button";
      remove.addEventListener("click", () => {
        programs.splice(index, 1);
        renderFacts();
        markDirty();
      });
      title.append(remove);
      card.append(title);
      const fields = node("div", "grid-form");
      fields.append(
        textInput(`scholarships.part_time_programs.${index}.program_id`, "Program reference"),
        moneyInput(
          `scholarships.part_time_programs.${index}.eligible_tuition_and_required_materials`,
          "Eligible tuition and required materials",
        ),
      );
      card.append(fields);
      section.append(card);
    });
  }
  const addProgram = node("button", "ghost", "Add part-time program cost pool");
  addProgram.type = "button";
  addProgram.addEventListener("click", addScholarshipProgram);
  section.append(addProgram);
  return section;
}

function declareNoRespEap() {
  state.input.resp_eap.reviewed = true;
  state.input.resp_eap.has_other_resp_payments = false;
  state.input.resp_eap.qesi_cumulative_amount_over_3600 = false;
  state.input.resp_eap.payments = [];
  renderFacts();
  markDirty();
}

function addRespPayment() {
  const payments = Array.isArray(state.input.resp_eap.payments) ? state.input.resp_eap.payments : [];
  payments.push({
    payment_id: `resp-${payments.length + 1}`,
    issuer_id: "",
    amount: null,
  });
  state.input.resp_eap.payments = payments;
  renderFacts();
  markDirty();
}

function renderRespEap() {
  const section = sectionCard(
    "RESP educational assistance payments",
    "Enter beneficiary EAP amounts that reconcile by issuer to T4A box 042 and RL-1 box O code RU/RZ-RU. T4A box 040 and other RESP payment types block calculation.",
  );
  section.append(
    checkbox("resp_eap.reviewed", "I reviewed RESP payment slips and account records."),
    boolSelect("resp_eap.has_other_resp_payments", "Any RESP payments other than beneficiary educational assistance payments"),
    boolSelect("resp_eap.qesi_cumulative_amount_over_3600", "Cumulative QESI amount over $3,600"),
  );
  const none = node("button", "ghost", "I reviewed RESP records; no EAP payments or special RESP branches apply");
  none.type = "button";
  none.addEventListener("click", declareNoRespEap);
  section.append(none);

  const payments = state.input.resp_eap.payments;
  if (!Array.isArray(payments) || payments.length === 0) {
    section.append(node("p", "muted", "No RESP EAP payment rows entered."));
  } else {
    payments.forEach((payment, index) => {
      const card = node("article", "slip-card");
      const title = node("div", "slip-title");
      title.append(node("h4", null, `RESP EAP ${index + 1}`));
      const remove = node("button", "ghost", "Remove");
      remove.type = "button";
      remove.addEventListener("click", () => {
        payments.splice(index, 1);
        renderFacts();
        markDirty();
      });
      title.append(remove);
      card.append(title);
      const fields = node("div", "grid-form");
      fields.append(
        textInput(`resp_eap.payments.${index}.payment_id`, "Payment reference"),
        textInput(`resp_eap.payments.${index}.issuer_id`, "Issuer", "Must match the T4A/RL-1 issuer for reconciliation."),
        moneyInput(`resp_eap.payments.${index}.amount`, "Gross EAP amount"),
      );
      card.append(fields);
      section.append(card);
    });
  }
  const add = node("button", null, "Add RESP EAP payment");
  add.type = "button";
  add.addEventListener("click", addRespPayment);
  section.append(add);
  return section;
}

function renderFacts() {
  const form = $("#facts-form");
  form.replaceChildren();
  form.append(
    boolSelect("federal_tuition.has_current_tuition", "Federal current-year tuition from T2202"),
    moneyInput("federal_tuition.t2202_eligible_fees", "T2202 eligible fees"),
    boolSelect("federal_tuition.has_prior_unused", "Federal prior unused tuition from NOA"),
    moneyInput("federal_tuition.prior_unused_amount", "Federal prior unused amount"),
    boolSelect("federal_tuition.wants_transfer", "Transfer federal tuition"),
    moneyInput("federal_tuition.transfer_amount", "Federal transfer amount"),
    boolSelect("federal_tuition.wants_canada_training_credit", "Claim Canada training credit"),
    moneyInput("federal_tuition.canada_training_credit_limit", "Canada training credit limit"),
    moneyInput("federal_tuition.canada_training_credit_claim", "Canada training credit claim"),
    boolSelect("quebec_tuition.has_current_tuition", "Quebec current-year tuition receipts"),
    boolSelect("quebec_tuition.institution_outside_quebec", "Quebec tuition institution outside Quebec"),
    moneyInput("quebec_tuition.eligible_tuition_or_exam_receipts", "Quebec eligible tuition or exam fees"),
    boolSelect("quebec_tuition.has_prior_unused", "Quebec prior unused tuition from notice"),
    moneyInput("quebec_tuition.prior_unused_at_8_percent", "Quebec prior unused fees at 8%"),
    moneyInput("quebec_tuition.prior_unused_at_20_percent", "Quebec prior unused fees at 20%"),
    boolSelect("quebec_tuition.wants_transfer", "Transfer Quebec tuition"),
    moneyInput("quebec_tuition.transfer_amount", "Quebec transfer amount"),
    boolSelect("rrsp.has_contributions", "RRSP contributions"),
    boolSelect("rrsp.has_prior_unused_contributions", "Prior unused RRSP contributions on latest NOA"),
    moneyInput("rrsp.contribution_receipts", "RRSP contribution receipts"),
    moneyInput("rrsp.march_to_december_contributions", "RRSP receipts for March to December 2025"),
    moneyInput("rrsp.first_60_days_contributions", "RRSP receipts for the first 60 days of 2026"),
    moneyInput("rrsp.prior_unused_contributions", "Prior unused RRSP contributions"),
    moneyInput("rrsp.deduction_limit", "RRSP deduction limit from NOA"),
    moneyInput("rrsp.deduction_requested", "RRSP deduction requested"),
    boolSelect("rrsp.has_hbp_or_llp_activity", "HBP or LLP activity"),
    checkbox("instalments.federal_reviewed", "I reviewed 2025 federal instalment payments."),
    moneyInput("instalments.federal_paid", "Federal instalments paid"),
    checkbox("instalments.quebec_reviewed", "I reviewed 2025 Quebec instalment payments."),
    moneyInput("instalments.quebec_paid", "Quebec instalments paid"),
    checkbox("quebec_schedule_b.living_alone_reviewed", "I reviewed Quebec Schedule B living-alone eligibility."),
    boolSelect("quebec_schedule_b.eligible_for_living_alone_amount", "Eligible for the Quebec living-alone amount"),
    checkbox("student_loan_interest.reviewed", "I reviewed qualifying government student-loan interest."),
    boolSelect("student_loan_interest.qualifying_government_loans_confirmed", "Interest is only from qualifying government student loans"),
    moneyInput("student_loan_interest.federal_current_year_paid", "Federal student-loan interest paid in 2025"),
    moneyInput("student_loan_interest.federal_unused_2020", "Federal unused student-loan interest from 2020"),
    moneyInput("student_loan_interest.federal_unused_2021", "Federal unused student-loan interest from 2021"),
    moneyInput("student_loan_interest.federal_unused_2022", "Federal unused student-loan interest from 2022"),
    moneyInput("student_loan_interest.federal_unused_2023", "Federal unused student-loan interest from 2023"),
    moneyInput("student_loan_interest.federal_unused_2024", "Federal unused student-loan interest from 2024"),
    moneyInput("student_loan_interest.federal_claim_amount", "Federal student-loan interest claim"),
    moneyInput("student_loan_interest.quebec_prior_unused", "Quebec prior unused student-loan interest"),
    moneyInput("student_loan_interest.quebec_current_year_paid", "Quebec student-loan interest paid in 2025"),
    moneyInput("student_loan_interest.quebec_claim_amount", "Quebec student-loan interest claim"),
    renderScholarships(),
    renderRespEap(),
    checkbox("drug_insurance.reviewed", "I reviewed all 12 months of Quebec prescription-drug coverage."),
    monthInput("drug_insurance.group_plan_months", "Months covered by a private/group drug plan", "Comma-separated month numbers, or leave unknown."),
    choiceInput("drug_insurance.group_plan_source", "Private/group plan source", [["self", "My plan"], ["parent", "Parent's plan"]]),
    monthInput("drug_insurance.eligible_student_months", "Months exempt as an eligible full-time student"),
    boolSelect("drug_insurance.other_exemption_applies", "Another Schedule K exemption applies"),
    checkbox("refundable_credits.work_premium_answers_reviewed", "I reviewed Quebec work premium eligibility."),
    checkbox("refundable_credits.solidarity_answers_reviewed", "I reviewed Quebec solidarity credit eligibility."),
    checkbox("refundable_credits.canada_workers_benefit_answers_reviewed", "I reviewed Canada workers benefit eligibility."),
    checkbox("refundable_credits.rl19_advance_payments_reviewed", "I reviewed RL-19 advance payments."),
    moneyInput("refundable_credits.rl19_box_a", "RL-19 box A advance payments"),
    moneyInput("refundable_credits.rl19_box_b", "RL-19 box B advance payments"),
    boolSelect("refundable_credits.rl19_has_other_advance_boxes", "RL-19 boxes C, D, G, or H have amounts"),
    boolSelect("refundable_credits.cwb_incarcerated_90_days", "Incarcerated for 90 days or more for CWB"),
    boolSelect("refundable_credits.cwb_foreign_officer_exempt", "Foreign officer or servant exemption for CWB"),
    moneyInput("refundable_credits.advanced_cwb_paid", "Advanced Canada workers benefit already paid"),
    moneyInput("refundable_credits.advanced_cwb_disability_paid", "Advanced Canada workers benefit disability supplement already paid"),
    boolSelect("refundable_credits.work_premium_eligible_status", "Eligible status for Quebec work premium"),
    boolSelect(
      "refundable_credits.quebec_work_premium_full_time_student",
      "Full-time student for Quebec work premium",
      linkHint(
        "This is a separate Quebec definition: term began during 2025, at least 9 hours a week, and term completed.",
        "https://www.revenuquebec.ca/en/definitions/full-time-student/",
        "Revenu Quebec definition",
      ),
    ),
    boolSelect("refundable_credits.transferred_schedule_s_amount", "Transferred an amount from Schedule S"),
    boolSelect("refundable_credits.family_allowance_received_for_self", "Family allowance was received for you"),
    boolSelect("refundable_credits.turned_18_before_december", "Turned 18 before December 2025"),
    boolSelect("refundable_credits.designated_as_dependent_child", "Designated as someone else's dependent child"),
    boolSelect("refundable_credits.incarcerated_over_183_days", "Incarcerated over 183 days"),
    boolSelect("refundable_credits.adapted_work_premium_eligible", "Adapted work premium eligible"),
    numberInput("refundable_credits.work_premium_supplement_months", "Work premium supplement months"),
    boolSelect("refundable_credits.request_tax_shield", "Request Quebec tax shield"),
    boolSelect("refundable_credits.wants_solidarity_credit", "Claim Quebec solidarity credit"),
    boolSelect("refundable_credits.solidarity_eligible_immigration_status", "Solidarity eligible immigration status"),
    boolSelect("refundable_credits.solidarity_refugee_claimant_dec31", "Refugee claimant on December 31"),
    boolSelect("refundable_credits.solidarity_family_allowance_paid_for_user_december", "Family allowance paid for you in December"),
    boolSelect("refundable_credits.solidarity_turned_18_in_december", "Turned 18 in December"),
    boolSelect("refundable_credits.solidarity_lived_alone_all_year", "Lived alone all year"),
    boolSelect("refundable_credits.solidarity_address_same_as_return", "Dwelling address same as return"),
    choiceInput("refundable_credits.solidarity_occupancy", "Solidarity occupancy", [["tenant", "Tenant"], ["owner", "Owner"], ["neither", "Neither"]]),
    textInput("refundable_credits.solidarity_rl31_dwelling_number", "RL-31 dwelling number"),
    textInput("refundable_credits.solidarity_rl31_occupant_number", "RL-31 occupant number"),
    boolSelect("refundable_credits.solidarity_owner_has_municipal_tax_bill", "Owner has a municipal tax bill"),
    textInput("refundable_credits.solidarity_owner_roll_number", "Owner roll number"),
    numberInput("refundable_credits.solidarity_owners_in_dwelling", "Owners living in the dwelling"),
  );
}

function renderResult(response) {
  state.result = response.result;
  state.responseSources = response.sources || {};
  $("#save-result").disabled = false;
  $("#print-packet").disabled = false;
  $("#calculation-state").textContent =
    state.result.status === "complete" ? "Calculation complete for the supported situation." : "Calculation is blocked.";
  renderProblems();
  renderLineTables();
}

function renderProblems() {
  const container = $("#problems");
  container.replaceChildren();
  const blockers = state.result?.blockers || [];
  if (blockers.length === 0) {
    container.append(node("p", "muted", "Calculation can continue for the supported situation."));
    return;
  }
  for (const blocker of blockers) {
    const card = node("article", "problem-card");
    card.append(node("span", "pill", blocker.code));
    card.append(node("h3", null, blocker.message));
    card.append(node("p", "muted", blocker.resolution));
    if (blocker.input_paths?.length) {
      card.append(node("p", "hint", `Fields: ${blocker.input_paths.join(", ")}`));
    }
    appendSources(card, blocker.source_ids || []);
    container.append(card);
  }
}

function renderLineTables() {
  const container = $("#results");
  container.replaceChildren();
  if (state.result?.status === "complete") {
    const headline = node("section", "result-block");
    headline.append(node("h3", null, "Refund or balance"));
    const cards = node("div", "result-cards");
    cards.append(
      node("p", "money-card", formatHeadlineMoney(state.result.federal_refund_or_balance, "Federal")),
      node("p", "money-card", formatHeadlineMoney(state.result.quebec_refund_or_balance, "Quebec")),
    );
    headline.append(cards);
    if (state.result.warnings?.length) {
      const warningBox = node("div", "warning-card");
      warningBox.append(node("h4", null, "Preparation warnings"));
      const list = document.createElement("ul");
      state.result.warnings.forEach((warning) => list.append(node("li", null, warning)));
      warningBox.append(list);
      headline.append(warningBox);
    }
    container.append(headline);
  }
  const lines = state.result?.lines || [];
  if (lines.length === 0) {
    container.append(node("p", "muted", "No form lines are available until the return calculator completes."));
    return;
  }
  const byForm = new Map();
  for (const line of lines) {
    if (!byForm.has(line.form_id)) byForm.set(line.form_id, []);
    byForm.get(line.form_id).push(line);
  }
  const order = Array.from(byForm.keys()).sort((a, b) => {
    const rank = (form) => (form === "T1" ? 0 : form === "TP1" ? 1 : 2);
    return rank(a) - rank(b) || a.localeCompare(b);
  });
  for (const formId of order) {
    const formLines = byForm.get(formId);
    const isMain = formId === "T1" || formId === "TP1";
    const block = isMain ? node("section", "result-block") : document.createElement("details");
    if (!isMain) block.className = "result-block schedule-details";
    const heading = isMain ? node("h3", null, formId) : document.createElement("summary");
    heading.textContent = isMain ? formId : `${formId} schedule lines`;
    block.append(heading);
    const table = node("table", "line-table");
    const thead = document.createElement("thead");
    const head = document.createElement("tr");
    ["Line", "Label", "Value", "Status", "Sources", "Details"].forEach((heading) =>
      head.append(node("th", null, heading)),
    );
    thead.append(head);
    const tbody = document.createElement("tbody");
    for (const line of formLines) {
      const row = document.createElement("tr");
      row.append(
        node("td", null, line.line_id),
        node("td", null, line.explanation || `Line ${line.line_id}`),
        node("td", null, formatLineValue(line.value)),
        node("td", null, line.status),
      );
      const sourceCell = document.createElement("td");
      appendSources(sourceCell, line.source_ids || []);
      const detailsCell = document.createElement("td");
      const detailItems = [];
      if (line.inputs?.length) detailItems.push(...line.inputs.map((input) => `Input: ${input}`));
      if (line.formula_id) detailItems.push(`Calculation step: ${line.formula_id}`);
      detailsCell.append(detailList("Show", detailItems));
      row.append(sourceCell, detailsCell);
      tbody.append(row);
    }
    table.append(thead, tbody);
    block.append(table);
    container.append(block);
  }
}

function appendSources(container, ids) {
  ids.forEach((id, index) => {
    const source = state.responseSources[id] || state.schema.sources[id];
    if (!source) {
      container.append(node("span", null, id));
      return;
    }
    if (index > 0) container.append(document.createTextNode(" "));
    const link = document.createElement("a");
    link.href = source.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = source.form_id || id;
    container.append(link);
  });
}

function importedPayloadInput(parsed) {
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return parsed;
  return Object.prototype.hasOwnProperty.call(parsed, "input") ? parsed.input : parsed;
}

function missingTemplateKeys(template, candidate, prefix = "") {
  if (Array.isArray(template)) return Array.isArray(candidate) ? [] : [prefix || "input"];
  if (!template || typeof template !== "object") return [];
  if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) return [prefix || "input"];

  const missing = [];
  for (const key of Object.keys(template)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (!Object.prototype.hasOwnProperty.call(candidate, key)) {
      missing.push(path);
      continue;
    }
    missing.push(...missingTemplateKeys(template[key], candidate[key], path));
  }
  return missing;
}

function normalizeImportedInput(parsed, schema = state.schema) {
  const candidate = importedPayloadInput(parsed);
  if (!schema?.blank_input) {
    return { ok: false, message: "The local workspace schema is not loaded yet." };
  }
  const missing = missingTemplateKeys(schema.blank_input, candidate);
  if (missing.length) {
    const shown = missing.slice(0, 6).join(", ");
    const suffix = missing.length > 6 ? ", ..." : "";
    return {
      ok: false,
      message: `The selected JSON does not match the current TaxAgent input shape. Missing or invalid fields: ${shown}${suffix}.`,
    };
  }
  return { ok: true, input: clone(candidate) };
}

function showBlockedResult(message, code = "request_failed", resolution = "Review the inputs and try again.", inputPaths = []) {
  state.result = {
    status: "blocked",
    blockers: [
      {
        code,
        message,
        resolution,
        input_paths: inputPaths,
        source_ids: [],
      },
    ],
    lines: [],
  };
  state.responseSources = {};
  $("#save-result").disabled = true;
  $("#print-packet").disabled = true;
  renderProblems();
  renderLineTables();
}

async function calculate() {
  const requestRevision = state.inputRevision;
  const requestId = state.latestCalculateRequest + 1;
  state.latestCalculateRequest = requestId;
  $("#calculation-state").textContent = "Calculating...";
  let response;
  let payload;
  try {
    response = await fetch("/api/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.input),
    });
    payload = await response.json();
  } catch {
    if (requestId !== state.latestCalculateRequest || requestRevision !== state.inputRevision) return;
    $("#calculation-state").textContent = "The local calculator did not return a usable response.";
    showBlockedResult(
      "The local calculator could not be reached or returned an unreadable response.",
      "local_service_error",
      "Make sure taxagent start is still running, then calculate again.",
    );
    return;
  }
  if (requestId !== state.latestCalculateRequest || requestRevision !== state.inputRevision) return;
  if (!response.ok) {
    $("#calculation-state").textContent = "Input was rejected.";
    showBlockedResult(
      payload.detail?.message || "The local calculator rejected the request.",
      payload.detail?.code || "request_failed",
      "Review the inputs and try again.",
      (payload.detail?.errors || []).map((error) => error.path),
    );
    return;
  }
  state.dirty = false;
  renderResult(payload);
}

function downloadJson(filename, data) {
  downloadText(filename, `${JSON.stringify(data, null, 2)}\n`, "application/json");
}

function downloadText(filename, content, type = "text/plain") {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function reviewPacket() {
  const lines = [];
  lines.push("TaxAgent 2025 Quebec local review packet");
  lines.push("No submission. Federal and Quebec filing are separate.");
  lines.push(`Status: ${state.result?.status || "not calculated"}`);
  lines.push(`Input digest: ${state.result?.input_digest || ""}`);
  lines.push("");
  lines.push("Warnings");
  for (const warning of state.result?.warnings || []) {
    lines.push(`- ${warning}`);
  }
  lines.push("");
  lines.push("Blockers");
  for (const blocker of state.result?.blockers || []) {
    lines.push(`- ${blocker.code}: ${blocker.message}`);
    lines.push(`  Resolution: ${blocker.resolution}`);
    if (blocker.input_paths?.length) lines.push(`  Fields: ${blocker.input_paths.join(", ")}`);
  }
  lines.push("");
  lines.push("Form lines");
  for (const line of state.result?.lines || []) {
    lines.push(
      `${line.form_id} line ${line.line_id}: ${line.value ?? ""} [${line.status}] ${line.explanation || ""}`,
    );
    if (line.inputs?.length) lines.push(`  Inputs: ${line.inputs.join(", ")}`);
    if (line.formula_id) lines.push(`  Calculation detail: ${line.formula_id}`);
    if (line.source_ids?.length) lines.push(`  Sources: ${line.source_ids.join(", ")}`);
  }
  lines.push("");
  lines.push("Official source URLs");
  for (const source of Object.values({ ...state.schema.sources, ...state.responseSources })) {
    lines.push(`- ${source.form_id}: ${source.title} ${source.url}`);
  }
  return `${lines.join("\n")}\n`;
}

function renderAll() {
  renderScope();
  renderInventory();
  renderSlips();
  renderFacts();
  renderLinks($("#collection-links"), state.schema.collection_links.slice(0, 2));
  renderLinks($("#handoff-links"), state.schema.collection_links.slice(2));
}

function bindNav() {
  $$(".step-link").forEach((button) => {
    button.addEventListener("click", () => {
      $$(".step-link").forEach((item) => item.classList.remove("active"));
      $$(".step-panel").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      $(`#${button.dataset.step}`).classList.add("active");
    });
  });
}

function bindActions() {
  $("#add-slip").addEventListener("click", () => {
    state.input.slips.push(newSlip());
    renderSlips();
    markDirty();
  });
  $("#calculate-button").addEventListener("click", calculate);
  $("#save-input").addEventListener("click", () => downloadJson("taxagent_2025_qc_input.json", state.input));
  $("#save-result").addEventListener("click", () =>
    downloadJson("taxagent_2025_qc_result.json", { result: state.result, sources: state.responseSources }),
  );
  $("#print-packet").addEventListener("click", () =>
    downloadText("taxagent_2025_qc_review_packet.txt", reviewPacket()),
  );
  $("#reset").addEventListener("click", () => {
    revokeAllPdfs();
    state.input = clone(state.schema.blank_input);
    state.dirty = false;
    state.sampleLoaded = false;
    state.result = null;
    state.responseSources = {};
    bumpInputRevision();
    $("#import-json").value = "";
    $("#calculation-state").textContent = "";
    $("#problems").replaceChildren();
    $("#results").replaceChildren();
    $("#save-result").disabled = true;
    $("#print-packet").disabled = true;
    setBanner("");
    renderAll();
  });
  $("#load-sample").addEventListener("click", async () => {
    if (state.dirty && !window.confirm("Replace the current in-memory input with the labelled sample?")) return;
    revokeAllPdfs();
    const response = await fetch("/api/sample");
    const sample = await response.json();
    state.input = clone(sample.input);
    state.dirty = true;
    state.sampleLoaded = true;
    setBanner(sample.label);
    renderAll();
    markDirty();
  });
  $("#import-json").addEventListener("change", importJson);
}

async function importJson(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  if (file.size > state.schema.max_request_bytes) {
    setBanner("The selected JSON file is too large for this local workspace.");
    event.target.value = "";
    return;
  }
  if (!file.name.toLowerCase().endsWith(".json") && file.type !== "application/json") {
    setBanner("Only structured TaxAgent JSON files are supported. PDF box extraction is not implemented here.");
    event.target.value = "";
    return;
  }
  if (state.dirty && !window.confirm("Replace the current in-memory input with the selected JSON file?")) {
    event.target.value = "";
    return;
  }
  try {
    const parsed = JSON.parse(await file.text());
    const normalized = normalizeImportedInput(parsed);
    if (!normalized.ok) {
      setBanner(normalized.message);
      event.target.value = "";
      return;
    }
    revokeAllPdfs();
    state.input = normalized.input;
    state.sampleLoaded = false;
    state.dirty = true;
    state.result = null;
    state.responseSources = {};
    bumpInputRevision();
    $("#calculation-state").textContent = "Imported JSON into memory. Calculate to validate it.";
    $("#problems").replaceChildren();
    $("#results").replaceChildren();
    $("#save-result").disabled = true;
    $("#print-packet").disabled = true;
    setBanner("Imported JSON into memory. Calculate to validate it.");
    renderAll();
  } catch {
    setBanner("The selected file is not valid JSON.");
    event.target.value = "";
  }
}

async function boot() {
  bindNav();
  bindActions();
  const response = await fetch("/api/schema");
  state.schema = await response.json();
  state.input = clone(state.schema.blank_input);
  renderAll();
}

if (typeof window !== "undefined" && !window.__TAXAGENT_SKIP_BOOT__) {
  boot().catch(() => {
    setBanner("The local workspace could not start. Run taxagent doctor and refresh this page.");
  });
}

if (typeof module !== "undefined") {
  module.exports = {
    state,
    missingTemplateKeys,
    normalizeImportedInput,
    importJson,
    calculate,
    markDirty,
    renderFacts,
    renderResult,
    reviewPacket,
  };
}

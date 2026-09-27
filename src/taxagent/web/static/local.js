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
  immigrated_or_emigrated_in_tax_year: "Immigrated to or emigrated from Canada in the tax year",
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
  "immigrated_or_emigrated_in_tax_year",
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

const candidateMetadataSpecs = {
  T4: {
    province_of_employment: { label: "Province of employment", kind: "text" },
    cpp_qpp_exempt: { label: "T4 box 28 CPP/QPP exempt", kind: "boolean" },
    ei_exempt: { label: "T4 box 28 EI exempt", kind: "boolean" },
    ppip_exempt: { label: "T4 box 28 PPIP exempt", kind: "boolean" },
  },
};

const candidateFieldSpecs = {
  T2202: {
    24: { label: "T2202 box 24 eligible tuition amount", kind: "money" },
    25: { label: "T2202 box 25 part-time months", kind: "money" },
  },
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

const yearKeys = ["2020", "2021", "2022", "2023", "2024", "2025"];

const choiceControlOptions = {
  "taxpayer.marital_status": [["single", "Single"], ["married", "Married"], ["common_law", "Common-law"], ["separated", "Separated"], ["divorced", "Divorced"], ["widowed", "Widowed"]],
  "drug_insurance.group_plan_source": [["self", "My plan"], ["parent", "Parent's plan"]],
  "refundable_credits.solidarity_occupancy": [["tenant", "Tenant"], ["owner", "Owner"], ["neither", "Neither"]],
};

const numberControlPaths = new Set([
  "tax_year",
  "taxpayer.age_dec31",
  "taxpayer.dependant_count",
  "refundable_credits.work_premium_supplement_months",
  "refundable_credits.solidarity_owners_in_dwelling",
]);

const monthControlPaths = new Set([
  "drug_insurance.group_plan_months",
  "drug_insurance.eligible_student_months",
]);

const moneyControlPaths = new Set([
  "federal_tuition.t2202_eligible_fees",
  "federal_tuition.prior_unused_amount",
  "federal_tuition.canada_training_credit_limit",
  "federal_tuition.canada_training_credit_claim",
  "federal_tuition.transfer_amount",
  "quebec_tuition.eligible_tuition_or_exam_receipts",
  "quebec_tuition.prior_unused_at_8_percent",
  "quebec_tuition.prior_unused_at_20_percent",
  "quebec_tuition.transfer_amount",
  "rrsp.contribution_receipts",
  "rrsp.march_to_december_contributions",
  "rrsp.first_60_days_contributions",
  "rrsp.prior_unused_contributions",
  "rrsp.deduction_limit",
  "rrsp.deduction_requested",
  "instalments.federal_paid",
  "instalments.quebec_paid",
  "student_loan_interest.federal_current_year_paid",
  "student_loan_interest.federal_unused_2020",
  "student_loan_interest.federal_unused_2021",
  "student_loan_interest.federal_unused_2022",
  "student_loan_interest.federal_unused_2023",
  "student_loan_interest.federal_unused_2024",
  "student_loan_interest.federal_claim_amount",
  "student_loan_interest.quebec_prior_unused",
  "student_loan_interest.quebec_current_year_paid",
  "student_loan_interest.quebec_claim_amount",
  "pandemic_repayment.eligible_repayment_amount",
  "pandemic_repayment.quebec_claim_amount",
  "refundable_credits.rl19_box_a",
  "refundable_credits.rl19_box_b",
  "refundable_credits.advanced_cwb_paid",
  "refundable_credits.advanced_cwb_disability_paid",
]);

const booleanControlPaths = new Set([
  "taxpayer.full_year_canada_resident",
  "taxpayer.full_year_quebec_resident",
  "taxpayer.deceased_return",
  "taxpayer.bankruptcy_return",
  "taxpayer.has_self_employment",
  "taxpayer.has_capital_gains",
  "taxpayer.has_rental_income",
  "taxpayer.has_foreign_income_or_tax",
  "taxpayer.has_foreign_property_over_100k",
  "taxpayer.has_crypto_transactions",
  "taxpayer.has_pension_or_benefit_income",
  "taxpayer.has_indian_act_exempt_income",
  "taxpayer.has_disability_or_caregiver_claim",
  "taxpayer.has_employment_expenses",
  "taxpayer.has_medical_expenses",
  "taxpayer.has_donations",
  "taxpayer.has_childcare_expenses",
  "taxpayer.has_moving_expenses",
  "taxpayer.has_tips_or_other_employment_income",
  "taxpayer.has_student_loan_interest",
  "taxpayer.received_qpp_disability_pension",
  "taxpayer.made_qpp_cpt30_election",
  "taxpayer.was_full_time_student_more_than_13_weeks",
  "inventory.income_sources_reviewed",
  "inventory.deductions_reviewed",
  "inventory.credits_reviewed",
  "inventory.cra_records_reviewed",
  "inventory.revenu_quebec_records_reviewed",
  "inventory.no_income_sources",
  "federal_tuition.has_current_tuition",
  "federal_tuition.has_prior_unused",
  "federal_tuition.wants_transfer",
  "federal_tuition.wants_canada_training_credit",
  "quebec_tuition.has_current_tuition",
  "quebec_tuition.institution_outside_quebec",
  "quebec_tuition.has_prior_unused",
  "quebec_tuition.wants_transfer",
  "rrsp.has_contributions",
  "rrsp.has_prior_unused_contributions",
  "rrsp.has_hbp_or_llp_activity",
  "instalments.federal_reviewed",
  "instalments.quebec_reviewed",
  "quebec_schedule_b.living_alone_reviewed",
  "quebec_schedule_b.eligible_for_living_alone_amount",
  "student_loan_interest.reviewed",
  "student_loan_interest.qualifying_government_loans_confirmed",
  "scholarships.reviewed",
  "resp_eap.reviewed",
  "resp_eap.has_other_resp_payments",
  "resp_eap.qesi_cumulative_amount_over_3600",
  "pandemic_repayment.reviewed",
  "additional_return_screens.immigrated_or_emigrated_2025",
  "additional_return_screens.immigrated_or_emigrated_in_tax_year",
  "additional_return_screens.quebec_trust_return",
  "additional_return_screens.separate_post_death_return",
  "additional_return_screens.quebec_enterprise_registration_or_annual_fee",
  "drug_insurance.reviewed",
  "drug_insurance.other_exemption_applies",
  "refundable_credits.work_premium_answers_reviewed",
  "refundable_credits.solidarity_answers_reviewed",
  "refundable_credits.canada_workers_benefit_answers_reviewed",
  "refundable_credits.rl19_advance_payments_reviewed",
  "refundable_credits.rl19_has_other_advance_boxes",
  "refundable_credits.cwb_incarcerated_90_days",
  "refundable_credits.cwb_foreign_officer_exempt",
  "refundable_credits.work_premium_eligible_status",
  "refundable_credits.quebec_work_premium_full_time_student",
  "refundable_credits.transferred_schedule_s_amount",
  "refundable_credits.family_allowance_received_for_self",
  "refundable_credits.turned_18_before_december",
  "refundable_credits.designated_as_dependent_child",
  "refundable_credits.incarcerated_over_183_days",
  "refundable_credits.adapted_work_premium_eligible",
  "refundable_credits.request_tax_shield",
  "refundable_credits.wants_solidarity_credit",
  "refundable_credits.solidarity_eligible_immigration_status",
  "refundable_credits.solidarity_refugee_claimant_dec31",
  "refundable_credits.solidarity_family_allowance_paid_for_user_december",
  "refundable_credits.solidarity_turned_18_in_december",
  "refundable_credits.solidarity_lived_alone_all_year",
  "refundable_credits.solidarity_address_same_as_return",
  "refundable_credits.solidarity_owner_has_municipal_tax_bill",
]);

const stableProfileFacts = [
  { path: "taxpayer.age_dec31", label: "Age on December 31", annualize: true },
  { path: "taxpayer.marital_status", label: "Marital status" },
  { path: "taxpayer.dependant_count", label: "Dependants" },
];

const state = {
  schema: null,
  input: null,
  mode: "single",
  workspace: null,
  selectedYear: "2025",
  activeYears: ["2025"],
  dirty: false,
  sampleLoaded: false,
  result: null,
  batchResult: null,
  responseSources: {},
  pdfUrls: [],
  batchFiles: [],
  batchPdfUrls: {},
  workspaceImportDocuments: {},
  pendingReviewActions: {
    corrections: [],
    decisions: [],
    carryforward_choices: [],
  },
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
  clearAnsweredMissingFact(root, path, value);
}

function hasAnswer(value) {
  return value !== null && value !== undefined && value !== "";
}

function clearAnsweredMissingFact(root, path, value) {
  if (root !== state.input || !state.workspace) return;
  if (!hasAnswer(value)) return;
  const yearState = selectedYearState();
  if (!yearState?.missing_facts?.length) return;
  yearState.missing_facts = yearState.missing_facts.filter((fact) => fact.path !== path);
}

function clearMissingFactsForPaths(yearState, paths) {
  if (!yearState?.missing_facts?.length) return;
  const answered = new Set(paths);
  yearState.missing_facts = yearState.missing_facts.filter((fact) => !answered.has(fact.path));
}

function controlSpecForPath(path) {
  if (!path) return null;
  if (path === "province_dec31" || path === "taxpayer.province_dec31") return { kind: "province" };
  if (choiceControlOptions[path]) return { kind: "choice", options: choiceControlOptions[path] };
  if (numberControlPaths.has(path)) return { kind: "number" };
  if (monthControlPaths.has(path)) return { kind: "months" };
  if (moneyControlPaths.has(path)) return { kind: "money" };
  if (booleanControlPaths.has(path)) return { kind: "boolean" };
  return null;
}

function markDirty() {
  state.dirty = true;
  state.inputRevision += 1;
  state.result = null;
  invalidateChangedYear();
  state.responseSources = {};
  $("#save-result").disabled = true;
  $("#print-packet").disabled = true;
  $("#calculation-state").textContent = "Inputs changed. Recalculate before exporting results.";
  $("#problems").replaceChildren();
  $("#results").replaceChildren();
  refreshActiveYears();
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
  Object.values(state.batchPdfUrls).forEach((url) => {
    if (url) URL.revokeObjectURL(url);
  });
  state.batchPdfUrls = {};
  state.batchFiles = [];
}

function setBanner(message) {
  const banner = $("#banner");
  banner.hidden = !message;
  banner.textContent = message || "";
}

function selectedYearState() {
  return state.workspace?.years?.[state.selectedYear] || null;
}

function setSelectedYear(yearKey) {
  state.selectedYear = String(yearKey);
  const yearState = selectedYearState();
  if (yearState) state.input = yearState.input;
}

function emptyReviewActions() {
  return { corrections: [], decisions: [], carryforward_choices: [] };
}

function pendingReviewCount(actions = state.pendingReviewActions) {
  return (
    (actions?.corrections?.length || 0) +
    (actions?.decisions?.length || 0) +
    (actions?.carryforward_choices?.length || 0)
  );
}

function normalizeReviewActions(actions) {
  return {
    corrections: Array.isArray(actions?.corrections) ? clone(actions.corrections) : [],
    decisions: Array.isArray(actions?.decisions) ? clone(actions.decisions) : [],
    carryforward_choices: Array.isArray(actions?.carryforward_choices) ? clone(actions.carryforward_choices) : [],
  };
}

function activeYearNumbers() {
  refreshActiveYears();
  return state.activeYears.map((year) => Number(year)).filter((year) => Number.isInteger(year));
}

function replaceByKey(items, next, keyFor) {
  const key = keyFor(next);
  const filtered = items.filter((item) => keyFor(item) !== key);
  filtered.push(next);
  return filtered;
}

function markReviewDirty(message = "Review changes are pending. Apply them or calculate to submit them.") {
  state.dirty = true;
  state.inputRevision += 1;
  state.result = null;
  state.batchResult = null;
  state.responseSources = {};
  $("#save-result").disabled = true;
  $("#print-packet").disabled = true;
  $("#calculation-state").textContent = message;
  $("#problems").replaceChildren();
  $("#results").replaceChildren();
}

function queueCorrection(candidateId, update) {
  if (!candidateId) return;
  const existing = state.pendingReviewActions.corrections.find((item) => item.candidate_id === candidateId) || {
    candidate_id: candidateId,
    reason: "Corrected extracted PDF candidate before calculation.",
  };
  const fields = update.fields ? { ...(existing.fields || {}), ...update.fields } : existing.fields;
  const metadata = update.metadata ? { ...(existing.metadata || {}), ...update.metadata } : existing.metadata;
  const next = { ...existing, ...update, fields, metadata };
  if (!next.fields) delete next.fields;
  if (!next.metadata) delete next.metadata;
  state.pendingReviewActions.corrections = replaceByKey(
    state.pendingReviewActions.corrections,
    next,
    (item) => item.candidate_id,
  );
  markReviewDirty();
}

function queueDecision(candidateId, action, selectedCandidateId) {
  if (!candidateId) return;
  const next = {
    candidate_id: candidateId,
    action,
    reason:
      action === "exclude"
        ? "Excluded after local PDF review."
        : action === "select_amendment"
          ? "Selected as the amendment candidate after local PDF review."
          : "Accepted after local PDF review.",
  };
  if (selectedCandidateId) next.selected_candidate_id = selectedCandidateId;
  state.pendingReviewActions.decisions = replaceByKey(
    state.pendingReviewActions.decisions,
    next,
    (item) => item.candidate_id,
  );
  markReviewDirty();
  renderPendingReviewSummary();
}

function queueCarryforwardChoice(taxYear, key, selection) {
  if (!taxYear || !key || !selection) return;
  const next = {
    tax_year: Number(taxYear),
    key,
    selection,
    reason:
      selection === "assessed"
        ? "Used the assessed opening balance supplied for this tax year."
        : "Used the preceding year's proposed closing balance.",
  };
  state.pendingReviewActions.carryforward_choices = replaceByKey(
    state.pendingReviewActions.carryforward_choices,
    next,
    (item) => `${item.tax_year}:${item.key}`,
  );
  markReviewDirty("Carryforward choice is pending. Apply it or calculate to submit it.");
  renderAll();
}

function reviewRequestPayload() {
  return {
    workspace: activeWorkspaceForCalculation(),
    active_years: activeYearNumbers(),
    corrections: clone(state.pendingReviewActions.corrections),
    decisions: clone(state.pendingReviewActions.decisions),
    carryforward_choices: clone(state.pendingReviewActions.carryforward_choices),
  };
}

function replaceWorkspaceFromBackend(workspace) {
  const preferredYear = state.selectedYear;
  state.workspace = clone(workspace);
  refreshActiveYears();
  if (!state.workspace.years?.[preferredYear]) {
    setSelectedYear(state.activeYears[0] || "2025");
  } else {
    setSelectedYear(preferredYear);
  }
}

function workspaceYearHasWork(yearState) {
  return Boolean(
    yearState?.input?.slips?.length ||
      yearState?.unresolved_candidates?.length ||
      yearState?.duplicate_candidates?.length ||
      yearState?.missing_facts?.some((fact) => fact.code !== "missing_imported_slips") ||
      yearState?.input?.inventory?.no_income_sources === true,
  );
}

function refreshActiveYears() {
  if (!state.workspace) {
    state.activeYears = [String(state.input?.tax_year || state.selectedYear || "2025")];
    return;
  }
  const active = yearKeys.filter((year) => workspaceYearHasWork(state.workspace.years[year]));
  state.activeYears = active.sort();
  state.workspace.active_years = state.activeYears.map((year) => Number(year));
}

function activateBatchWorkspace(workspace, preferredYear = "2025") {
  state.mode = "batch";
  state.workspace = clone(workspace);
  state.workspace.active_years = Array.isArray(state.workspace.active_years) ? state.workspace.active_years : [];
  state.pendingReviewActions = emptyReviewActions();
  const activePreferred = workspaceYearHasWork(state.workspace.years?.[preferredYear]);
  setSelectedYear(activePreferred ? preferredYear : yearKeys.find((year) => workspaceYearHasWork(state.workspace.years[year])) || preferredYear);
  refreshActiveYears();
  state.result = null;
  state.batchResult = null;
  state.responseSources = {};
  state.dirty = true;
  bumpInputRevision();
}

function activateSingleInput(input) {
  state.mode = "single";
  state.workspace = null;
  state.selectedYear = String(input.tax_year || "2025");
  state.activeYears = [state.selectedYear];
  state.input = clone(input);
  state.result = null;
  state.batchResult = null;
  state.responseSources = {};
  state.pendingReviewActions = emptyReviewActions();
  state.dirty = true;
  bumpInputRevision();
}

function invalidateChangedYear(yearKey = state.selectedYear) {
  if (!state.batchResult?.results) return;
  for (const activeYear of state.activeYears) {
    if (Number(activeYear) >= Number(yearKey)) delete state.batchResult.results[activeYear];
  }
}

function profileFactForPath(path) {
  return stableProfileFacts.find((fact) => fact.path === path) || null;
}

function adjustedProfileValue(fact, value, sourceYear, targetYear) {
  if (!fact?.annualize) return value;
  const age = Number(value);
  if (!Number.isFinite(age)) return undefined;
  return age + (Number(targetYear) - Number(sourceYear));
}

function changedValue(previous, next) {
  return JSON.stringify(previous) !== JSON.stringify(next);
}

function applySelectedProfileFactsToActiveYears(paths, options = {}) {
  if (!state.workspace) return [];
  const selectedPaths = Array.from(new Set(paths || [])).filter((path) => profileFactForPath(path));
  if (!selectedPaths.length) return [];
  const sourceYear = Number(state.selectedYear);
  const changedYears = new Set();
  for (const targetYear of state.activeYears) {
    if (targetYear === state.selectedYear) continue;
    const yearState = state.workspace.years?.[targetYear];
    if (!yearState?.input) continue;
    const changedPaths = [];
    for (const path of selectedPaths) {
      const fact = profileFactForPath(path);
      const sourceValue = getPath(state.input, path);
      if (!hasAnswer(sourceValue)) continue;
      const targetValue = getPath(yearState.input, path);
      if (hasAnswer(targetValue) && !options.overwrite) continue;
      const nextValue = adjustedProfileValue(fact, sourceValue, sourceYear, Number(targetYear));
      if (nextValue === undefined || !changedValue(targetValue, nextValue)) continue;
      setPath(yearState.input, path, nextValue);
      changedPaths.push(path);
    }
    if (changedPaths.length) {
      clearMissingFactsForPaths(yearState, changedPaths);
      changedYears.add(targetYear);
    }
  }
  if (!changedYears.size) return [];
  const earliestChangedYear = Math.min(...Array.from(changedYears).map(Number));
  state.dirty = true;
  state.inputRevision += 1;
  state.result = null;
  state.responseSources = {};
  invalidateChangedYear(String(earliestChangedYear));
  $("#save-result").disabled = true;
  $("#print-packet").disabled = true;
  $("#calculation-state").textContent = "Profile facts copied to active years. Recalculate before exporting results.";
  $("#problems").replaceChildren();
  $("#results").replaceChildren();
  setSelectedYear(state.selectedYear);
  refreshActiveYears();
  return Array.from(changedYears).sort();
}

function profilePreviewValue(path, targetYear) {
  const fact = profileFactForPath(path);
  const value = getPath(state.input, path);
  const adjusted = adjustedProfileValue(fact, value, Number(state.selectedYear), Number(targetYear));
  if (adjusted === undefined || adjusted === null || adjusted === "") return "unknown";
  if (path === "taxpayer.marital_status") return String(adjusted).replace("_", "-");
  return String(adjusted);
}

function renderProfileReuse() {
  const container = $("#profile-reuse");
  if (!container) return;
  container.replaceChildren();
  if (!state.workspace || state.activeYears.length < 2) return;
  const available = stableProfileFacts.filter((fact) => hasAnswer(getPath(state.input, fact.path)));
  if (!available.length) return;
  const card = node("article", "review-card");
  card.append(node("h3", null, "Apply selected profile facts to other active years"));
  card.append(
    node(
      "p",
      "muted",
      "Only the checked identity facts are copied. Residence, student status, income, credits, and drug-insurance months stay year-specific.",
    ),
  );
  const choices = node("div", "copy-list");
  available.forEach((fact) => {
    const line = node("label", "checkbox-line");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = true;
    input.dataset.profilePath = fact.path;
    line.append(input, node("span", null, fact.annualize ? `${fact.label} (adjust by tax year)` : fact.label));
    choices.append(line);
  });
  card.append(choices);

  const overwrite = document.createElement("input");
  overwrite.type = "checkbox";
  const overwriteLine = node("label", "checkbox-line");
  overwriteLine.append(overwrite, node("span", null, "Overwrite existing answers in destination years"));
  card.append(overwriteLine);

  const preview = node("div", "copy-list");
  const refreshPreview = () => {
    preview.replaceChildren();
    state.activeYears
      .filter((year) => year !== state.selectedYear)
      .forEach((year) => {
        const row = node("div", "copy-row");
        row.append(node("strong", null, year));
        available.forEach((fact) => {
          const existing = getPath(state.workspace.years?.[year]?.input, fact.path);
          const keep = hasAnswer(existing) && !overwrite.checked;
          const suffix = keep ? `keeps existing ${existing}` : `would use ${profilePreviewValue(fact.path, year)}`;
          row.append(node("span", "hint", `${fact.label}: ${suffix}`));
        });
        preview.append(row);
      });
  };
  overwrite.addEventListener("change", refreshPreview);
  refreshPreview();
  card.append(preview);

  const apply = node("button", "secondary", "Apply selected profile facts to other active years");
  apply.type = "button";
  apply.addEventListener("click", () => {
    const selected = Array.from(choices.children)
      .map((line) => line.children[0])
      .filter((input) => input.checked)
      .map((input) => input.dataset.profilePath);
    const changed = applySelectedProfileFactsToActiveYears(selected, { overwrite: overwrite.checked });
    setBanner(changed.length ? `Applied selected profile facts to ${changed.join(", ")}.` : "No destination year needed a copied profile fact.");
    renderAll();
  });
  card.append(apply);
  container.append(card);
}

function acceptedSlipCount(yearState) {
  return yearState?.input?.slips?.length || 0;
}

function unresolvedCount(yearState) {
  return (yearState?.unresolved_candidates?.length || 0) + (yearState?.duplicate_candidates?.length || 0);
}

function missingFactsForYear(yearState) {
  return (yearState?.missing_facts || []).filter((fact) => fact.code !== "missing_imported_slips");
}

function formatMoneyAmount(raw) {
  if (raw === null || raw === undefined || raw === "") return "not calculated";
  const amount = Number(raw);
  if (!Number.isFinite(amount)) return String(raw);
  return amount.toLocaleString("en-CA", { style: "currency", currency: "CAD" });
}

function candidateFields(candidate) {
  return candidate?.candidate?.fields || candidate?.fields || {};
}

function candidateMetadata(candidate) {
  return candidate?.candidate?.metadata || candidate?.metadata || {};
}

function candidateSlipType(candidate) {
  return candidate?.slip_type || candidate?.candidate?.slip_type || "";
}

function sourceCandidate(candidateId) {
  return candidateId ? state.workspace?.source_candidates?.[candidateId] || null : null;
}

function sourceCandidateIdForSlip(slip) {
  if (!slip?.document_id) return null;
  const documentId = String(slip.document_id);
  if (sourceCandidate(documentId)) return documentId;
  return null;
}

function isImportedSlip(slip) {
  return Boolean(sourceCandidateIdForSlip(slip));
}

function slipForCandidateToken(token) {
  const slips = state.input?.slips || [];
  if (/^\d+$/.test(String(token))) return slips[Number(token)] || null;
  return slips.find((slip) => sourceCandidateIdForSlip(slip) === token || slip.document_id === token) || null;
}

function slipCorrectionTargetForPath(path) {
  const fieldMatch = String(path || "").match(/^slips\.([^.]+)\.fields\.([^.]+)$/);
  if (fieldMatch) {
    const slip = slipForCandidateToken(fieldMatch[1]);
    const candidateId = sourceCandidateIdForSlip(slip);
    const slipType = slip?.slip_type || candidateSlipType(sourceCandidate(candidateId));
    if (!candidateId || !candidateFieldSpecs[slipType]?.[fieldMatch[2]]) return null;
    return { slip, candidateId, group: "fields", key: fieldMatch[2], spec: candidateFieldSpecs[slipType][fieldMatch[2]] };
  }
  const metadataMatch = String(path || "").match(/^slips\.([^.]+)\.([^.]+)$/);
  if (metadataMatch) {
    const slip = slipForCandidateToken(metadataMatch[1]);
    const candidateId = sourceCandidateIdForSlip(slip);
    const slipType = slip?.slip_type || candidateSlipType(sourceCandidate(candidateId));
    if (!candidateId || !candidateMetadataSpecs[slipType]?.[metadataMatch[2]]) return null;
    return { slip, candidateId, group: "metadata", key: metadataMatch[2], spec: candidateMetadataSpecs[slipType][metadataMatch[2]] };
  }
  return null;
}

function fieldFromSlipValue(value) {
  return { value: value ?? "" };
}

function fieldForCorrection(value) {
  if (value && typeof value === "object" && ("value" in value || "accepted_value" in value)) return value;
  return fieldFromSlipValue(value);
}

function candidatePdfUrl(candidate) {
  const documentId = candidate?.document_id || candidate?.candidate?.document_id;
  const filename = state.workspaceImportDocuments?.[documentId]?.filename;
  return state.batchPdfUrls[documentId] || (filename ? state.batchPdfUrls[filename] : null);
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

function renderBatchStatus() {
  const container = $("#batch-status");
  if (!container) return;
  container.replaceChildren();
  if (!state.batchFiles.length) {
    container.append(node("p", "muted", "No PDFs selected yet."));
    return;
  }
  const table = node("table", "field-table compact-table");
  const thead = document.createElement("thead");
  const head = document.createElement("tr");
  ["File", "Status", "Source"].forEach((heading) => head.append(node("th", null, heading)));
  thead.append(head);
  const tbody = document.createElement("tbody");
  state.batchFiles.forEach((item) => {
    const row = document.createElement("tr");
    row.append(node("td", null, item.name), node("td", null, item.status));
    const source = document.createElement("td");
    const url = state.batchPdfUrls[item.name] || (item.document_id ? state.batchPdfUrls[item.document_id] : null);
    if (url) {
      const link = document.createElement("a");
      link.href = url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = "Preview retained for this session";
      source.append(link);
    } else {
      source.append(node("span", "muted", "PDF not available in restored JSON"));
    }
    row.append(source);
    tbody.append(row);
  });
  table.append(thead, tbody);
  container.append(table);
}

function renderYearOverview() {
  const container = $("#year-overview");
  if (!container) return;
  container.replaceChildren();
  if (!state.workspace) {
    container.append(node("p", "muted", "Import PDFs or restore a batch workspace to review 2020-2025 together."));
    return;
  }
  refreshActiveYears();
  for (const year of yearKeys) {
    const yearState = state.workspace.years[year];
    const active = state.activeYears.includes(year);
    const card = node("button", `year-card${year === state.selectedYear ? " selected" : ""}${active ? "" : " inactive"}`);
    card.type = "button";
    card.dataset.year = year;
    const problems = unresolvedCount(yearState) + missingFactsForYear(yearState).length;
    const result = state.batchResult?.results?.[year];
    card.append(node("strong", null, year));
    card.append(node("span", null, `${acceptedSlipCount(yearState)} accepted slip${acceptedSlipCount(yearState) === 1 ? "" : "s"}`));
    if (yearState.input?.inventory?.no_income_sources === true) card.append(node("span", "pill", "No income confirmed"));
    if (problems) card.append(node("span", "pill warn-pill", `${problems} review item${problems === 1 ? "" : "s"}`));
    else if (yearState.ready_to_calculate) card.append(node("span", "pill ok-pill", "Ready"));
    else if (!active) card.append(node("span", "muted", "Inactive"));
    else card.append(node("span", "muted", "Needs facts"));
    if (result?.status === "complete") {
      card.append(node("span", "year-money", `Federal ${formatMoneyAmount(result.federal_refund_or_balance)}`));
      card.append(node("span", "year-money", `Quebec ${formatMoneyAmount(result.quebec_refund_or_balance)}`));
    } else if (result?.status === "blocked") {
      card.append(node("span", "muted", result.reason || "Blocked"));
    }
    card.addEventListener("click", () => {
      setSelectedYear(year);
      renderAll();
    });
    container.append(card);
  }
  const status = $("#year-state");
  if (status) status.textContent = `Selected ${state.selectedYear}. Active years: ${state.activeYears.join(", ") || "none"}.`;
}

function renderCandidateReview() {
  const container = $("#candidate-review");
  if (!container) return;
  container.replaceChildren();
  if (!state.workspace) return;
  const globalItems = [
    ...state.workspace.unassigned_candidates.map((item) => ({ ...item, scope: "Unassigned" })),
    ...state.workspace.duplicate_candidates.map((item) => ({ ...item, scope: "Duplicate" })),
  ];
  const yearState = selectedYearState();
  const yearItems = [
    ...(yearState?.unresolved_candidates || []).map((item) => ({ ...item, scope: state.selectedYear })),
    ...(yearState?.duplicate_candidates || []).map((item) => ({ ...item, scope: `${state.selectedYear} duplicate` })),
  ];
  const items = [...globalItems, ...yearItems];
  const section = node("section", "result-block");
  section.append(node("h3", null, "Targeted slip review"));
  section.append(pendingReviewSummary());
  if (!items.length) {
    section.append(node("p", "muted", "No ambiguous, unsupported, duplicate, or unassigned slip candidates need review."));
    container.append(section);
    return;
  }
  items.forEach((item) => section.append(candidateCard(item)));
  container.append(section);
}

function pendingReviewSummary() {
  const wrap = node("div", "review-action-bar");
  const count = pendingReviewCount();
  const accepted = (state.workspace?.decisions?.length || 0) + (state.workspace?.corrections?.length || 0);
  wrap.append(node("span", "muted", `${count} pending review action${count === 1 ? "" : "s"}. ${accepted} accepted review record${accepted === 1 ? "" : "s"} already in the workspace.`));
  const apply = node("button", count ? "secondary" : "ghost", "Apply review changes");
  apply.type = "button";
  apply.disabled = count === 0;
  apply.addEventListener("click", () => applyReviewActions());
  wrap.append(apply);
  return wrap;
}

function renderPendingReviewSummary() {
  renderCandidateReview();
}

function extractedDisplayValue(field) {
  const value = field?.accepted_value ?? field?.value ?? "";
  return typeof value === "boolean" ? (value ? "Yes" : "No") : String(value);
}

function correctionControl(candidateId, group, key, field, spec) {
  const current = field?.accepted_value ?? field?.value ?? "";
  if (spec?.kind === "boolean" || typeof current === "boolean") {
    const select = document.createElement("select");
    select.append(new Option("", ""));
    select.append(new Option("Yes", "true"));
    select.append(new Option("No", "false"));
    select.value = current ? "true" : "false";
    select.dataset.candidateId = candidateId;
    select.dataset.correctionGroup = group;
    select.dataset.correctionKey = key;
    select.addEventListener("change", () => {
      if (select.value === "") return;
      queueCorrection(candidateId, { [group]: { [key]: select.value === "true" } });
    });
    return select;
  }
  const input = document.createElement("input");
  input.inputMode = group === "fields" ? "decimal" : "text";
  input.value = current == null ? "" : String(current);
  input.dataset.candidateId = candidateId;
  input.dataset.correctionGroup = group;
  input.dataset.correctionKey = key;
  input.addEventListener("input", () => {
    const value = input.value.trim();
    if (value !== "") queueCorrection(candidateId, { [group]: { [key]: value } });
  });
  return input;
}

function candidateCorrectionRow(candidateId, group, key, field, spec) {
  const label = spec?.label || key;
  return fieldWrap(label, correctionControl(candidateId, group, key, field, spec), "Applies as a source correction when review changes are applied.");
}

function appendSupportedCandidateCorrections(container, itemOrSlip, candidateId) {
  const slipType = itemOrSlip?.slip_type || candidateSlipType(itemOrSlip) || candidateSlipType(sourceCandidate(candidateId));
  const controls = [];
  const fields = itemOrSlip?.fields || candidateFields(itemOrSlip) || {};
  const metadata = itemOrSlip?.metadata || candidateMetadata(itemOrSlip) || {};
  Object.entries(candidateFieldSpecs[slipType] || {}).forEach(([key, spec]) => {
    controls.push(candidateCorrectionRow(candidateId, "fields", key, fieldForCorrection(fields[key]), spec));
  });
  Object.entries(candidateMetadataSpecs[slipType] || {}).forEach(([key, spec]) => {
    controls.push(candidateCorrectionRow(candidateId, "metadata", key, fieldForCorrection(metadata[key] ?? itemOrSlip?.[key]), spec));
  });
  if (!controls.length) return;
  container.append(node("h4", null, "Supported source corrections"));
  const grid = node("div", "grid-form tight-grid");
  controls.forEach((control) => grid.append(control));
  container.append(grid);
}

function appendExtractedTable(card, title, items, candidateId, group, slipType) {
  const entries = Object.entries(items || {});
  if (!entries.length) return;
  if (title) card.append(node("h4", null, title));
  const table = node("table", "field-table compact-table");
  const thead = document.createElement("thead");
  const head = document.createElement("tr");
  ["Key", "Accepted value", "Confidence", "Source text", "Correction"].forEach((heading) => head.append(node("th", null, heading)));
  thead.append(head);
  const tbody = document.createElement("tbody");
  entries.forEach(([key, field]) => {
    const row = document.createElement("tr");
    const correctionCell = document.createElement("td");
    const spec = group === "metadata" ? candidateMetadataSpecs[slipType]?.[key] : candidateFieldSpecs[slipType]?.[key];
    correctionCell.append(correctionControl(candidateId, group, key, field, spec));
    row.append(
      node("td", null, key),
      node("td", null, extractedDisplayValue(field)),
      node("td", null, field.confidence == null ? "" : `${Math.round(Number(field.confidence) * 100)}%`),
      node("td", null, field.raw_text || ""),
      correctionCell,
    );
    tbody.append(row);
  });
  table.append(thead, tbody);
  card.append(table);
}

function candidateCard(item) {
  const card = node("article", "review-card");
  const title = node("div", "slip-title");
  title.append(node("h4", null, `${item.scope}: ${item.slip_type || "Unknown slip"} ${item.candidate_id || ""}`));
  title.append(node("span", "pill warn-pill", item.reason || item.decision || "review"));
  card.append(title);
  const fields = node("div", "grid-form tight-grid");
  fields.append(
    readonlyField("Year", item.tax_year ?? "Unknown"),
    readonlyField("Issuer", item.issuer_id || "Unknown"),
    readonlyField("Decision", item.decision || ""),
    readonlyField("Review reasons", (item.review_reasons || []).join(", ") || "None supplied"),
  );
  card.append(fields);
  const slipType = candidateSlipType(item);
  appendExtractedTable(card, null, candidateFields(item), item.candidate_id, "fields", slipType);
  appendExtractedTable(card, "Source facts", candidateMetadata(item), item.candidate_id, "metadata", slipType);
  card.append(candidateReviewControls(item));
  const url = candidatePdfUrl(item);
  if (url) {
    const frame = document.createElement("iframe");
    frame.className = "pdf-preview short-preview";
    frame.title = `Source PDF preview for ${item.candidate_id || "candidate"}`;
    frame.src = url;
    card.append(frame);
  } else {
    card.append(node("p", "muted", "Source PDF preview is unavailable after restoring JSON unless the PDF is selected again in this browser session."));
  }
  return card;
}

function candidateReviewControls(item) {
  const controls = node("div", "review-controls");
  const correctionGrid = node("div", "grid-form tight-grid");
  const typeSelect = document.createElement("select");
  const typeOptions = Array.from(new Set([item.slip_type, ...(state.schema?.supported_slips || []), "RL8"].filter(Boolean)));
  typeOptions.forEach((value) => typeSelect.append(new Option(value, value)));
  typeSelect.value = item.slip_type || typeOptions[0] || "";
  typeSelect.addEventListener("change", () => queueCorrection(item.candidate_id, { slip_type: typeSelect.value }));

  const yearSelect = document.createElement("select");
  yearKeys.forEach((year) => yearSelect.append(new Option(year, year)));
  yearSelect.value = item.tax_year ? String(item.tax_year) : state.selectedYear;
  yearSelect.addEventListener("change", () => queueCorrection(item.candidate_id, { tax_year: Number(yearSelect.value) }));

  const issuer = document.createElement("input");
  issuer.value = item.issuer_id || "";
  issuer.placeholder = "Issuer name from the slip";
  issuer.addEventListener("input", () => {
    const value = issuer.value.trim();
    if (value) queueCorrection(item.candidate_id, { issuer_id: value });
  });

  correctionGrid.append(
    fieldWrap("Slip type", typeSelect),
    fieldWrap("Tax year", yearSelect),
    fieldWrap("Issuer", issuer, "Leave unknown blank until the source identifies it."),
  );
  controls.append(correctionGrid);
  appendSupportedCandidateCorrections(controls, item, item.candidate_id);

  const buttons = node("div", "toolbar");
  const accept = node("button", "secondary", "Accept candidate");
  accept.type = "button";
  accept.addEventListener("click", () => queueDecision(item.candidate_id, "accept"));
  const exclude = node("button", "ghost", "Exclude candidate");
  exclude.type = "button";
  exclude.addEventListener("click", () => queueDecision(item.candidate_id, "exclude"));
  buttons.append(accept, exclude);
  if (item.decision === "duplicate" || String(item.scope || "").toLowerCase().includes("duplicate")) {
    const selectAmendment = node("button", "secondary", "Select as amendment");
    selectAmendment.type = "button";
    selectAmendment.addEventListener("click", () => queueDecision(item.candidate_id, "select_amendment", item.candidate_id));
    buttons.append(selectAmendment);
  }
  controls.append(buttons);
  return controls;
}

function readonlyField(label, value) {
  const wrap = node("div", "field");
  wrap.append(node("span", "label", label), node("span", null, String(value)));
  return wrap;
}

function renderEvidenceReview() {
  const container = $("#evidence-review");
  if (!container) return;
  container.replaceChildren();
  const yearState = selectedYearState();
  if (!yearState) return;
  const evidence = yearState.evidence || {};
  const section = node("section", "result-block");
  section.append(node("h3", null, `Accepted source evidence for ${state.selectedYear}`));
  if (!Object.keys(evidence).length) {
    section.append(node("p", "muted", "No accepted source evidence for this year yet."));
    container.append(section);
    return;
  }
  Object.entries(evidence).forEach(([slipId, item]) => {
    const details = document.createElement("details");
    details.className = "evidence-detail";
    const summary = document.createElement("summary");
    summary.textContent = `${item.slip_type || "Slip"} ${slipId} from ${item.issuer_id || "unknown issuer"}`;
    details.append(summary);
    const table = node("table", "field-table compact-table");
    const thead = document.createElement("thead");
    const head = document.createElement("tr");
    ["Key", "Original value", "Accepted value", "Source location", "Source text", "Correction"].forEach((heading) => head.append(node("th", null, heading)));
    thead.append(head);
    const tbody = document.createElement("tbody");
    const rows = [
      ...Object.entries(item.fields || {}).map(([key, field]) => [key, field, "fields"]),
      ...Object.entries(item.metadata || {}).map(([key, field]) => [key, field, "metadata"]),
    ];
    rows.forEach(([key, field, group]) => {
      const row = document.createElement("tr");
      const correctionCell = document.createElement("td");
      correctionCell.append(correctionControl(item.candidate_id, group, key, field));
      row.append(
        node("td", null, key),
        node("td", null, field.value == null ? "" : extractedDisplayValue({ value: field.value })),
        node("td", null, extractedDisplayValue(field)),
        node("td", null, field.page ? `Page ${field.page}${field.bbox ? `, region ${field.bbox.join(", ")}` : ""}` : "Location unavailable"),
        node("td", null, field.raw_text || ""),
        correctionCell,
      );
      tbody.append(row);
    });
    table.append(thead, tbody);
    details.append(table);
    const url = state.batchPdfUrls[item.document_id];
    if (url) {
      const link = document.createElement("a");
      link.href = url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = "Open retained source PDF";
      details.append(link);
    }
    section.append(details);
  });
  container.append(section);
}

function renderMissingFacts() {
  const container = $("#missing-facts");
  if (!container) return;
  container.replaceChildren();
  if (!state.workspace) {
    container.append(node("p", "muted", "The full review form below is for the current 2025 input."));
    return;
  }
  const facts = missingFactsForYear(selectedYearState());
  const section = node("section", "result-block");
  section.append(node("h3", null, `Questions for ${state.selectedYear}`));
  if (!facts.length) {
    section.append(node("p", "muted", "No targeted questions are currently blocking this year. The advanced fields remain available below."));
    appendCarryforwardConflictChoices(section, selectedYearState());
    container.append(section);
    return;
  }
  groupMissingFacts(facts).forEach((group) => section.append(renderMissingFactGroup(group)));
  appendCarryforwardConflictChoices(section, selectedYearState());
  container.append(section);
}

function groupMissingFacts(facts) {
  const groups = new Map();
  facts.forEach((fact) => {
    const key = missingFactGroupKey(fact.path || "");
    if (!groups.has(key)) groups.set(key, { key, facts: [] });
    groups.get(key).facts.push(fact);
  });
  return Array.from(groups.values());
}

function missingFactGroupKey(path) {
  if (path.startsWith("taxpayer") || path === "province_dec31") return "person";
  if (path.includes("tuition") || path.includes("scholarships") || path.includes("student_loan")) return "student";
  if (path.includes("drug_insurance")) return "insurance";
  if (path.includes("rrsp") || path.includes("carry") || path.includes("prior_unused")) return "prior";
  if (path.includes("inventory") || path === "slips") return "records";
  return "credits";
}

function renderMissingFactGroup(group) {
  const labels = {
    person: "Person and residency",
    student: "Student, tuition, awards, and loans",
    insurance: "Quebec drug insurance",
    prior: "Prior balances and RRSP limits",
    records: "Income records",
    credits: "Credits and Quebec schedules",
  };
  const card = node("article", "review-card");
  card.append(node("h4", null, labels[group.key] || "Review"));
  const unique = Array.from(new Map(group.facts.map((fact) => [fact.path, fact])).values());
  appendGroupQuickActions(card, unique);
  unique.forEach((fact) => {
    const control = controlForMissingFact(fact);
    if (control) card.append(control);
    else card.append(node("p", "muted", `${fact.label} (${fact.path})`));
  });
  return card;
}

function appendGroupQuickActions(card, facts) {
  const paths = new Set(facts.map((fact) => fact.path));
  const codes = new Set(facts.map((fact) => fact.code));
  if (facts.some((fact) => unsupportedFields.includes(String(fact.path || "").replace("taxpayer.", "")))) {
    const button = node("button", "secondary", "I reviewed the unsupported situations listed here and none apply");
    button.type = "button";
    button.addEventListener("click", () => {
      const answered = [];
      unsupportedFields.forEach((field) => {
        const path = `taxpayer.${field}`;
        if (paths.has(path)) {
          state.input.taxpayer[field] = false;
          answered.push(path);
        }
      });
      clearMissingFactsForPaths(selectedYearState(), answered);
      markDirty();
      renderAll();
    });
    card.append(button);
  }
  if (facts.some((fact) => additionalReturnScreenFields.includes(String(fact.path || "").replace("additional_return_screens.", "")))) {
    const button = node("button", "secondary", "I reviewed these additional filing screens and none apply");
    button.type = "button";
    button.addEventListener("click", () => {
      const answered = [];
      additionalReturnScreenFields.forEach((field) => {
        const path = `additional_return_screens.${field}`;
        if (paths.has(path)) {
          state.input.additional_return_screens[field] = false;
          answered.push(path);
        }
      });
      clearMissingFactsForPaths(selectedYearState(), answered);
      markDirty();
      renderAll();
    });
    card.append(button);
  }
  if (paths.has("taxpayer.has_student_loan_interest") || codes.has("missing_student_loan_interest_answers")) {
    const currentOnly = node("button", "secondary", "No current-year qualifying student-loan interest paid");
    currentOnly.type = "button";
    currentOnly.addEventListener("click", () => applyNoCurrentStudentLoanInterest());
    card.append(currentOnly);

    const noneAtAll = node("button", "secondary", "No current-year or prior unused qualifying student-loan interest");
    noneAtAll.type = "button";
    noneAtAll.addEventListener("click", () => applyNoStudentLoanInterestAtAll());
    card.append(noneAtAll);
  }
}

function numericAmount(value) {
  if (value === null || value === undefined || value === "") return null;
  const amount = Number(value);
  return Number.isFinite(amount) ? amount : null;
}

function hasPositiveAmount(value) {
  const amount = numericAmount(value);
  return amount !== null && amount > 0;
}

function setZeroUnlessPositive(root, path) {
  const current = getPath(root, path);
  if (hasPositiveAmount(current)) return false;
  setPath(root, path, "0.00");
  return true;
}

function studentLoanOriginYears(taxYear) {
  const year = Number(taxYear || state.input?.tax_year || state.selectedYear);
  if (!Number.isInteger(year)) return [];
  return [year - 5, year - 4, year - 3, year - 2, year - 1];
}

function legacyStudentLoanOriginPaths(taxYear) {
  return studentLoanOriginYears(taxYear)
    .filter((year) => year >= 2020 && year <= 2024)
    .map((year) => `student_loan_interest.federal_unused_${year}`);
}

function setFederalUnusedOriginsToZeroUnlessPositive(answered) {
  const interest = state.input.student_loan_interest;
  if (interest.federal_unused_by_origin_year && typeof interest.federal_unused_by_origin_year === "object") {
    studentLoanOriginYears(state.input.tax_year).forEach((year) => {
      const key = String(year);
      if (hasPositiveAmount(interest.federal_unused_by_origin_year[key])) return;
      interest.federal_unused_by_origin_year[key] = "0.00";
    });
    answered.push("student_loan_interest.federal_unused_by_origin_year");
    return;
  }
  legacyStudentLoanOriginPaths(state.input.tax_year).forEach((path) => {
    if (setZeroUnlessPositive(state.input, path)) answered.push(path);
  });
}

function positiveStudentLoanAmountExists() {
  const interest = state.input.student_loan_interest;
  const fields = [
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
  ];
  if (fields.some((field) => hasPositiveAmount(interest[field]))) return true;
  return Object.values(interest.federal_unused_by_origin_year || {}).some((value) => hasPositiveAmount(value));
}

function applyNoCurrentStudentLoanInterest() {
  const answered = ["student_loan_interest.reviewed"];
  state.input.student_loan_interest.reviewed = true;
  if (setZeroUnlessPositive(state.input, "student_loan_interest.federal_current_year_paid")) {
    answered.push("student_loan_interest.federal_current_year_paid");
  }
  if (setZeroUnlessPositive(state.input, "student_loan_interest.quebec_current_year_paid")) {
    answered.push("student_loan_interest.quebec_current_year_paid");
  }
  clearMissingFactsForPaths(selectedYearState(), answered);
  if (
    hasPositiveAmount(state.input.student_loan_interest.federal_current_year_paid) ||
    hasPositiveAmount(state.input.student_loan_interest.quebec_current_year_paid)
  ) {
    setBanner("Existing current-year student-loan amounts were preserved. Review the visible student-loan fields before calculating.");
  }
  markDirty();
  renderAll();
}

function applyNoStudentLoanInterestAtAll() {
  const hadPositiveAmount = positiveStudentLoanAmountExists();
  const answered = ["student_loan_interest.reviewed"];
  state.input.student_loan_interest.reviewed = true;
  if (!hadPositiveAmount) {
    state.input.taxpayer.has_student_loan_interest = false;
    state.input.student_loan_interest.qualifying_government_loans_confirmed = false;
    answered.push("taxpayer.has_student_loan_interest", "student_loan_interest.qualifying_government_loans_confirmed");
  }
  if (setZeroUnlessPositive(state.input, "student_loan_interest.federal_current_year_paid")) {
    answered.push("student_loan_interest.federal_current_year_paid");
  }
  if (setZeroUnlessPositive(state.input, "student_loan_interest.quebec_current_year_paid")) {
    answered.push("student_loan_interest.quebec_current_year_paid");
  }
  if (!hadPositiveAmount) {
    if (setZeroUnlessPositive(state.input, "student_loan_interest.federal_claim_amount")) {
      answered.push("student_loan_interest.federal_claim_amount");
    }
    if (setZeroUnlessPositive(state.input, "student_loan_interest.quebec_prior_unused")) {
      answered.push("student_loan_interest.quebec_prior_unused");
    }
    if (setZeroUnlessPositive(state.input, "student_loan_interest.quebec_claim_amount")) {
      answered.push("student_loan_interest.quebec_claim_amount");
    }
    setFederalUnusedOriginsToZeroUnlessPositive(answered);
  }
  clearMissingFactsForPaths(selectedYearState(), answered);
  if (hadPositiveAmount) {
    setBanner("Existing student-loan amounts were preserved. Review the visible student-loan fields before calculating.");
  }
  markDirty();
  renderAll();
}

function candidateCorrectionControlForMissingFact(fact) {
  const target = slipCorrectionTargetForPath(fact?.path);
  if (!target) return null;
  const slipValue = target.group === "fields" ? target.slip?.fields?.[target.key] : target.slip?.[target.key];
  return candidateCorrectionRow(
    target.candidateId,
    target.group,
    target.key,
    fieldForCorrection(slipValue),
    { ...target.spec, label: fact.label || target.spec.label },
  );
}

function controlForMissingFact(fact) {
  const path = fact.path;
  if (fact.code === "carryforward_conflict" || String(path || "").startsWith("carryforwards.conflicts")) return null;
  if (!path || path === "slips") {
    const wrap = node("div", "field");
    wrap.append(node("span", "label", "Income slips for this year"));
    const button = node("button", "ghost", "Confirm no income slips for this active year");
    button.type = "button";
    button.addEventListener("click", () => {
      state.input.inventory.no_income_sources = true;
      state.input.inventory.income_sources_reviewed = true;
      const yearState = selectedYearState();
      if (yearState?.missing_facts) yearState.missing_facts = yearState.missing_facts.filter((fact) => fact.path !== "slips");
      markDirty();
      renderAll();
    });
    wrap.append(button, node("span", "hint", "This makes the selected year active with no income slips confirmed."));
    return wrap;
  }
  const candidateControl = candidateCorrectionControlForMissingFact(fact);
  if (candidateControl) return candidateControl;
  const label = fact.label || path;
  const spec = controlSpecForPath(path);
  if (!spec) return null;
  if (spec.kind === "boolean") return boolSelect(path, label);
  if (spec.kind === "number") return numberInput(path, label);
  if (spec.kind === "months") return monthInput(path, label);
  if (spec.kind === "money") return moneyInput(path, label);
  if (spec.kind === "province") return provinceSelect();
  if (spec.kind === "choice") return choiceInput(path, label, spec.options);
  return null;
}

function carryAmount(value) {
  return value?.amount ?? value;
}

function appendCarryforwardConflictChoices(container, yearState) {
  const conflicts = yearState?.carryforwards?.conflicts || [];
  if (!conflicts.length) return;
  const card = node("article", "review-card");
  card.append(node("h4", null, "Carryforward opening balance choices"));
  conflicts.forEach((conflict) => {
    const row = node("div", "carry-choice");
    row.append(node("span", "label", conflict.key));
    row.append(node("span", null, `Assessed opening balance: ${formatMoneyAmount(conflict.assessed_amount)}`));
    row.append(node("span", null, `Preceding-year proposed closing balance: ${formatMoneyAmount(conflict.proposed_amount)}`));
    const buttons = node("div", "toolbar");
    const assessed = node("button", conflict.resolved_selection === "assessed" ? "secondary" : "ghost", "Use assessed");
    assessed.type = "button";
    assessed.addEventListener("click", () => queueCarryforwardChoice(yearState.tax_year, conflict.key, "assessed"));
    const proposed = node("button", conflict.resolved_selection === "proposed" ? "secondary" : "ghost", "Use proposed");
    proposed.type = "button";
    proposed.addEventListener("click", () => queueCarryforwardChoice(yearState.tax_year, conflict.key, "proposed"));
    buttons.append(assessed, proposed);
    row.append(buttons);
    card.append(row);
  });
  container.append(card);
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

function renderImportedSlip(card, slip, index, candidateId) {
  const summary = node("div", "grid-form");
  summary.append(
    readonlyField("Imported from batch PDF", candidateId),
    readonlyField("Slip type", slip.slip_type || "Unknown"),
    readonlyField("Issuer or payer", slip.issuer_id || "Unknown"),
    readonlyField("Slip tax year", slip.tax_year ?? "Unknown"),
  );
  if (slip.slip_type === "T4") {
    summary.append(
      readonlyField("Province of employment", slip.province_of_employment ?? "Unknown"),
      readonlyField("T4 box 28 CPP/QPP exempt", slip.cpp_qpp_exempt === null || slip.cpp_qpp_exempt === undefined ? "Unknown" : slip.cpp_qpp_exempt ? "Yes" : "No"),
      readonlyField("T4 box 28 EI exempt", slip.ei_exempt === null || slip.ei_exempt === undefined ? "Unknown" : slip.ei_exempt ? "Yes" : "No"),
      readonlyField("T4 box 28 PPIP exempt", slip.ppip_exempt === null || slip.ppip_exempt === undefined ? "Unknown" : slip.ppip_exempt ? "Yes" : "No"),
    );
  }
  card.append(summary);
  card.append(node("p", "muted", "Use source correction controls for imported slips. Direct edits are applied only after review changes are submitted."));

  const table = node("table", "field-table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["Box / field", "Imported value"].forEach((heading) => headRow.append(node("th", null, heading)));
  thead.append(headRow);
  const tbody = document.createElement("tbody");
  for (const [key, value] of Object.entries(slip.fields || {})) {
    const row = document.createElement("tr");
    row.append(node("td", null, key), node("td", null, value ?? ""));
    tbody.append(row);
  }
  table.append(thead, tbody);
  card.append(table);

  appendSupportedCandidateCorrections(card, slip, candidateId);

  const controls = node("div", "toolbar");
  const exclude = node("button", "ghost", "Exclude imported slip");
  exclude.type = "button";
  exclude.dataset.action = "exclude-imported-slip";
  exclude.dataset.candidateId = candidateId;
  exclude.addEventListener("click", () => queueDecision(candidateId, "exclude"));
  controls.append(exclude);
  card.append(controls);

  const url = state.batchPdfUrls[candidateId] || state.batchPdfUrls[slip.document_id] || state.pdfUrls[index];
  if (url) {
    const frame = document.createElement("iframe");
    frame.className = "pdf-preview";
    frame.title = `Source PDF preview for imported slip ${index + 1}`;
    frame.src = url;
    card.append(frame);
  }
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
    const importedCandidateId = sourceCandidateIdForSlip(slip);
    title.append(node("h3", null, `Slip ${index + 1}`));
    const remove = node("button", "ghost", "Remove");
    remove.type = "button";
    if (importedCandidateId) {
      remove.dataset.action = "exclude-imported-slip";
      remove.dataset.candidateId = importedCandidateId;
    }
    remove.addEventListener("click", () => {
      if (importedCandidateId) {
        queueDecision(importedCandidateId, "exclude");
        return;
      }
      revokePdf(index);
      state.input.slips.splice(index, 1);
      state.pdfUrls.splice(index, 1);
      renderSlips();
      markDirty();
    });
    title.append(remove);
    card.append(title);

    if (importedCandidateId) {
      renderImportedSlip(card, slip, index, importedCandidateId);
      list.append(card);
      return;
    }

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
        "Use this preview for manual source checks. Batch PDF import above handles automatic candidate extraction.",
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
  if (state.mode === "batch" && state.workspace) {
    const result = state.batchResult;
    if (!result) {
      container.append(node("p", "muted", "No batch calculation has run yet."));
      return;
    }
    if (result.status === "blocked" && result.reason === "unassigned_candidates_require_review") {
      const card = node("article", "problem-card");
      card.append(node("span", "pill", "unassigned_candidates"));
      card.append(node("h3", null, "Some imported slips need year or type review before batch calculation."));
      card.append(node("p", "muted", "Review unassigned candidates in the Years step, then calculate again."));
      container.append(card);
    }
    for (const year of state.activeYears) {
      const yearResult = result.results?.[year];
      if (!yearResult || yearResult.status === "complete") continue;
      const card = node("article", "problem-card");
      card.append(node("span", "pill", yearResult.reason || "blocked"));
      card.append(node("h3", null, `${year} is not ready to calculate`));
      const facts = yearResult.missing_facts || [];
      const unresolved = yearResult.unresolved_candidates || [];
      if (unresolved.length) card.append(node("p", "muted", `${unresolved.length} slip candidate${unresolved.length === 1 ? "" : "s"} still need review.`));
      if (facts.length) {
        const list = document.createElement("ul");
        facts.slice(0, 8).forEach((fact) => list.append(node("li", null, fact.label || fact.path || fact.code)));
        card.append(list);
      }
      container.append(card);
    }
    if (!container.children.length) container.append(node("p", "muted", "Active years either calculated or are waiting for the backend to mark them ready."));
    return;
  }
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
  if (state.mode === "batch" && state.workspace) {
    if (!state.batchResult) {
      container.append(node("p", "muted", "No year results are available yet."));
      return;
    }
    for (const year of state.activeYears) {
      const result = state.batchResult.results?.[year];
      const block = node("section", "result-block");
      block.append(node("h3", null, `${year} return`));
      if (!result) {
        block.append(node("p", "muted", "No result returned for this active year."));
        container.append(block);
        continue;
      }
      if (result.status !== "complete") {
        block.append(node("p", "muted", result.reason || "Blocked"));
        container.append(block);
        continue;
      }
      const cards = node("div", "result-cards");
      cards.append(
        node("p", "money-card", formatHeadlineMoney(result.federal_refund_or_balance, "Federal")),
        node("p", "money-card", formatHeadlineMoney(result.quebec_refund_or_balance, "Quebec")),
      );
      block.append(cards);
      if (result.warnings?.length) {
        const warningBox = node("div", "warning-card");
        warningBox.append(node("h4", null, "Preparation warnings"));
        const list = document.createElement("ul");
        result.warnings.forEach((warning) => list.append(node("li", null, warning)));
        warningBox.append(list);
        block.append(warningBox);
      }
      appendCarryforwards(block, result.carryforwards);
      const lines = result.lines || [];
      if (lines.length) {
        const details = document.createElement("details");
        details.className = "result-block schedule-details nested-result";
        const summary = document.createElement("summary");
        summary.textContent = `Full trace: ${lines.length} form lines`;
        details.append(summary);
        details.append(lineTableFor(lines));
        block.append(details);
      }
      container.append(block);
    }
    return;
  }
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
    appendCarryforwards(headline, state.result.carryforwards);
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

function importedPayloadWorkspace(parsed) {
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return null;
  if (parsed.schema_version === "batch-workspace-v1" && parsed.years) return parsed;
  if (parsed.workspace?.schema_version === "batch-workspace-v1") return parsed.workspace;
  if (parsed.input?.schema_version === "batch-workspace-v1") return parsed.input;
  return null;
}

function normalizeImportedWorkspace(parsed) {
  const workspace = importedPayloadWorkspace(parsed);
  if (!workspace) return { ok: false, message: "The selected JSON is not a batch workspace." };
  if (!workspace.years || !yearKeys.every((year) => workspace.years[year]?.input?.tax_year === Number(year))) {
    return { ok: false, message: "The selected batch workspace is missing one or more 2020-2025 year inputs." };
  }
  if (workspace.schema_version !== "batch-workspace-v1") {
    return { ok: false, message: "The selected batch workspace uses an unsupported schema version." };
  }
  const normalized = clone(workspace);
  normalized.unassigned_candidates = normalized.unassigned_candidates || [];
  normalized.duplicate_candidates = normalized.duplicate_candidates || [];
  normalized.excluded_candidates = normalized.excluded_candidates || [];
  normalized.source_candidates = normalized.source_candidates || {};
  normalized.file_errors = normalized.file_errors || [];
  normalized.active_years = Array.isArray(normalized.active_years) ? normalized.active_years : [];
  normalized.corrections = Array.isArray(normalized.corrections) ? normalized.corrections : [];
  normalized.decisions = Array.isArray(normalized.decisions) ? normalized.decisions : [];
  normalized.carryforward_choices = Array.isArray(normalized.carryforward_choices) ? normalized.carryforward_choices : [];
  normalized.correction_audit = Array.isArray(normalized.correction_audit) ? normalized.correction_audit : [];
  return { ok: true, workspace: normalized };
}

function normalizeImportedJson(parsed) {
  const batch = normalizeImportedWorkspace(parsed);
  if (batch.ok) return { ...batch, mode: "batch", pendingReviewActions: normalizeReviewActions(parsed?.pending_review_actions) };
  const single = normalizeImportedInput(parsed);
  if (single.ok) return { ...single, mode: "single" };
  return single;
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

function addBatchFiles(files) {
  const accepted = [];
  Array.from(files || []).forEach((file) => {
    const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    const existing = state.batchFiles.find((item) => item.name === file.name && item.size === file.size);
    if (existing) return;
    if (!isPdf) {
      state.batchFiles.push({ name: file.name, size: file.size, status: "Rejected: PDF files only" });
      return;
    }
    state.batchFiles.push({ name: file.name, size: file.size, file, status: "Ready to import" });
    if (typeof URL !== "undefined" && URL.createObjectURL) state.batchPdfUrls[file.name] = URL.createObjectURL(file);
    accepted.push(file);
  });
  renderBatchStatus();
  return accepted;
}

function mapImportedDocuments(documents) {
  state.workspaceImportDocuments = {};
  (documents || []).forEach((document) => {
    state.workspaceImportDocuments[document.document_id] = document;
    const fileUrl = state.batchPdfUrls[document.filename];
    if (fileUrl) state.batchPdfUrls[document.document_id] = fileUrl;
    const queued = state.batchFiles.find((item) => item.name === document.filename);
    if (queued) {
      queued.document_id = document.document_id;
      queued.status = document.status === "processed" ? "Imported" : document.status || "Reviewed by importer";
    }
  });
}

async function importPdfs(files) {
  const accepted = addBatchFiles(files);
  if (!accepted.length) {
    setBanner("Select one or more PDF files to import.");
    return;
  }
  const formData = new FormData();
  accepted.forEach((file) => formData.append("files", file, file.name));
  accepted.forEach((file) => {
    const queued = state.batchFiles.find((item) => item.file === file);
    if (queued) queued.status = "Importing...";
  });
  renderBatchStatus();
  try {
    const response = await fetch(state.schema.batch_pdf.endpoint, {
      method: "POST",
      body: formData,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail?.message || "The local PDF importer rejected the files.");
    mapImportedDocuments(payload.import_result?.documents || []);
    activateBatchWorkspace(payload.workspace);
    state.sampleLoaded = false;
    $("#calculation-state").textContent = "";
    setBanner("PDF import finished. Review the active years and answer only the remaining questions.");
    renderAll();
  } catch (error) {
    accepted.forEach((file) => {
      const queued = state.batchFiles.find((item) => item.file === file);
      if (queued) queued.status = `Import failed: ${error.message || "local service error"}`;
    });
    setBanner("PDF import failed. Valid selected PDFs are still retained in browser memory for another try.");
    renderBatchStatus();
  }
}

function lineTableFor(lines) {
  const table = node("table", "line-table");
  const thead = document.createElement("thead");
  const head = document.createElement("tr");
  ["Form", "Line", "Label", "Value", "Status", "Details"].forEach((heading) => head.append(node("th", null, heading)));
  thead.append(head);
  const tbody = document.createElement("tbody");
  lines.forEach((line) => {
    const row = document.createElement("tr");
    const detailsCell = document.createElement("td");
    const detailItems = [];
    if (line.inputs?.length) detailItems.push(...line.inputs.map((input) => `Input: ${input}`));
    if (line.formula_id) detailItems.push(`Calculation step: ${line.formula_id}`);
    if (line.source_ids?.length) detailItems.push(`Sources: ${line.source_ids.join(", ")}`);
    detailsCell.append(detailList("Show", detailItems));
    row.append(
      node("td", null, line.form_id),
      node("td", null, line.line_id),
      node("td", null, line.explanation || `Line ${line.line_id}`),
      node("td", null, formatLineValue(line.value)),
      node("td", null, line.status),
      detailsCell,
    );
    tbody.append(row);
  });
  table.append(thead, tbody);
  return table;
}

function appendCarryforwards(container, carryforwards) {
  const entries = Object.entries(carryforwards || {});
  if (!entries.length) return;
  const box = node("div", "warning-card");
  box.append(node("h4", null, "Proposed closing carryforwards"));
  box.append(node("p", "muted", "These are calculator outputs for review. They are not assessed NOA opening balances for another year."));
  const list = document.createElement("ul");
  entries.forEach(([key, value]) => {
    const amount = value?.amount ?? value;
    const explanation = value?.explanation ? ` - ${value.explanation}` : "";
    list.append(node("li", null, `${key}: ${formatMoneyAmount(amount)}${explanation}`));
  });
  box.append(list);
  container.append(box);
}

function activeWorkspaceForCalculation() {
  if (!state.workspace) return null;
  const workspace = clone(state.workspace);
  workspace.active_years = activeYearNumbers();
  return workspace;
}

async function applyReviewActions({ render = true } = {}) {
  if (!state.workspace || pendingReviewCount() === 0) return true;
  $("#calculation-state").textContent = "Applying PDF review choices...";
  let response;
  let payload;
  try {
    response = await fetch(state.schema.batch_pdf.reconcile_endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(reviewRequestPayload()),
    });
    payload = await response.json();
  } catch {
    $("#calculation-state").textContent = "The local workspace could not apply the review choices.";
    setBanner("Review choices were not applied. They are still pending in memory.");
    if (render) renderAll();
    return false;
  }
  if (!response.ok) {
    const detail = payload?.detail;
    const errors = (detail?.errors || []).map((error) => error.message || error.path).filter(Boolean).slice(0, 3).join("; ");
    $("#calculation-state").textContent = "The local workspace rejected the review choices.";
    setBanner(errors ? `Review choices were not applied: ${errors}` : detail?.message || "Review choices were not applied.");
    if (render) renderAll();
    return false;
  }
  replaceWorkspaceFromBackend(payload);
  state.pendingReviewActions = emptyReviewActions();
  state.batchResult = null;
  state.result = null;
  state.responseSources = {};
  state.dirty = true;
  state.inputRevision += 1;
  $("#save-result").disabled = true;
  $("#print-packet").disabled = true;
  $("#calculation-state").textContent = "Review choices applied. Calculate to refresh results.";
  setBanner("Review choices were applied to the workspace.");
  if (render) renderAll();
  return true;
}

async function calculateBatch() {
  const requestId = state.latestCalculateRequest + 1;
  state.latestCalculateRequest = requestId;
  if (pendingReviewCount() > 0) {
    const applied = await applyReviewActions({ render: false });
    if (!applied || requestId !== state.latestCalculateRequest) {
      renderAll();
      renderProblems();
      renderLineTables();
      return;
    }
  }
  const requestRevision = state.inputRevision;
  $("#calculation-state").textContent = "Calculating active ready years...";
  let response;
  let payload;
  try {
    response = await fetch(state.schema.batch_pdf.calculate_endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(activeWorkspaceForCalculation()),
    });
    payload = await response.json();
  } catch {
    if (requestId !== state.latestCalculateRequest || requestRevision !== state.inputRevision) return;
    $("#calculation-state").textContent = "The local batch calculator did not return a usable response.";
    state.batchResult = {
      schema_version: "batch-calculation-v1",
      status: "blocked",
      reason: "local_service_error",
      results: {},
    };
    renderProblems();
    renderLineTables();
    return;
  }
  if (requestId !== state.latestCalculateRequest || requestRevision !== state.inputRevision) return;
  if (!response.ok) {
    $("#calculation-state").textContent = "Batch workspace was rejected.";
    state.batchResult = {
      schema_version: "batch-calculation-v1",
      status: "blocked",
      reason: payload.detail?.code || "request_failed",
      results: {},
    };
    renderProblems();
    renderLineTables();
    return;
  }
  state.dirty = false;
  if (payload.workspace) replaceWorkspaceFromBackend(payload.workspace);
  state.batchResult = payload;
  state.result = null;
  $("#save-result").disabled = false;
  $("#print-packet").disabled = false;
  $("#calculation-state").textContent = "Batch calculation finished for active years that the backend accepted as ready.";
  renderAll();
  renderProblems();
  renderLineTables();
}

async function calculate() {
  if (state.mode === "batch" && state.workspace) return calculateBatch();
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
  if (state.mode === "batch" && state.workspace) {
    lines.push("TaxAgent local batch review packet");
    lines.push("No submission. Federal and Quebec filing are separate.");
    lines.push(`Active years: ${state.activeYears.join(", ")}`);
    lines.push("Source PDFs are not embedded in this packet.");
    lines.push("");
    for (const year of state.activeYears) {
      const result = state.batchResult?.results?.[year];
      lines.push(`${year}`);
      lines.push(`Status: ${result?.status || "not calculated"}`);
      if (result?.status === "complete") {
        lines.push(`Federal: ${result.federal_refund_or_balance ?? ""}`);
        lines.push(`Quebec: ${result.quebec_refund_or_balance ?? ""}`);
        lines.push(`Lines: ${(result.lines || []).length}`);
      } else if (result) {
        lines.push(`Reason: ${result.reason || ""}`);
        for (const fact of result.missing_facts || []) lines.push(`- ${fact.code}: ${fact.label}`);
      }
      lines.push("");
    }
    return `${lines.join("\n")}\n`;
  }
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
  setSelectedYear(state.selectedYear);
  renderBatchStatus();
  renderYearOverview();
  renderCandidateReview();
  renderEvidenceReview();
  renderProfileReuse();
  renderMissingFacts();
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
    if (state.workspace && !state.activeYears.includes(state.selectedYear)) state.activeYears.push(state.selectedYear);
    state.input.slips.push(newSlip());
    renderSlips();
    markDirty();
  });
  $("#calculate-button").addEventListener("click", calculate);
  $("#save-input").addEventListener("click", () =>
    downloadJson(
      state.mode === "batch" ? "taxagent_batch_workspace_reviewed.json" : "taxagent_2025_qc_input.json",
      state.mode === "batch"
        ? {
            workspace: state.workspace,
            active_years: state.activeYears,
            selected_year: state.selectedYear,
            pending_review_actions: state.pendingReviewActions,
            original_pdfs_embedded: false,
            source_pdf_availability: Object.keys(state.batchPdfUrls).length
              ? "Source PDFs are retained only in this browser session and are not embedded in the JSON."
              : "Source PDFs are not available in this restored/exported JSON.",
          }
        : state.input,
    ),
  );
  $("#save-result").addEventListener("click", () =>
    downloadJson(
      state.mode === "batch" ? "taxagent_batch_results.json" : "taxagent_2025_qc_result.json",
      state.mode === "batch"
        ? {
            result: state.batchResult,
            workspace: state.workspace,
            active_years: state.activeYears,
            pending_review_actions: state.pendingReviewActions,
            original_pdfs_embedded: false,
          }
        : { result: state.result, sources: state.responseSources },
    ),
  );
  $("#print-packet").addEventListener("click", () =>
    downloadText(state.mode === "batch" ? "taxagent_batch_review_packet.txt" : "taxagent_2025_qc_review_packet.txt", reviewPacket()),
  );
  $("#reset").addEventListener("click", () => {
    revokeAllPdfs();
    state.mode = "single";
    state.workspace = null;
    state.selectedYear = "2025";
    state.activeYears = ["2025"];
    state.batchResult = null;
    state.workspaceImportDocuments = {};
    state.pendingReviewActions = emptyReviewActions();
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
    activateSingleInput(sample.input);
    state.pendingReviewActions = emptyReviewActions();
    state.dirty = true;
    state.sampleLoaded = true;
    setBanner(sample.label);
    renderAll();
    markDirty();
  });
  $("#import-json").addEventListener("change", importJson);
  $("#import-pdfs")?.addEventListener("change", (event) => importPdfs(event.target.files));
  $("#pdf-drop-zone")?.addEventListener("click", () => $("#import-pdfs").click());
  $("#pdf-drop-zone")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      $("#import-pdfs").click();
    }
  });
  $("#pdf-drop-zone")?.addEventListener("dragover", (event) => {
    event.preventDefault();
    $("#pdf-drop-zone").classList.add("dragging");
  });
  $("#pdf-drop-zone")?.addEventListener("dragleave", () => $("#pdf-drop-zone").classList.remove("dragging"));
  $("#pdf-drop-zone")?.addEventListener("drop", (event) => {
    event.preventDefault();
    $("#pdf-drop-zone").classList.remove("dragging");
    importPdfs(event.dataTransfer?.files);
  });
  $("#create-zero-year")?.addEventListener("click", () => {
    if (!state.workspace) {
      activateBatchWorkspace({
        schema_version: "batch-workspace-v1",
        years: Object.fromEntries(
          yearKeys.map((year) => [
            year,
            {
              tax_year: Number(year),
              input: Object.assign(clone(state.schema.blank_input), { tax_year: Number(year) }),
              evidence: {},
              unresolved_candidates: [],
              duplicate_candidates: [],
              missing_facts: [{ path: "slips", code: "missing_imported_slips", label: `Import or enter income slips for ${year}, or explicitly confirm there are none.` }],
              carryforwards: { assessed_opening_balances: {}, proposed_closing_balances: {}, conflicts: [], downstream_invalidated: false },
              ready_to_calculate: false,
            },
          ]),
        ),
        unassigned_candidates: [],
        duplicate_candidates: [],
      });
    }
    state.input.inventory.no_income_sources = true;
    state.input.inventory.income_sources_reviewed = true;
    const yearState = selectedYearState();
    if (yearState?.missing_facts) yearState.missing_facts = yearState.missing_facts.filter((fact) => fact.path !== "slips");
    if (!state.activeYears.includes(state.selectedYear)) state.activeYears.push(state.selectedYear);
    markDirty();
    setBanner(`Created ${state.selectedYear} as an explicit no-slip active year.`);
    renderAll();
  });
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
    setBanner("Use Restore JSON for TaxAgent JSON files. Use the PDF drop zone to import local PDFs.");
    event.target.value = "";
    return;
  }
  if (state.dirty && !window.confirm("Replace the current in-memory input with the selected JSON file?")) {
    event.target.value = "";
    return;
  }
  try {
    const parsed = JSON.parse(await file.text());
    const normalized = normalizeImportedJson(parsed);
    if (!normalized.ok) {
      setBanner(normalized.message);
      event.target.value = "";
      return;
    }
    revokeAllPdfs();
    if (normalized.mode === "batch") {
      activateBatchWorkspace(normalized.workspace, parsed.selected_year || parsed.selectedYear || "2025");
      state.activeYears = Array.isArray(parsed.active_years) ? parsed.active_years.map(String) : state.activeYears;
      state.pendingReviewActions = normalizeReviewActions(normalized.pendingReviewActions);
    } else {
      activateSingleInput(normalized.input);
      state.pendingReviewActions = emptyReviewActions();
    }
    state.sampleLoaded = false;
    state.dirty = true;
    $("#calculation-state").textContent = "Imported JSON into memory. Calculate to validate it.";
    $("#problems").replaceChildren();
    $("#results").replaceChildren();
    $("#save-result").disabled = true;
    $("#print-packet").disabled = true;
    setBanner(normalized.mode === "batch" ? "Restored batch workspace JSON. Source PDF previews are unavailable until PDFs are selected again." : "Imported JSON into memory. Calculate to validate it.");
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
    normalizeImportedWorkspace,
    normalizeImportedJson,
    activateBatchWorkspace,
    applySelectedProfileFactsToActiveYears,
    activeWorkspaceForCalculation,
    controlSpecForPath,
    reviewRequestPayload,
    applyReviewActions,
    queueCorrection,
    queueDecision,
    queueCarryforwardChoice,
    importPdfs,
    importJson,
    calculate,
    markDirty,
    renderFacts,
    renderMissingFacts,
    renderSlips,
    renderResult,
    reviewPacket,
  };
}

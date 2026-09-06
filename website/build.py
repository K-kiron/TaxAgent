"""Build the TaxAgent static documentation site with only the Python stdlib."""

from __future__ import annotations

import argparse
import html
import json
import shutil
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
TEMPLATE = (ROOT / "templates" / "page.html").read_text(encoding="utf-8")
DEV_COMMIT = "a40a171"
REPO_URL = "https://github.com/K-kiron/TaxAgent"
DEV_README = f"{REPO_URL}/blob/{DEV_COMMIT}/README.md"
DEV_GUIDE = f"{REPO_URL}/blob/{DEV_COMMIT}/docs/user/guide.md"
DEV_COVERAGE = f"{REPO_URL}/blob/{DEV_COMMIT}/docs/coverage.md"
DEV_EXAMPLE = f"{REPO_URL}/blob/dev/examples/synthetic_2025_qc_salary_student.json"
DEV_CONTRIBUTING = f"{REPO_URL}/blob/dev/CONTRIBUTING.md"
MARKER = ".taxagent-site-output.json"


@dataclass(frozen=True)
class Page:
    key: str
    lang: str
    locale: str
    path: str
    title: str
    description: str
    nav_label: str
    skip_label: str
    brand_note: str
    language_label: str
    footer_text: str
    footer_links: str
    body: str


PAGES = [
    Page(
        key="overview",
        lang="en",
        locale="en-CA",
        path="/",
        title="TaxAgent Canada - Quebec and federal tax preparation preview",
        description="Evaluate TaxAgent Canada, an open-source local preparation preview for bounded Canadian and Quebec tax workflows.",
        nav_label="Primary navigation",
        skip_label="Skip to content",
        brand_note="Canadian and Quebec preparation preview",
        language_label="Language",
        footer_text="TaxAgent Canada is a preview project. It prepares review outputs; it does not file returns or provide certified advice.",
        footer_links=f'<a href="{REPO_URL}">GitHub</a> | <a href="{DEV_README}">dev README</a> | <a href="{DEV_GUIDE}">user guide</a>',
        body="""
<section class="hero">
  <div>
    <p class="eyebrow">Open-source tax preparation preview</p>
    <h1>TaxAgent Canada</h1>
    <p class="lede">A local PDF intake and return-preparation workspace for reviewers evaluating a bounded Canadian and Quebec salary/student workflow. The runnable source is available on <code>dev</code>; the coverage wording here is based on the documented revision <a href="https://github.com/K-kiron/TaxAgent/blob/a40a171/docs/coverage.md">a40a171</a>.</p>
  </div>
  <aside class="hero-card" aria-label="Project facts">
    <dl>
      <div><dt>Status</dt><dd>Development preview source is available on <code>dev</code>.</dd></div>
      <div><dt>Preparation model</dt><dd>PDF/OCR intake and deterministic calculation run locally on loopback.</dd></div>
      <div><dt>Boundary</dt><dd>No CRA or Revenu Quebec sign-in, no filing submission, no certified advice.</dd></div>
    </dl>
  </aside>
</section>
<section class="band" id="evaluate">
  <div class="content-grid">
    <div>
      <p class="eyebrow">Evaluate</p>
      <h2>Inspect scope before trying it.</h2>
    </div>
    <div class="stack">
      <p>TaxAgent is built for technically comfortable evaluators, contributors, and reviewers who want source-visible Canadian tax preparation logic with a careful Quebec focus.</p>
      <p>The useful preview workflow imports supported tax-slip PDFs, asks for missing facts, blocks unsupported cases, calculates covered return lines, and exports JSON or text packets for review.</p>
      <div class="callout">Use a certified or authorized filing path for actual submission. TaxAgent outputs are preparation and review materials.</div>
      <p><a href="getting-started/">Try the development preview</a>, follow the <a href="walkthrough/">synthetic walkthrough</a>, or read the <a href="coverage/">versioned coverage summary</a>.</p>
    </div>
  </div>
</section>
<section class="band alt" id="signals">
  <div class="card-grid">
    <article class="card"><h3>Inspectable</h3><p>Public source, Apache-2.0 license, scoped deterministic calculation, and exact preview documentation links.</p></article>
    <article class="card"><h3>Local preparation</h3><p>The preparation app runs at <code>127.0.0.1:8056</code>. PDF/OCR intake and return calculation do not require a model endpoint.</p></article>
    <article class="card"><h3>Conservative scope</h3><p>Unsupported facts block calculation instead of being filled with broad estimates.</p></article>
  </div>
</section>
""",
    ),
    Page(
        key="getting-started",
        lang="en",
        locale="en-CA",
        path="/getting-started/",
        title="Getting started with the TaxAgent development preview",
        description="Install the TaxAgent development preview from the dev branch and start the local preparation workspace.",
        nav_label="Primary navigation",
        skip_label="Skip to content",
        brand_note="Canadian and Quebec preparation preview",
        language_label="Language",
        footer_text="Preview instructions are branch-aware: clone dev to run the documented development source.",
        footer_links=f'<a href="{REPO_URL}">GitHub</a> | <a href="{DEV_README}">dev README</a> | <a href="{DEV_GUIDE}">user guide</a>',
        body="""
<section class="hero">
  <div>
    <p class="eyebrow">Getting started</p>
    <h1>Run the local preview.</h1>
    <p class="lede">Clone the <code>dev</code> branch explicitly. The development source is the install target for this preview site.</p>
  </div>
  <aside class="hero-card" aria-label="Preview requirements">
    <dl>
      <div><dt>Python</dt><dd>Python 3.11+</dd></div>
      <div><dt>Branch</dt><dd><code>dev</code> at documented preview revision <a href="https://github.com/K-kiron/TaxAgent/blob/a40a171/README.md">a40a171</a></dd></div>
      <div><dt>Local URL</dt><dd><code>http://127.0.0.1:8056</code></dd></div>
    </dl>
  </aside>
</section>
<section class="band" id="install">
  <div class="content-grid">
    <div><p class="eyebrow">Install</p><h2>Windows PowerShell</h2></div>
    <div class="stack">
      <pre><code>git clone --branch dev https://github.com/K-kiron/TaxAgent.git
cd TaxAgent
py -3.11 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install --upgrade pip
.\\.venv\\Scripts\\python.exe -m pip install ".[web]"
.\\.venv\\Scripts\\taxagent.exe doctor
.\\.venv\\Scripts\\taxagent.exe start</code></pre>
      <p>Open <code>http://127.0.0.1:8056</code>. The preview workspace is designed for loopback use.</p>
    </div>
  </div>
</section>
<section class="band" id="install-unix">
  <div class="content-grid">
    <div><p class="eyebrow">Install</p><h2>Linux or macOS</h2></div>
    <div class="stack">
      <pre><code>git clone --branch dev https://github.com/K-kiron/TaxAgent.git
cd TaxAgent
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ".[web]"
taxagent doctor
taxagent start</code></pre>
      <p>Open <code>http://127.0.0.1:8056</code>. The local preparation workflow does not require the advisory endpoint.</p>
    </div>
  </div>
</section>
<section class="band alt" id="workflow">
  <div class="content-grid">
    <div><p class="eyebrow">Workflow</p><h2>Prepare, review, export.</h2></div>
    <ol class="steps">
      <li>Collect your own issuer, CRA, and Revenu Quebec records before calculating.</li>
      <li>Import local PDF slips or restore a saved TaxAgent JSON workspace.</li>
      <li>Resolve review candidates and missing facts that block calculation.</li>
      <li>Calculate ready active years and review any remaining blockers.</li>
      <li>Save input JSON, result JSON, or the text review packet for your own records.</li>
    </ol>
  </div>
</section>
<section class="band" id="docs">
  <div class="content-grid">
    <div><p class="eyebrow">References</p><h2>Read the preview docs.</h2></div>
    <div class="stack">
      <p>The branch-specific README and user guide describe the current preview and its limits.</p>
      <p><a href="https://github.com/K-kiron/TaxAgent/blob/a40a171/README.md">Development README at a40a171</a></p>
      <p><a href="https://github.com/K-kiron/TaxAgent/blob/a40a171/docs/user/guide.md">Development user guide at a40a171</a></p>
      <p><a href="https://github.com/K-kiron/TaxAgent/blob/dev/CONTRIBUTING.md">Contributor guide on dev</a></p>
    </div>
  </div>
</section>
""",
    ),
    Page(
        key="walkthrough",
        lang="en",
        locale="en-CA",
        path="/walkthrough/",
        title="Synthetic TaxAgent walkthrough for the 2025 Quebec preview",
        description="Run a synthetic 2025 Quebec salary/student TaxAgent example and compare the deterministic output.",
        nav_label="Primary navigation",
        skip_label="Skip to content",
        brand_note="Canadian and Quebec preparation preview",
        language_label="Language",
        footer_text="The walkthrough uses synthetic facts only. Do not use personal records in public examples.",
        footer_links=f'<a href="{REPO_URL}">GitHub</a> | <a href="{DEV_EXAMPLE}">synthetic example</a> | <a href="{DEV_CONTRIBUTING}">contributor guide</a>',
        body="""
<section class="hero">
  <div>
    <p class="eyebrow">Synthetic walkthrough</p>
    <h1>One reproducible return packet.</h1>
    <p class="lede">This walkthrough uses a synthetic 2025 Quebec salary example. It contains no personal records, no government identifiers, and no real slips.</p>
  </div>
  <aside class="hero-card" aria-label="Expected result">
    <dl>
      <div><dt>Input</dt><dd><a href="https://github.com/K-kiron/TaxAgent/blob/dev/examples/synthetic_2025_qc_salary_student.json">synthetic_2025_qc_salary_student.json</a></dd></div>
      <div><dt>Complete result</dt><dd>Federal refund <code>2546.70</code>; Quebec refund <code>863.84</code>.</dd></div>
      <div><dt>Unsupported variant</dt><dd>Set <code>taxpayer.has_self_employment</code> to <code>true</code>; calculation blocks without refund or balance headlines.</dd></div>
    </dl>
  </aside>
</section>
<section class="band" id="run">
  <div class="content-grid">
    <div><p class="eyebrow">Run</p><h2>Calculate from JSON.</h2></div>
    <div class="stack">
      <p>Clone <code>dev</code>, install the local web extra, then run the public CLI against the synthetic input.</p>
      <pre><code># Windows PowerShell
.\\.venv\\Scripts\\taxagent.exe calculate examples\\synthetic_2025_qc_salary_student.json --output synthetic_result.json

# Linux or macOS
taxagent calculate examples/synthetic_2025_qc_salary_student.json --output synthetic_result.json</code></pre>
      <p>The checked example is a plain <code>TaxReturnInput</code> JSON file. The CLI writes a deterministic calculation packet and returns success only when the result status is <code>complete</code>.</p>
    </div>
  </div>
</section>
<section class="band alt" id="expected-output">
  <div class="content-grid">
    <div><p class="eyebrow">Expected output</p><h2>Current engine result.</h2></div>
    <table class="scope-table">
      <tr><th>Status</th><td><code>complete</code></td></tr>
      <tr><th>Coverage profile</th><td><code>2025-qc-single-salaried-student-v1</code></td></tr>
      <tr><th>Federal headline</th><td><code>2546.70</code> refund</td></tr>
      <tr><th>Quebec headline</th><td><code>863.84</code> refund</td></tr>
      <tr><th>Line records</th><td>At least 600 line records across the federal and Quebec returns and schedules.</td></tr>
    </table>
  </div>
</section>
<section class="band" id="blocked-case">
  <div class="content-grid">
    <div><p class="eyebrow">Blocked case</p><h2>Unsupported facts stay visible.</h2></div>
    <div class="stack">
      <p>If the same synthetic input is changed to declare self-employment, the public test expects the CLI to return a blocked result with blocker code <code>unsupported_situation</code> and input path <code>taxpayer.has_self_employment</code>.</p>
      <p>Blocked results do not expose federal or Quebec refund/balance headlines.</p>
    </div>
  </div>
</section>
""",
    ),
    Page(
        key="coverage",
        lang="en",
        locale="en-CA",
        path="/coverage/",
        title="Versioned TaxAgent coverage for the Quebec preview",
        description="Read the versioned TaxAgent Quebec and federal preparation scope, supported inputs, and explicit exclusions.",
        nav_label="Primary navigation",
        skip_label="Skip to content",
        brand_note="Canadian and Quebec preparation preview",
        language_label="Language",
        footer_text="Coverage is a source-code and documentation statement, not certification or filing authorization.",
        footer_links=f'<a href="{REPO_URL}">GitHub</a> | <a href="{DEV_COVERAGE}">coverage at a40a171</a> | <a href="{DEV_CONTRIBUTING}">contributor guide</a>',
        body="""
<section class="hero">
  <div>
    <p class="eyebrow">Versioned coverage</p>
    <h1>What the preview covers.</h1>
    <p class="lede">This summary is based on the development documentation at revision <a href="https://github.com/K-kiron/TaxAgent/blob/a40a171/docs/coverage.md">a40a171</a>. Newer development changes may adjust the supported inputs, blockers, or calculated line set.</p>
  </div>
  <aside class="hero-card" aria-label="Coverage facts">
    <dl>
      <div><dt>Workspace years</dt><dd>2020 through 2025 local preparation workspace.</dd></div>
      <div><dt>Detailed matrix</dt><dd>2025 Quebec/federal line-by-line coverage for the bounded supported profile.</dd></div>
      <div><dt>Contribution entry</dt><dd><a href="https://github.com/K-kiron/TaxAgent/blob/dev/CONTRIBUTING.md">CONTRIBUTING.md on dev</a>.</dd></div>
    </dl>
  </aside>
</section>
<section class="band" id="supported-profile">
  <div class="content-grid">
    <div><p class="eyebrow">Supported profile</p><h2>Explicit answers required.</h2></div>
    <div class="stack">
      <p>The documented 2025 calculator profile is full-year Canadian and Quebec residency, Quebec province on December 31, single status, zero dependants, and an ordinary Quebec salary/student fact pattern.</p>
      <p>Calculation requires the user to confirm income-source review, deduction review, credit review, CRA records review, Revenu Quebec records review, unsupported-situation screens, instalments, drug-insurance months, tuition questions, and supported credit facts.</p>
    </div>
  </div>
</section>
<section class="band alt" id="supported-inputs">
  <div class="content-grid">
    <div><p class="eyebrow">Inputs</p><h2>Supported slip families.</h2></div>
    <ul class="pill-list">
      <li>T4 Quebec employment</li><li>RL-1 Quebec employment</li><li>T4A supported scholarship and RESP EAP boxes</li><li>T5 box 13 interest</li><li>RL-3 box D interest</li><li>T2202 tuition</li><li>RRSP receipts</li><li>RC210 and RL-19 supported advance-payment boxes</li>
    </ul>
  </div>
</section>
<section class="band" id="blocked-exclusions">
  <div class="content-grid">
    <div><p class="eyebrow">Exclusions</p><h2>Blocked rather than estimated.</h2></div>
    <div class="stack">
      <p>The documented exclusions include non-Quebec or part-year residency, filing statuses other than single, dependants, deceased or bankruptcy returns, self-employment, capital gains, rental income, foreign income or tax, foreign property over $100,000, crypto transactions, pension or benefit income, Indian Act exempt income, disability or caregiver claims, employment expenses, medical expenses, donations, childcare expenses, moving expenses, and tips or other employment income outside supported slip fields.</p>
      <p>Filing remains separate. TaxAgent does not submit returns, create filing-ready NETFILE/ReFILE/ImpôtNet Québec files, or request government credentials.</p>
    </div>
  </div>
</section>
""",
    ),
    Page(
        key="faq-scope",
        lang="en",
        locale="en-CA",
        path="/faq-scope/",
        title="TaxAgent scope, privacy, and filing limits",
        description="Understand what TaxAgent supports, what runs locally, and which filing and advisory boundaries apply.",
        nav_label="Primary navigation",
        skip_label="Skip to content",
        brand_note="Canadian and Quebec preparation preview",
        language_label="Language",
        footer_text="TaxAgent blocks unsupported preparation cases and keeps filing outside the project.",
        footer_links=f'<a href="{REPO_URL}">GitHub</a> | <a href="{DEV_README}">dev README</a> | <a href="{DEV_GUIDE}">user guide</a>',
        body="""
<section class="hero">
  <div>
    <p class="eyebrow">FAQ and scope</p>
    <h1>Know the limits first.</h1>
    <p class="lede">TaxAgent is a preview preparation tool, not certified filing software. The local calculation workflow is separate from older advisory commands that can contact a configured external model endpoint.</p>
  </div>
  <aside class="hero-card" aria-label="Fast answers">
    <dl>
      <div><dt>Does it file?</dt><dd>No. It does not submit returns or create NETFILE, ReFILE, or NetFile Quebec submission files.</dd></div>
      <div><dt>Does calculation call AI?</dt><dd>No. PDF/OCR intake and deterministic calculation run locally.</dd></div>
      <div><dt>Is every case covered?</dt><dd>No. Unsupported facts block calculation.</dd></div>
    </dl>
  </aside>
</section>
<section class="band" id="current-scope">
  <div class="content-grid">
    <div><p class="eyebrow">Current scope</p><h2>Bounded coverage.</h2></div>
    <table class="scope-table">
      <tr><th>Years</th><td>Preview workspace for 2020 through 2025.</td></tr>
      <tr><th>Jurisdiction</th><td>Federal Canada and Quebec.</td></tr>
      <tr><th>Persona</th><td>Full-year Canadian and Quebec resident, Quebec province on December 31, single, no dependants, ordinary salary/student profile.</td></tr>
      <tr><th>Inputs</th><td>Supported boxes from local PDFs and stated facts, with review items for uncertainty.</td></tr>
      <tr><th>Output</th><td>Preparation JSON, result JSON, and text review packets for the user's review.</td></tr>
    </table>
  </div>
</section>
<section class="band alt" id="privacy">
  <div class="content-grid">
    <div><p class="eyebrow">Privacy</p><h2>Local preparation is separate from advisory calls.</h2></div>
    <div class="stack">
      <p>The local preparation app runs on loopback. PDF/OCR intake and return calculation do not contact CRA, Revenu Quebec, tax software accounts, or a language-model endpoint.</p>
      <p>Saved JSON, optional saved profiles, and text review packets are plaintext files on your computer. Original PDFs are not embedded in exported JSON.</p>
      <p>Ask or chat advisory commands are separate from local preparation. When used, they send prompts and relevant structured context to the configured external endpoint. Do not treat advisory behavior as part of local deterministic preparation.</p>
    </div>
  </div>
</section>
<section class="band" id="not-covered">
  <div class="content-grid">
    <div><p class="eyebrow">Unsupported examples</p><h2>Blocked instead of guessed.</h2></div>
    <ul class="pill-list">
      <li>self-employment</li><li>capital gains</li><li>rental income</li><li>foreign income</li><li>crypto</li><li>dependants</li><li>medical expenses</li><li>donations</li><li>employment expenses</li><li>immigration or emigration year</li>
    </ul>
  </div>
</section>
""",
    ),
    Page(
        key="overview",
        lang="fr",
        locale="fr-CA",
        path="/fr/",
        title="TaxAgent Canada - préparation fiscale à code source ouvert",
        description="Évaluer TaxAgent Canada, un aperçu de préparation locale ouverte pour des flux fiscaux canadiens et québécois délimités.",
        nav_label="Navigation principale",
        skip_label="Aller au contenu",
        brand_note="Aperçu de préparation Canada et Québec",
        language_label="Langue",
        footer_text="TaxAgent Canada est un projet en aperçu. Il prépare des résultats à réviser; il ne transmet pas de déclarations et ne donne pas de conseils certifiés.",
        footer_links=f'<a href="{REPO_URL}">GitHub</a> | <a href="{DEV_README}">README dev (en anglais)</a> | <a href="{DEV_GUIDE}">guide utilisateur (en anglais)</a>',
        body="""
<section class="hero">
  <div>
    <p class="eyebrow">Projet fiscal à code source ouvert</p>
    <h1>TaxAgent Canada</h1>
    <p class="lede">Un espace local d'importation de PDF et de préparation de déclarations pour évaluer un flux canadien et québécois délimité, axé sur un profil salarié/étudiant. La source exécutable est disponible sur <code>dev</code>; la portée décrite ici est fondée sur la révision documentée <a href="https://github.com/K-kiron/TaxAgent/blob/a40a171/docs/coverage.md">a40a171</a>.</p>
  </div>
  <aside class="hero-card" aria-label="Faits sur le projet">
    <dl>
      <div><dt>Statut</dt><dd>La source de l'aperçu de développement est disponible sur <code>dev</code>.</dd></div>
      <div><dt>Préparation</dt><dd>L'importation PDF/OCR et le calcul déterministe s'exécutent localement sur votre ordinateur.</dd></div>
      <div><dt>Limite</dt><dd>Aucune connexion ARC ou Revenu Québec, aucune transmission, aucun conseil certifié.</dd></div>
    </dl>
  </aside>
</section>
<section class="band" id="evaluer">
  <div class="content-grid">
    <div><p class="eyebrow">Évaluer</p><h2>Lire la portée avant d'essayer.</h2></div>
    <div class="stack">
      <p>TaxAgent vise les évaluateurs techniques, les contributeurs et les réviseurs qui veulent une logique de préparation fiscale canadienne visible dans le code, avec une attention particulière au Québec.</p>
      <p>L'aperçu utile importe des relevés PDF pris en charge, demande les faits manquants, bloque les cas non pris en charge, calcule les lignes couvertes et exporte des fichiers JSON ou texte pour révision.</p>
      <div class="callout">Utilisez un logiciel certifié ou une voie autorisée pour transmettre une déclaration. Les sorties TaxAgent servent à la préparation et à la révision.</div>
      <p><a href="demarrage/">Essayer l'aperçu de développement</a>, suivre le <a href="parcours/">parcours synthétique</a> ou lire le <a href="portee-versionnee/">résumé de portée versionnée</a>.</p>
    </div>
  </div>
</section>
<section class="band alt" id="signaux">
  <div class="card-grid">
    <article class="card"><h3>Inspectable</h3><p>Source publique, licence Apache-2.0, calcul déterministe et liens exacts vers la documentation d'aperçu.</p></article>
    <article class="card"><h3>Préparation locale</h3><p>L'application de préparation fonctionne sur <code>127.0.0.1:8056</code>. L'importation PDF/OCR et le calcul ne nécessitent pas de point de terminaison de modèle.</p></article>
    <article class="card"><h3>Portée prudente</h3><p>Les faits non pris en charge bloquent le calcul au lieu d'être remplacés par des estimations générales.</p></article>
  </div>
</section>
""",
    ),
    Page(
        key="getting-started",
        lang="fr",
        locale="fr-CA",
        path="/fr/demarrage/",
        title="Démarrer avec l'aperçu de développement TaxAgent",
        description="Installer l'aperçu de développement TaxAgent depuis la branche dev et lancer l'espace local de préparation.",
        nav_label="Navigation principale",
        skip_label="Aller au contenu",
        brand_note="Aperçu de préparation Canada et Québec",
        language_label="Langue",
        footer_text="Les instructions d'aperçu indiquent la branche: clonez dev pour exécuter la source de développement documentée.",
        footer_links=f'<a href="{REPO_URL}">GitHub</a> | <a href="{DEV_README}">README dev (en anglais)</a> | <a href="{DEV_GUIDE}">guide utilisateur (en anglais)</a>',
        body="""
<section class="hero">
  <div>
    <p class="eyebrow">Démarrage</p>
    <h1>Lancer l'aperçu local.</h1>
    <p class="lede">Clonez explicitement la branche <code>dev</code>. La source de développement est la cible d'installation pour ce site d'aperçu.</p>
  </div>
  <aside class="hero-card" aria-label="Exigences de l'aperçu">
    <dl>
      <div><dt>Python</dt><dd>Python 3.11+</dd></div>
      <div><dt>Branche</dt><dd><code>dev</code> à la révision documentée <a href="https://github.com/K-kiron/TaxAgent/blob/a40a171/README.md">a40a171</a></dd></div>
      <div><dt>URL locale</dt><dd><code>http://127.0.0.1:8056</code></dd></div>
    </dl>
  </aside>
</section>
<section class="band" id="installer">
  <div class="content-grid">
    <div><p class="eyebrow">Installer</p><h2>Windows PowerShell</h2></div>
    <div class="stack">
      <pre><code>git clone --branch dev https://github.com/K-kiron/TaxAgent.git
cd TaxAgent
py -3.11 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install --upgrade pip
.\\.venv\\Scripts\\python.exe -m pip install ".[web]"
.\\.venv\\Scripts\\taxagent.exe doctor
.\\.venv\\Scripts\\taxagent.exe start</code></pre>
      <p>Ouvrez <code>http://127.0.0.1:8056</code>. L'espace de préparation est prévu pour une utilisation sur une adresse locale.</p>
    </div>
  </div>
</section>
<section class="band" id="installer-unix">
  <div class="content-grid">
    <div><p class="eyebrow">Installer</p><h2>Linux ou macOS</h2></div>
    <div class="stack">
      <pre><code>git clone --branch dev https://github.com/K-kiron/TaxAgent.git
cd TaxAgent
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ".[web]"
taxagent doctor
taxagent start</code></pre>
      <p>Ouvrez <code>http://127.0.0.1:8056</code>. Le flux de préparation local ne nécessite pas le point de terminaison de conseil.</p>
    </div>
  </div>
</section>
<section class="band alt" id="flux">
  <div class="content-grid">
    <div><p class="eyebrow">Flux</p><h2>Préparer, réviser, exporter.</h2></div>
    <ol class="steps">
      <li>Rassemblez vos relevés et dossiers d'émetteurs, de l'ARC et de Revenu Québec avant le calcul.</li>
      <li>Importez des relevés PDF locaux ou restaurez un espace TaxAgent JSON sauvegardé.</li>
      <li>Résolvez les éléments à réviser et les faits manquants qui bloquent le calcul.</li>
      <li>Calculez les années actives prêtes et lisez les blocages restants.</li>
      <li>Sauvegardez le JSON d'entrée, le JSON de résultat ou le paquet texte de révision.</li>
    </ol>
  </div>
</section>
<section class="band" id="docs">
  <div class="content-grid">
    <div><p class="eyebrow">Références</p><h2>Lire la documentation d'aperçu.</h2></div>
    <div class="stack">
      <p>Le README et le guide liés à la révision documentent l'aperçu actuel et ses limites; ces documents sont en anglais.</p>
      <p><a href="https://github.com/K-kiron/TaxAgent/blob/a40a171/README.md">README de développement à a40a171 (en anglais)</a></p>
      <p><a href="https://github.com/K-kiron/TaxAgent/blob/a40a171/docs/user/guide.md">Guide utilisateur de développement à a40a171 (en anglais)</a></p>
      <p><a href="https://github.com/K-kiron/TaxAgent/blob/dev/CONTRIBUTING.md">Guide de contribution sur dev (en anglais)</a></p>
    </div>
  </div>
</section>
""",
    ),
    Page(
        key="walkthrough",
        lang="fr",
        locale="fr-CA",
        path="/fr/parcours/",
        title="Parcours synthétique TaxAgent pour l'aperçu Québec 2025",
        description="Exécuter un exemple synthétique TaxAgent 2025 Québec et comparer la sortie déterministe.",
        nav_label="Navigation principale",
        skip_label="Aller au contenu",
        brand_note="Aperçu de préparation Canada et Québec",
        language_label="Langue",
        footer_text="Le parcours utilise seulement des faits synthétiques. N'utilisez pas de dossiers personnels dans les exemples publics.",
        footer_links=f'<a href="{REPO_URL}">GitHub</a> | <a href="{DEV_EXAMPLE}">exemple synthétique</a> | <a href="{DEV_CONTRIBUTING}">guide de contribution (en anglais)</a>',
        body="""
<section class="hero">
  <div>
    <p class="eyebrow">Parcours synthétique</p>
    <h1>Un paquet reproductible.</h1>
    <p class="lede">Ce parcours utilise un exemple salarial québécois synthétique pour 2025. Il ne contient aucun dossier personnel, aucun identifiant gouvernemental et aucun relevé réel.</p>
  </div>
  <aside class="hero-card" aria-label="Résultat attendu">
    <dl>
      <div><dt>Entrée</dt><dd><a href="https://github.com/K-kiron/TaxAgent/blob/dev/examples/synthetic_2025_qc_salary_student.json">synthetic_2025_qc_salary_student.json</a></dd></div>
      <div><dt>Résultat complet</dt><dd>Remboursement fédéral <code>2546.70</code>; remboursement Québec <code>863.84</code>.</dd></div>
      <div><dt>Variante non prise en charge</dt><dd>Définissez <code>taxpayer.has_self_employment</code> à <code>true</code>; le calcul bloque sans afficher de remboursement ni de solde.</dd></div>
    </dl>
  </aside>
</section>
<section class="band" id="executer">
  <div class="content-grid">
    <div><p class="eyebrow">Exécuter</p><h2>Calculer depuis JSON.</h2></div>
    <div class="stack">
      <p>Clonez <code>dev</code>, installez l'extra web local, puis exécutez la CLI publique sur l'entrée synthétique.</p>
      <pre><code># Windows PowerShell
.\\.venv\\Scripts\\taxagent.exe calculate examples\\synthetic_2025_qc_salary_student.json --output synthetic_result.json

# Linux ou macOS
taxagent calculate examples/synthetic_2025_qc_salary_student.json --output synthetic_result.json</code></pre>
      <p>L'exemple vérifié est un fichier JSON <code>TaxReturnInput</code> ordinaire. La CLI écrit un paquet de calcul déterministe et réussit seulement lorsque le statut est <code>complete</code>.</p>
    </div>
  </div>
</section>
<section class="band alt" id="sortie-attendue">
  <div class="content-grid">
    <div><p class="eyebrow">Sortie attendue</p><h2>Résultat actuel du moteur.</h2></div>
    <table class="scope-table">
      <tr><th>Statut</th><td><code>complete</code></td></tr>
      <tr><th>Profil de couverture</th><td><code>2025-qc-single-salaried-student-v1</code></td></tr>
      <tr><th>Fédéral</th><td>Remboursement de <code>2546.70</code></td></tr>
      <tr><th>Québec</th><td>Remboursement de <code>863.84</code></td></tr>
      <tr><th>Lignes</th><td>Au moins 600 lignes sur les déclarations et annexes fédérales et québécoises.</td></tr>
    </table>
  </div>
</section>
<section class="band" id="cas-bloque">
  <div class="content-grid">
    <div><p class="eyebrow">Cas bloqué</p><h2>Les faits non pris en charge restent visibles.</h2></div>
    <div class="stack">
      <p>Si la même entrée synthétique déclare du travail autonome, le test public attend un résultat bloqué avec le code <code>unsupported_situation</code> et le chemin d'entrée <code>taxpayer.has_self_employment</code>.</p>
      <p>Les résultats bloqués n'affichent pas de remboursement ni de solde fédéral ou québécois.</p>
    </div>
  </div>
</section>
""",
    ),
    Page(
        key="coverage",
        lang="fr",
        locale="fr-CA",
        path="/fr/portee-versionnee/",
        title="Portée versionnée TaxAgent pour l'aperçu Québec",
        description="Lire la portée versionnée de préparation TaxAgent Québec et fédérale, les entrées prises en charge et les exclusions explicites.",
        nav_label="Navigation principale",
        skip_label="Aller au contenu",
        brand_note="Aperçu de préparation Canada et Québec",
        language_label="Langue",
        footer_text="La portée décrit le code source et la documentation; ce n'est pas une certification ni une autorisation de transmission.",
        footer_links=f'<a href="{REPO_URL}">GitHub</a> | <a href="{DEV_COVERAGE}">portée à a40a171 (en anglais)</a> | <a href="{DEV_CONTRIBUTING}">guide de contribution (en anglais)</a>',
        body="""
<section class="hero">
  <div>
    <p class="eyebrow">Portée versionnée</p>
    <h1>Ce que couvre l'aperçu.</h1>
    <p class="lede">Ce résumé est fondé sur la documentation de développement à la révision <a href="https://github.com/K-kiron/TaxAgent/blob/a40a171/docs/coverage.md">a40a171</a>. Des changements de développement plus récents peuvent ajuster les entrées prises en charge, les blocages ou l'ensemble des lignes calculées.</p>
  </div>
  <aside class="hero-card" aria-label="Faits de couverture">
    <dl>
      <div><dt>Années de l'espace</dt><dd>Espace local de préparation pour 2020 à 2025.</dd></div>
      <div><dt>Matrice détaillée</dt><dd>Couverture ligne par ligne Québec/fédéral 2025 pour le profil délimité pris en charge.</dd></div>
      <div><dt>Contribution</dt><dd><a href="https://github.com/K-kiron/TaxAgent/blob/dev/CONTRIBUTING.md">CONTRIBUTING.md sur dev</a> (en anglais).</dd></div>
    </dl>
  </aside>
</section>
<section class="band" id="profil-pris-en-charge">
  <div class="content-grid">
    <div><p class="eyebrow">Profil pris en charge</p><h2>Réponses explicites requises.</h2></div>
    <div class="stack">
      <p>Le profil documenté du calculateur 2025 est la résidence canadienne et québécoise toute l'année, la province du Québec au 31 décembre, le statut célibataire, aucune personne à charge et une situation québécoise ordinaire de salarié/étudiant.</p>
      <p>Le calcul exige la confirmation des sources de revenu, des déductions, des crédits, des dossiers de l'ARC et de Revenu Québec, des écrans de situations non prises en charge, des acomptes provisionnels, des mois d'assurance médicaments, des questions de scolarité et des faits de crédits pris en charge.</p>
    </div>
  </div>
</section>
<section class="band alt" id="entrees-prises-en-charge">
  <div class="content-grid">
    <div><p class="eyebrow">Entrées</p><h2>Familles de relevés prises en charge.</h2></div>
    <ul class="pill-list">
      <li>T4 emploi Québec</li><li>RL-1 emploi Québec</li><li>T4A bourses et PAE de REEE pris en charge</li><li>T5 case 13 intérêts</li><li>RL-3 case D intérêts</li><li>T2202 scolarité</li><li>Reçus REER</li><li>RC210 et RL-19 pour certaines avances</li>
    </ul>
  </div>
</section>
<section class="band" id="exclusions-bloquees">
  <div class="content-grid">
    <div><p class="eyebrow">Exclusions</p><h2>Bloqué au lieu d'être estimé.</h2></div>
    <div class="stack">
      <p>Les exclusions documentées comprennent la résidence hors Québec ou une partie de l'année, les statuts autres que célibataire, les personnes à charge, les déclarations de personne décédée ou en faillite, le travail autonome, les gains en capital, les revenus de location, les revenus ou impôts étrangers, les biens étrangers de plus de 100 000 $, les cryptoactifs, les revenus de pension ou de prestations, les revenus exonérés selon la Loi sur les Indiens, les crédits pour personne handicapée ou aidant naturel, les dépenses d'emploi, les frais médicaux, les dons, les frais de garde, les frais de déménagement et les pourboires ou autres revenus d'emploi hors des cases de relevés prises en charge.</p>
      <p>La transmission reste séparée. TaxAgent ne soumet pas de déclarations, ne crée pas de fichiers prêts pour NETFILE/ReFILE/ImpôtNet Québec et ne demande pas d'identifiants gouvernementaux.</p>
    </div>
  </div>
</section>
""",
    ),
    Page(
        key="faq-scope",
        lang="fr",
        locale="fr-CA",
        path="/fr/faq-portee/",
        title="Portée, confidentialité et limites de transmission de TaxAgent",
        description="Comprendre ce que TaxAgent prend en charge, ce qui s'exécute localement et les limites de transmission et de conseil.",
        nav_label="Navigation principale",
        skip_label="Aller au contenu",
        brand_note="Aperçu de préparation Canada et Québec",
        language_label="Langue",
        footer_text="TaxAgent bloque les cas non pris en charge et garde la transmission en dehors du projet.",
        footer_links=f'<a href="{REPO_URL}">GitHub</a> | <a href="{DEV_README}">README dev (en anglais)</a> | <a href="{DEV_GUIDE}">guide utilisateur (en anglais)</a>',
        body="""
<section class="hero">
  <div>
    <p class="eyebrow">FAQ et portée</p>
    <h1>Comprendre les limites.</h1>
    <p class="lede">TaxAgent est un outil de préparation en aperçu, pas un logiciel de transmission certifié. Le flux de calcul local est distinct des anciennes commandes de conseil qui peuvent contacter un point de terminaison de modèle configuré.</p>
  </div>
  <aside class="hero-card" aria-label="Réponses rapides">
    <dl>
      <div><dt>Transmet-il?</dt><dd>Non. Il ne soumet pas de déclarations et ne crée pas de fichiers NETFILE, ReFILE ou ImpôtNet Québec.</dd></div>
      <div><dt>Le calcul appelle-t-il l'IA?</dt><dd>Non. L'importation PDF/OCR et le calcul déterministe s'exécutent localement.</dd></div>
      <div><dt>Tous les cas sont-ils couverts?</dt><dd>Non. Les faits non pris en charge bloquent le calcul.</dd></div>
    </dl>
  </aside>
</section>
<section class="band" id="portee-actuelle">
  <div class="content-grid">
    <div><p class="eyebrow">Portée actuelle</p><h2>Couverture délimitée.</h2></div>
    <table class="scope-table">
      <tr><th>Années</th><td>Espace d'aperçu pour 2020 à 2025.</td></tr>
      <tr><th>Juridiction</th><td>Fédéral Canada et Québec.</td></tr>
      <tr><th>Profil</th><td>Résident canadien et québécois toute l'année, province du Québec au 31 décembre, célibataire, sans personnes à charge, profil salarié/étudiant ordinaire.</td></tr>
      <tr><th>Entrées</th><td>Cases prises en charge à partir de PDF locaux et de faits déclarés, avec révision en cas d'incertitude.</td></tr>
      <tr><th>Sorties</th><td>JSON de préparation, JSON de résultat et paquets texte pour révision par l'utilisateur.</td></tr>
    </table>
  </div>
</section>
<section class="band alt" id="confidentialite">
  <div class="content-grid">
    <div><p class="eyebrow">Confidentialité</p><h2>La préparation locale est séparée des appels de conseil.</h2></div>
    <div class="stack">
      <p>L'application de préparation locale fonctionne sur une adresse locale. L'importation PDF/OCR et le calcul de déclaration ne contactent pas l'ARC, Revenu Québec, des comptes de logiciel fiscal ou un point de terminaison de modèle de langage.</p>
      <p>Les fichiers JSON, les profils sauvegardés facultatifs et les paquets texte sauvegardés sont des fichiers en texte clair sur votre ordinateur. Les PDF originaux ne sont pas intégrés au JSON exporté.</p>
      <p>Les commandes de questions ou de clavardage-conseil sont séparées de la préparation locale. Lorsqu'elles sont utilisées, elles envoient les prompts et le contexte structuré pertinent au point de terminaison externe configuré. Ne les confondez pas avec la préparation déterministe locale.</p>
    </div>
  </div>
</section>
<section class="band" id="non-couvert">
  <div class="content-grid">
    <div><p class="eyebrow">Exemples non couverts</p><h2>Bloqué au lieu d'être deviné.</h2></div>
    <ul class="pill-list">
      <li>travail autonome</li><li>gains en capital</li><li>revenus de location</li><li>revenus étrangers</li><li>cryptoactifs</li><li>personnes à charge</li><li>frais médicaux</li><li>dons</li><li>dépenses d'emploi</li><li>immigration ou émigration pendant l'année</li>
    </ul>
  </div>
</section>
""",
    ),
]


PAIRS = {
    ("overview", "en"): ("overview", "fr"),
    ("getting-started", "en"): ("getting-started", "fr"),
    ("walkthrough", "en"): ("walkthrough", "fr"),
    ("coverage", "en"): ("coverage", "fr"),
    ("faq-scope", "en"): ("faq-scope", "fr"),
    ("overview", "fr"): ("overview", "en"),
    ("getting-started", "fr"): ("getting-started", "en"),
    ("walkthrough", "fr"): ("walkthrough", "en"),
    ("coverage", "fr"): ("coverage", "en"),
    ("faq-scope", "fr"): ("faq-scope", "en"),
}


def clean_url(url: str) -> str:
    validate_url_text(url, "--base-url")
    parsed = urlparse(url)
    validate_parsed_url(parsed, "--base-url")
    if parsed.scheme != "https":
        raise ValueError("--base-url must be an absolute HTTPS URL for production builds")
    base_path = parsed.path.rstrip("/")
    return f"https://{parsed.netloc}{base_path}"


def preview_url(url: str) -> str:
    validate_url_text(url, "--preview-url")
    parsed = urlparse(url)
    validate_parsed_url(parsed, "--preview-url")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("--preview-url must be an absolute HTTP(S) URL")
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("--preview-url must use localhost, 127.0.0.1, or ::1")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"


def validate_url_text(url: str, flag: str) -> None:
    if not url or url != url.strip() or any(ch in url for ch in " \t\r\n\"'<>"):
        raise ValueError(f"{flag} contains malformed URL characters")


def validate_parsed_url(parsed, flag: str) -> None:
    if not parsed.netloc:
        raise ValueError(f"{flag} must include a host")
    if parsed.username or parsed.password:
        raise ValueError(f"{flag} must not include credentials")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError(f"{flag} includes an invalid port") from exc
    if parsed.query or parsed.fragment:
        raise ValueError(f"{flag} must not include a query string or fragment")
    for segment in unquote(parsed.path).split("/"):
        if segment in {".", ".."}:
            raise ValueError(f"{flag} must not include dot-segment paths")


def attr(value: str) -> str:
    return html.escape(value, quote=True)


def page_url(base_url: str, page: Page) -> str:
    if page.path == "/":
        return base_url + "/"
    return base_url + page.path


def output_path(out_dir: Path, page: Page) -> Path:
    if page.path == "/":
        return out_dir / "index.html"
    return out_dir / page.path.strip("/") / "index.html"


def rel_asset_prefix(page: Page) -> str:
    depth = 0 if page.path == "/" else len([part for part in page.path.strip("/").split("/") if part])
    return "" if depth == 0 else "../" * depth


def nav_for(page: Page) -> str:
    labels = {
        "en": [
            ("Overview", "/"),
            ("Getting started", "/getting-started/"),
            ("Walkthrough", "/walkthrough/"),
            ("Coverage", "/coverage/"),
            ("FAQ and scope", "/faq-scope/"),
        ],
        "fr": [
            ("Aperçu", "/fr/"),
            ("Démarrage", "/fr/demarrage/"),
            ("Parcours", "/fr/parcours/"),
            ("Portée", "/fr/portee-versionnee/"),
            ("FAQ et portée", "/fr/faq-portee/"),
        ],
    }[page.lang]
    parts = []
    for label, href in labels:
        current = ' aria-current="page"' if href == page.path else ""
        parts.append(f'<a href="{relative_href(page.path, href)}"{current}>{html.escape(label)}</a>')
    return "\n      ".join(parts)


def language_links(page: Page) -> str:
    pair_key = PAIRS[(page.key, page.lang)]
    pair = next(candidate for candidate in PAGES if (candidate.key, candidate.lang) == pair_key)
    current_label = "English" if page.lang == "en" else "Français"
    other_label = "Français" if page.lang == "en" else "English"
    return (
        f'<a href="{relative_href(page.path, page.path)}" aria-current="page">{current_label}</a>\n'
        f'      <a href="{relative_href(page.path, pair.path)}">{other_label}</a>'
    )


def relative_href(from_path: str, to_path: str) -> str:
    if from_path == to_path:
        return "./"
    from_parts = [] if from_path == "/" else [part for part in from_path.strip("/").split("/") if part]
    to_parts = [] if to_path == "/" else [part for part in to_path.strip("/").split("/") if part]
    common = 0
    for left, right in zip(from_parts, to_parts):
        if left != right:
            break
        common += 1
    up = [".."] * (len(from_parts) - common)
    down = to_parts[common:]
    rel_parts = up + down
    if not rel_parts:
        return "./"
    return "/".join(rel_parts) + "/"


def render_page(page: Page, base_url: str, robots: str) -> str:
    alternates = []
    same_key_pages = [candidate for candidate in PAGES if candidate.key == page.key]
    for candidate in sorted(same_key_pages, key=lambda item: item.locale):
        alternates.append(
            f'<link rel="alternate" hreflang="{candidate.locale}" href="{attr(page_url(base_url, candidate))}">'
        )
    english = next(candidate for candidate in same_key_pages if candidate.lang == "en")
    alternates.append(f'<link rel="alternate" hreflang="x-default" href="{attr(page_url(base_url, english))}">')
    source_code = {
        "@context": "https://schema.org",
        "@type": "SoftwareSourceCode",
        "name": "TaxAgent Canada",
        "codeRepository": REPO_URL,
        "license": f"{REPO_URL}/blob/main/LICENSE",
        "programmingLanguage": "Python",
        "description": "Open-source Canadian and Quebec tax preparation preview with local PDF intake and scoped deterministic calculation.",
    }
    values = {
        "lang": page.locale,
        "title": html.escape(page.title),
        "description": html.escape(page.description),
        "robots": robots,
        "canonical": attr(page_url(base_url, page)),
        "alternates": "\n  ".join(alternates),
        "og_image": attr(base_url + "/assets/taxagent-logo.png"),
        "asset_prefix": rel_asset_prefix(page),
        "json_ld": json.dumps(source_code, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c"),
        "skip_label": html.escape(page.skip_label),
        "home_href": relative_href(page.path, "/" if page.lang == "en" else "/fr/"),
        "brand_note": html.escape(page.brand_note),
        "nav_label": html.escape(page.nav_label),
        "nav_links": nav_for(page),
        "language_label": html.escape(page.language_label),
        "language_links": language_links(page),
        "body": page.body,
        "footer_text": html.escape(page.footer_text),
        "footer_links": page.footer_links,
    }
    html_doc = TEMPLATE
    for key, value in values.items():
        html_doc = html_doc.replace("{{ " + key + " }}", value)
    return html_doc


def write_sitemap(out_dir: Path, base_url: str) -> None:
    ns = "http://www.sitemaps.org/schemas/sitemap/0.9"
    ElementTree.register_namespace("", ns)
    root = ElementTree.Element(f"{{{ns}}}urlset")
    for page in PAGES:
        url = ElementTree.SubElement(root, f"{{{ns}}}url")
        loc = ElementTree.SubElement(url, f"{{{ns}}}loc")
        loc.text = page_url(base_url, page)
    tree = ElementTree.ElementTree(root)
    tree.write(out_dir / "sitemap.xml", encoding="utf-8", xml_declaration=True)


def expected_outputs(out_dir: Path) -> set[Path]:
    files = {out_dir / "assets" / "taxagent-logo.png", out_dir / "assets" / "site.css", out_dir / "sitemap.xml", out_dir / MARKER}
    files.update(output_path(out_dir, page) for page in PAGES)
    return {path.resolve() for path in files}


def read_marker(out_dir: Path) -> set[Path] | None:
    marker = out_dir / MARKER
    if not marker.exists():
        return None
    data = json.loads(marker.read_text(encoding="utf-8"))
    if data.get("builder") != "taxagent-static-site":
        raise ValueError(f"output marker is not a TaxAgent static-site marker: {marker}")
    return {(out_dir / rel).resolve() for rel in data.get("files", [])}


def rel_files(out_dir: Path, files: set[Path]) -> list[str]:
    return sorted(path.relative_to(out_dir.resolve()).as_posix() for path in files)


def is_reparse_point(path: Path) -> bool:
    try:
        mode = path.lstat().st_file_attributes
    except AttributeError:
        return path.is_symlink()
    except OSError:
        return False
    return bool(mode & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def absolute_unresolved(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def reject_reparse_path(path: Path) -> None:
    absolute = absolute_unresolved(path)
    parts = [absolute]
    parts.extend(absolute.parents)
    for candidate in reversed(parts):
        if candidate.exists() and (candidate.is_symlink() or is_reparse_point(candidate)):
            raise ValueError(f"refusing to write through symlink or reparse point: {candidate}")


def reject_reparse_descendants(out_dir: Path) -> None:
    for candidate in out_dir.rglob("*"):
        if candidate.is_symlink() or is_reparse_point(candidate):
            raise ValueError(f"refusing to write output with symlink or reparse descendant: {candidate}")


def prepare_output_dir(out_dir: Path) -> None:
    reject_reparse_path(out_dir)
    if not out_dir.exists():
        out_dir.mkdir(parents=True)
        return
    if not out_dir.is_dir():
        raise ValueError(f"output path exists and is not a directory: {out_dir}")
    out_root = out_dir.resolve()
    previous = read_marker(out_dir)
    actual = {path.resolve() for path in out_dir.rglob("*") if path.is_file()}
    reject_reparse_descendants(out_dir)
    if previous is None:
        if actual:
            names = ", ".join(rel_files(out_dir, actual))
            raise ValueError(f"refusing to reuse nonempty unmarked output directory: {names}")
        return
    for path in previous:
        resolved = path.resolve()
        if out_root not in resolved.parents and resolved != out_root:
            raise ValueError(f"refusing to trust marked file outside output directory: {path}")


def write_marker(out_dir: Path) -> None:
    files = expected_outputs(out_dir) - {(out_dir / MARKER).resolve()}
    marker = {
        "builder": "taxagent-static-site",
        "files": rel_files(out_dir, files),
    }
    (out_dir / MARKER).write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8", newline="\n")


def build(out_dir: Path, base_url: str, preview: bool) -> None:
    prepare_output_dir(out_dir)
    assets = out_dir / "assets"
    assets.mkdir(exist_ok=True)
    shutil.copy2(REPO_ROOT / "assets" / "taxagent-logo.png", assets / "taxagent-logo.png")
    shutil.copy2(ROOT / "assets" / "site.css", assets / "site.css")
    robots = "noindex, nofollow" if preview else "index, follow"
    for page in PAGES:
        target = output_path(out_dir, page)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_page(page, base_url, robots), encoding="utf-8", newline="\n")
    write_sitemap(out_dir, base_url)
    write_marker(out_dir)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ROOT / "dist"), help="Output directory")
    parser.add_argument("--base-url", help="Production HTTPS base URL, for example https://k-kiron.github.io/TaxAgent")
    parser.add_argument("--preview", action="store_true", help="Build a loopback preview with noindex metadata")
    parser.add_argument("--preview-url", default="http://127.0.0.1:8000", help="Absolute preview URL used when --preview is set")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        base_url = preview_url(args.preview_url) if args.preview else clean_url(args.base_url or "")
        build(absolute_unresolved(Path(args.out)), base_url, args.preview)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

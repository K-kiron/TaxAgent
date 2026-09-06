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
    <p class="lede">A local PDF intake and return-preparation workspace for reviewers evaluating a bounded Canadian and Quebec salary/student workflow. The runnable preview is on the development branch while release PR #6 remains under review.</p>
  </div>
  <aside class="hero-card" aria-label="Project facts">
    <dl>
      <div><dt>Status</dt><dd>Preview code on <code>dev</code>; default <code>main</code> is a public landing branch.</dd></div>
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
      <p><a href="getting-started/">Try the development preview</a> or read the <a href="faq-scope/">scope and privacy FAQ</a>.</p>
    </div>
  </div>
</section>
<section class="band alt" id="signals">
  <div class="card-grid">
    <article class="card"><h3>Inspectable</h3><p>Public source, Apache-2.0 license, deterministic calculation boundaries, and exact preview documentation links.</p></article>
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
        footer_text="Preview instructions are branch-aware because the runnable workspace is not yet released on main.",
        footer_links=f'<a href="{REPO_URL}">GitHub</a> | <a href="{DEV_README}">dev README</a> | <a href="{DEV_GUIDE}">user guide</a>',
        body="""
<section class="hero">
  <div>
    <p class="eyebrow">Getting started</p>
    <h1>Run the local preview.</h1>
    <p class="lede">Clone the <code>dev</code> branch explicitly. The inherited README and guide text may mention earlier branches while release PR #6 is pending; this page treats the current <code>dev</code> preview as the install target.</p>
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
    <p class="lede">Un espace local d'importation de PDF et de préparation de déclarations pour évaluer un flux canadien et québécois délimité, axé sur un profil salarié/étudiant. L'aperçu exécutable se trouve sur la branche de développement pendant que la PR #6 reste en révision.</p>
  </div>
  <aside class="hero-card" aria-label="Faits sur le projet">
    <dl>
      <div><dt>Statut</dt><dd>Code d'aperçu sur <code>dev</code>; la branche <code>main</code> sert de page publique.</dd></div>
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
      <p><a href="demarrage/">Essayer l'aperçu de développement</a> ou lire la <a href="faq-portee/">FAQ sur la portée et la confidentialité</a>.</p>
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
        footer_text="Les instructions d'aperçu indiquent la branche, car l'espace exécutable n'est pas encore publié sur main.",
        footer_links=f'<a href="{REPO_URL}">GitHub</a> | <a href="{DEV_README}">README dev (en anglais)</a> | <a href="{DEV_GUIDE}">guide utilisateur (en anglais)</a>',
        body="""
<section class="hero">
  <div>
    <p class="eyebrow">Démarrage</p>
    <h1>Lancer l'aperçu local.</h1>
    <p class="lede">Clonez explicitement la branche <code>dev</code>. Le README ou le guide hérités peuvent mentionner des branches antérieures pendant que la PR #6 est en attente; cette page traite l'aperçu <code>dev</code> comme cible d'installation.</p>
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
      <p>L'application de préparation locale fonctionne sur loopback. L'importation PDF/OCR et le calcul de déclaration ne contactent pas l'ARC, Revenu Québec, des comptes de logiciel fiscal ou un point de terminaison de modèle de langage.</p>
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
    ("faq-scope", "en"): ("faq-scope", "fr"),
    ("overview", "fr"): ("overview", "en"),
    ("getting-started", "fr"): ("getting-started", "en"),
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
        "en": [("Overview", "/"), ("Getting started", "/getting-started/"), ("FAQ and scope", "/faq-scope/")],
        "fr": [("Aperçu", "/fr/"), ("Démarrage", "/fr/demarrage/"), ("FAQ et portée", "/fr/faq-portee/")],
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
    expected = expected_outputs(out_dir)
    previous = read_marker(out_dir)
    actual = {path.resolve() for path in out_dir.rglob("*") if path.is_file()}
    reject_reparse_descendants(out_dir)
    if previous is None:
        if actual:
            names = ", ".join(rel_files(out_dir, actual))
            raise ValueError(f"refusing to reuse nonempty unmarked output directory: {names}")
        return
    for path in previous - expected:
        resolved = path.resolve()
        if out_root not in resolved.parents and resolved != out_root:
            raise ValueError(f"refusing to remove file outside output directory: {path}")
        if resolved.exists() and resolved.is_file():
            resolved.unlink()
    for directory in sorted((path for path in out_dir.rglob("*") if path.is_dir()), key=lambda item: len(item.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass


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

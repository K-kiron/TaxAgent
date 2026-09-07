from __future__ import annotations

import importlib.util
import re
import shutil
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urldefrag, urljoin, urlparse
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("site_builder", ROOT / "build.py")
builder = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.attrs: list[tuple[str, dict[str, str]]] = []
        self.ids: set[str] = set()
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        self.attrs.append((tag, attr_map))
        if "id" in attr_map:
            self.ids.add(attr_map["id"])

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.text.append(data.strip())


class StaticSiteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="taxagent-site-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    def build(self, base_url: str = "https://k-kiron.github.io/TaxAgent", preview: bool = False) -> Path:
        out = self.tmp / ("preview" if preview else "dist")
        builder.build(out, base_url, preview)
        return out

    def html_files(self, out: Path) -> list[Path]:
        return sorted(path for path in out.rglob("index.html"))

    def parse(self, path: Path) -> LinkParser:
        parser = LinkParser()
        parser.feed(path.read_text(encoding="utf-8"))
        return parser

    def test_generates_six_readable_pages_and_assets(self) -> None:
        out = self.build()
        pages = self.html_files(out)
        self.assertEqual(10, len(pages))
        self.assertTrue((out / "assets" / "site.css").is_file())
        self.assertTrue((out / "assets" / "taxagent-logo.png").is_file())
        root_text = (out / "index.html").read_text(encoding="utf-8")
        self.assertIn("TaxAgent Canada", root_text)
        self.assertIn("git clone --branch dev", (out / "getting-started" / "index.html").read_text(encoding="utf-8"))
        self.assertIn("git clone --branch dev", (out / "fr" / "demarrage" / "index.html").read_text(encoding="utf-8"))
        self.assertIn("synthetic_2025_qc_salary_student.json", (out / "walkthrough" / "index.html").read_text(encoding="utf-8"))
        self.assertIn("synthetic_2025_qc_salary_student.json", (out / "fr" / "parcours" / "index.html").read_text(encoding="utf-8"))
        self.assertIn("CONTRIBUTING.md", (out / "coverage" / "index.html").read_text(encoding="utf-8"))
        self.assertIn("README dev (en anglais)", (out / "fr" / "index.html").read_text(encoding="utf-8"))
        self.assertFalse((out / "robots.txt").exists())

    def test_links_assets_and_fragments_resolve(self) -> None:
        out = self.build()
        for html_file in self.html_files(out):
            parser = self.parse(html_file)
            base = html_file.parent.as_uri() + "/"
            for tag, attrs in parser.attrs:
                url = attrs.get("href") if tag in {"a", "link"} else attrs.get("src")
                if not url or url.startswith(("http://", "https://", "mailto:")):
                    continue
                target_url, fragment = urldefrag(urljoin(base, url))
                parsed = urlparse(target_url)
                target_path = unquote(parsed.path)
                target = Path(target_path[1:] if re.match(r"^/[A-Za-z]:/", target_path) else target_path)
                if target.is_dir():
                    target = target / "index.html"
                self.assertTrue(target.exists(), f"{html_file}: missing {url}")
                if fragment and target.suffix == ".html":
                    self.assertIn(fragment, self.parse(target).ids, f"{html_file}: missing fragment {url}")

    def test_metadata_is_reciprocal_under_project_path(self) -> None:
        out = self.build("https://k-kiron.github.io/TaxAgent")
        expected = {
            "index.html": "https://k-kiron.github.io/TaxAgent/",
            "getting-started/index.html": "https://k-kiron.github.io/TaxAgent/getting-started/",
            "faq-scope/index.html": "https://k-kiron.github.io/TaxAgent/faq-scope/",
            "walkthrough/index.html": "https://k-kiron.github.io/TaxAgent/walkthrough/",
            "coverage/index.html": "https://k-kiron.github.io/TaxAgent/coverage/",
            "fr/index.html": "https://k-kiron.github.io/TaxAgent/fr/",
            "fr/demarrage/index.html": "https://k-kiron.github.io/TaxAgent/fr/demarrage/",
            "fr/parcours/index.html": "https://k-kiron.github.io/TaxAgent/fr/parcours/",
            "fr/portee-versionnee/index.html": "https://k-kiron.github.io/TaxAgent/fr/portee-versionnee/",
            "fr/faq-portee/index.html": "https://k-kiron.github.io/TaxAgent/fr/faq-portee/",
        }
        pairs = [
            ("index.html", "fr/index.html"),
            ("getting-started/index.html", "fr/demarrage/index.html"),
            ("walkthrough/index.html", "fr/parcours/index.html"),
            ("coverage/index.html", "fr/portee-versionnee/index.html"),
            ("faq-scope/index.html", "fr/faq-portee/index.html"),
        ]
        for rel, canonical in expected.items():
            text = (out / rel).read_text(encoding="utf-8")
            self.assertIn(f'<link rel="canonical" href="{canonical}">', text)
            self.assertIn('<link rel="alternate" hreflang="en-CA"', text)
            self.assertIn('<link rel="alternate" hreflang="fr-CA"', text)
            self.assertIn('<link rel="alternate" hreflang="x-default"', text)
            english, french = next(pair for pair in pairs if rel in pair)
            alternates = {
                attrs["hreflang"]: attrs["href"]
                for tag, attrs in self.parse(out / rel).attrs
                if tag == "link" and attrs.get("rel") == "alternate"
            }
            self.assertEqual({
                "en-CA": expected[english],
                "fr-CA": expected[french],
                "x-default": expected[english],
            }, alternates)
            script = re.search(r'<script type="application/ld\+json">(.*?)</script>', text, flags=re.S)
            self.assertIsNotNone(script)
            self.assertEqual("SoftwareSourceCode", builder.json.loads(script.group(1))["@type"])
            self.assertNotIn("AggregateRating", text)
            self.assertNotIn("Offer", text)
        sitemap = ElementTree.parse(out / "sitemap.xml")
        locs = [node.text for node in sitemap.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
        self.assertEqual(sorted(expected.values()), sorted(locs))

    def test_metadata_is_valid_under_root_domain(self) -> None:
        out = self.build("https://taxagent.example")
        text = (out / "fr" / "faq-portee" / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="https://taxagent.example/fr/faq-portee/"', text)
        self.assertNotIn("https://taxagent.example//", text)

    def test_preview_uses_noindex_and_loopback_urls(self) -> None:
        out = self.build("http://127.0.0.1:8000", preview=True)
        text = (out / "index.html").read_text(encoding="utf-8")
        self.assertIn('<meta name="robots" content="noindex, nofollow">', text)
        self.assertIn('href="http://127.0.0.1:8000/"', text)

    def test_rejects_invalid_production_urls(self) -> None:
        for url in [
            "",
            "http://example.com",
            "https://example.com/path?x=1",
            "https:///TaxAgent",
            "https://user:pass@example.com",
            "https://example.com:bad",
            "https://example.com/a/../b",
            "https://example.com/%2e/TaxAgent",
            " https://example.com",
            "https://example.com/<TaxAgent>",
        ]:
            with self.assertRaises(ValueError, msg=url):
                builder.clean_url(url)

    def test_preview_url_enforces_loopback(self) -> None:
        self.assertEqual("http://127.0.0.1:8000", builder.preview_url("http://127.0.0.1:8000"))
        self.assertEqual("http://localhost:8000/TaxAgent", builder.preview_url("http://localhost:8000/TaxAgent"))
        for url in ["http://example.com", "http://0.0.0.0:8000", "http://127.0.0.1:bad"]:
            with self.assertRaises(ValueError, msg=url):
                builder.preview_url(url)

    def test_output_guard_is_manifest_managed(self) -> None:
        out = self.build()
        marker = out / builder.MARKER
        data = builder.json.loads(marker.read_text(encoding="utf-8"))
        extra = out / "old" / "preserved.html"
        extra.parent.mkdir()
        extra.write_text("manual", encoding="utf-8")
        data["files"].append("old/preserved.html")
        marker.write_text(builder.json.dumps(data), encoding="utf-8")
        builder.build(out, "https://k-kiron.github.io/TaxAgent", False)
        self.assertTrue(extra.exists())
        self.assertEqual("manual", extra.read_text(encoding="utf-8"))

        unmarked = self.tmp / "manual"
        unmarked.mkdir()
        (unmarked / "notes.txt").write_text("do not touch", encoding="utf-8")
        with self.assertRaises(ValueError):
            builder.build(unmarked, "https://k-kiron.github.io/TaxAgent", False)

        unmarked_expected_name = self.tmp / "looks-generated"
        unmarked_expected_name.mkdir()
        (unmarked_expected_name / "index.html").write_text("manual", encoding="utf-8")
        with self.assertRaises(ValueError):
            builder.build(unmarked_expected_name, "https://k-kiron.github.io/TaxAgent", False)

    def test_copy_avoids_tax_advice_and_live_claims(self) -> None:
        out = self.build()
        corpus = "\n".join(path.read_text(encoding="utf-8") for path in self.html_files(out))
        forbidden_patterns = [
            r"certified tax software",
            r"files? your return",
            r"guaranteed refund",
            r"official government service",
            r"all data stays local",
            r"now live at https://k-kiron\.github\.io/TaxAgent",
            r"release PR #6",
            r"public landing branch",
        ]
        for pattern in forbidden_patterns:
            self.assertIsNone(re.search(pattern, corpus, flags=re.IGNORECASE), pattern)

    def test_public_copy_does_not_expose_commit_identifiers(self) -> None:
        out = self.build()
        corpus = "\n".join(path.read_text(encoding="utf-8") for path in self.html_files(out))
        self.assertIsNone(re.search(r"\b[0-9a-f]{7,40}\b", corpus, flags=re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()

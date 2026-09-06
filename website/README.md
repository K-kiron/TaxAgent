# TaxAgent Static Site

This folder builds the first static documentation slice for TaxAgent Canada. It is intentionally separate from the application runtime: no JavaScript runtime, analytics, forms, tax uploads, model calls, deployment automation, or crawler-training file is included.

The site has six crawlable pages:

- English: overview, getting started, FAQ and scope.
- French: aperçu, démarrage, questions fréquentes et portée.

## Preview Locally

Preview output defaults to `http://127.0.0.1:8000` and adds `noindex` metadata so a loopback or temporary preview is not mistaken for the production canonical site.

```bash
python website/build.py --preview --out website/preview
python -m http.server 8000 --bind 127.0.0.1 --directory website/preview
```

Open `http://127.0.0.1:8000/`.

## Build For Production

Set the canonical HTTPS base URL for the deployed location. For a GitHub Pages project site, include the repository path in the base URL:

```bash
python website/build.py --base-url https://k-kiron.github.io/TaxAgent --out website/dist
```

For a root domain, omit the project path:

```bash
python website/build.py --base-url https://taxagent.example --out website/dist
```

The builder derives canonical URLs, reciprocal `hreflang` links, Open Graph URLs, JSON-LD source-code metadata, and `sitemap.xml` from the configured base URL. It also copies the existing project logo into the generated output.

## Hosting Caveats

The production host must serve `website/dist` from the same path used in `--base-url`. Rebuild if the host or path changes, then spot-check the canonical URL, language links, logo, stylesheet, and sitemap in the deployed HTML.

This slice does not generate `/TaxAgent/robots.txt`. On GitHub Pages project sites, that path is not the origin-root `/robots.txt` and cannot control crawling for the host. Add an origin-root robots policy only when the final hosting surface makes that possible and the desired crawler policy is explicit.

## Tests

The tests build temporary root, project-subpath, preview, and invalid-URL outputs. They check page count, readable content, metadata reciprocity, sitemap URLs, internal links, fragment targets, assets, preview `noindex`, and URL validation.

```bash
python -m unittest discover -s website/tests
```

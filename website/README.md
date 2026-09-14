# TaxAgent Static Site

This folder builds the static documentation site for TaxAgent Canada. It is separate from the application runtime: no JavaScript runtime, analytics, forms, tax uploads, model calls, or crawler-training file is included in the generated site. A dedicated workflow publishes only the static output.

The site has ten crawlable pages:

- English: overview, getting started, synthetic walkthrough, versioned coverage, FAQ and scope.
- French: aperçu, démarrage, parcours synthétique, portée versionnée, questions fréquentes et portée.

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

## GitHub Pages Workflow

The repository includes a dedicated website workflow at `.github/workflows/website.yml`. It validates the static site with the Python standard library only:

```bash
python -m unittest discover -s website/tests
python website/build.py --base-url https://k-kiron.github.io/TaxAgent --out website/dist
```

Pull requests run tests and a production-shaped build only. They do not configure Pages, upload artifacts, or deploy previews.

Pages deployment runs only from the `dev` branch, either after a matching push or a manual `workflow_dispatch` run selected on `dev`. The workflow builds `website/dist` for `https://k-kiron.github.io/TaxAgent`, uploads only that generated directory as the standard Pages artifact, and deploys it through the `github-pages` environment.

The workflow permissions are intentionally narrow. The test job has repository read access only while it checks out source, runs Python, builds the static site, and uploads the generated Pages artifact on `dev`. The deploy job does not check out the repository or run Python; it adds only `pages: write` and `id-token: write` for `actions/deploy-pages`.

## Hosting Caveats

The production host must serve `website/dist` from the same path used in `--base-url`. The checked workflow currently builds for `https://k-kiron.github.io/TaxAgent`. If the Pages URL, custom domain, or path changes, update the workflow build command and this README, rebuild, and spot-check the canonical URL, language links, logo, stylesheet, and sitemap in the deployed HTML.

This slice does not generate `/TaxAgent/robots.txt`. On GitHub Pages project sites, that path is not the origin-root `/robots.txt` and cannot control crawling for the host. Add an origin-root robots policy only when the final hosting surface makes that possible and the desired crawler policy is explicit.

GitHub Pages must be configured to use GitHub Actions as the build and deployment source, and the `github-pages` environment should restrict deployments to the `dev` branch. A workflow file added on a non-default branch may not appear in the manual dispatch UI until the default branch includes that workflow; pushing to `dev` still triggers the branch-scoped deployment path.

After deployment, check the live page source for the canonical URL, reciprocal language links, `og:url`, `og:image`, stylesheet, logo, and `sitemap.xml`. The deployed artifact should contain only generated static files from `website/dist`, not repository source, tax fixtures, local profiles, or application runtime files.

To roll back, revert the problematic website change on `dev` and let the workflow redeploy the previous reviewed content. Do not force-push a rollback over reviewed history.

## Tests

The tests build temporary root, project-subpath, preview, and invalid-URL outputs. They check page count, readable content, metadata reciprocity, sitemap URLs, internal links, fragment targets, assets, preview `noindex`, and URL validation.

```bash
python -m unittest discover -s website/tests
```

# Discovery Measurement

This project measures public discovery with GitHub aggregate traffic only. It does not add tracking code, analytics pixels, telemetry, raw request logs, user identifiers, tax data collection, prompt upload collection, or document upload collection.

GitHub traffic endpoints report a rolling 14-day UTC window. Treat clones as aggregate repository clone events, not daily install counts, active users, successful setup, or tax workflow completion.

## Collect GitHub Aggregate Inputs

Run these commands manually as a repository maintainer with access to traffic insights:

```bash
mkdir -p ../taxagent-discovery-metrics/2026-09-06
gh api repos/K-kiron/TaxAgent/traffic/views > ../taxagent-discovery-metrics/2026-09-06/views.json
gh api repos/K-kiron/TaxAgent/traffic/clones > ../taxagent-discovery-metrics/2026-09-06/clones.json
gh api repos/K-kiron/TaxAgent/traffic/popular/referrers > ../taxagent-discovery-metrics/2026-09-06/referrers.json
gh api repos/K-kiron/TaxAgent/traffic/popular/paths > ../taxagent-discovery-metrics/2026-09-06/paths.json
python scripts/marketing/discovery_measurement.py \
  --repo K-kiron/TaxAgent \
  --views-json ../taxagent-discovery-metrics/2026-09-06/views.json \
  --clones-json ../taxagent-discovery-metrics/2026-09-06/clones.json \
  --referrers-json ../taxagent-discovery-metrics/2026-09-06/referrers.json \
  --paths-json ../taxagent-discovery-metrics/2026-09-06/paths.json \
  --output ../taxagent-discovery-metrics/2026-09-06/taxagent-discovery-snapshot.json
```

The snapshot preserves unavailable inputs as `available=false` with null counts. Reported zero counts remain numeric zero.

For referrers and popular paths, missing inputs or saved API errors produce `null`; a successful empty response remains `[]`. An unavailable optional endpoint does not discard valid views or clone counts.

## Minimal Outcome Definitions

- Views: GitHub aggregate repository page views in the traffic window.
- Unique visitors: GitHub aggregate unique visitors in the traffic window.
- Clones: GitHub aggregate clone events in the traffic window. Do not call them installs.
- Referrers: GitHub aggregate referring sites. Do not infer identity, geography, profession, or tax situation.
- Popular paths: GitHub aggregate viewed repository paths.
- Conversion signals: stars, issues, discussions, forks, and pull requests observed on GitHub. Treat them as engagement, not proof of tax correctness.

## Manual Search and Bing Follow-Up

Use search engines only for manual public discoverability checks. Do not automate scraping search-result pages and do not track individual users.

Suggested checks:

```text
TaxAgent Canada GitHub
TaxAgent Quebec tax GitHub
site:github.com/K-kiron/TaxAgent taxagent
site:github.com/K-kiron/TaxAgent Quebec
```

Record only aggregate observations in local notes outside the repository, such as whether the repository appears for a query on the collection date. Do not commit those notes unless they become durable maintainer documentation.

For GitHub Pages and search-console ownership, keep verification manual and maintainer-owned. Do not add verification files, meta tags, or DNS changes from this repository without an explicit maintainer decision.

## Successful Trial Start

Count a voluntary public trial as a successful start only when the tester reports all three aggregate steps:

- Install checks passed.
- The local browser UI opened.
- Synthetic data produced either a calculation output or an expected unsupported-case blocker.

Do not ask for tax data, documents, credentials, personal prompts, or screenshots to prove these steps.

## Bilingual Search Diagnostic

Run the same public-product question set in English and French, then record only aggregate local observations:

```text
English queries:
- TaxAgent Canada GitHub
- open source Quebec tax preparation prototype
- local Canadian tax preparation CLI GitHub

French queries:
- TaxAgent Canada GitHub
- prototype impôt Québec open source
- outil local déclaration revenus Québec GitHub
```

Local results table schema:

| Date | Engine | Language | Query | Cited URL | Result position or absent | Snippet accurate to scope? | Error vs absent | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

Use `Error vs absent` to distinguish browser/search failure from a real absence in visible results. Do not store personal prompts, signed-in personalization details, account identifiers, or raw result pages.

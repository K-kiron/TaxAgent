# TaxAgent MVP

A minimal, working slice of the harness in README_HARNESS.md: a question goes in,
a **grounded, structured `Recommendation`** comes out, and a two-layer eval grades it.

## What's here

```
src/taxagent/
  models.py            # Pydantic models (single source of truth)
  config.py            # endpoint / model / output-mode (all env-overridable)
  knowledge/           # rule-card store + naive retrieval
  agent/
    reasoner.py        # THE framework seam — Pydantic AI -> Recommendation (only LLM-touching file)
    session.py         # TaxSession — multi-turn: threaded history + accumulating fact store
    render.py          # Recommendation -> 8-part markdown (rendered, never hand-written)
  persistence.py       # UserProfile + AsyncProfileWriter (async, coalescing, atomic disk writes)
  web/                 # FastAPI chat app (app.py) + single-page UI (static/index.html)
  evals/
    schemas.py         # GoldenScenario (tax_year, maps_to_rule_cards, smoke_*, safety, ...)
    scenarios.py       # the 5 canonical golden scenarios (4 advisory + 1 adversarial refusal)
    graders.py         # Layer 1 structural (deterministic) + negation-aware smoke + safety gate
    run_evals.py       # runner
  cli.py               # taxagent ask | eval | rule-card
src/taxagent/data/knowledge_base/  # packaged JSON rule cards (source_type + last_verified)
tests/                 # unit graders/models + live serve smoke (auto-skips if serve down)
infra/                 # serve + stop scripts
```

## Framework choice

**Agent layer = Pydantic AI.** The whole harness is Pydantic-object-centric, so
`output_type=Recommendation` returns a validated object directly. Everything except
`agent/reasoner.py` is framework-agnostic — swapping to **LangGraph** later (when this
grows real multi-agent branching: jurisdiction sub-agents + verifier + LLM-judge) means
rewriting only that one file. See the framework comparison in the project notes.

## Run it

```bash
# 1. serve the model (Qwen3.6-35B-A3B, 35B/3B-active MoE) — low footprint
bash infra/serve_35b_mvp.sh          # TP=4 on GPUs 1-4, ~47% each, OpenAI API on :8011

# 2. use it (from the repo venv)
.venv/bin/taxagent ask "I interned in 2025 and don't know if I had group drug insurance. Should I answer Yes?"
.venv/bin/taxagent chat               # MULTI-TURN: follow-ups + accumulating fact store (:facts, :q)
.venv/bin/taxagent chat --user alice  # + PERSIST: profile async-saved to .profiles/alice.json
.venv/bin/taxagent profile show --user alice   # inspect a returning user's saved profile
.venv/bin/taxagent eval               # runs the 5 golden scenarios, prints the two-layer grade
.venv/bin/taxagent rule-card list --jurisdiction quebec

# tests
.venv/bin/python -m pytest -q         # unit (no LLM) + live serve smoke (skips if :8011 down)

# chat UI (web) - public static demo works even without the model serve
.venv/bin/pip install -e '.[web]'   # first time: installs fastapi + uvicorn
bash infra/run_ui.sh                 # -> http://127.0.0.1:8055

# optional private live demo: keep behind a PIN and tunnel only the UI port
TAXAGENT_DEMO_LIVE_ENABLED=1 TAXAGENT_DEMO_PIN='<temporary-pin>' bash infra/run_ui.sh
cloudflared tunnel --url http://127.0.0.1:8055   # never tunnel :8011

# stop the serve
bash infra/stop_serve.sh
```

Point at any OpenAI-compatible endpoint via env: `TAXAGENT_BASE_URL`, `TAXAGENT_MODEL`,
`TAXAGENT_OUTPUT_MODE` (`native`|`prompted`|`tool`), `TAXAGENT_TEMPERATURE`.
For public demos, see `docs/festival_demo_runbook.md`: keep vLLM on localhost,
avoid `TAXAGENT_UI_HOST=0.0.0.0`, and expose only `127.0.0.1:8055` through a
protected tunnel.

## Deliberately stubbed (next steps, per the harness design)

- **Layer-2 semantic judge (LLM-judge)** — not implemented. Correctness / grounding /
  uncertainty are currently checked only structurally + by a negation-aware smoke pre-filter
  and a heuristic safety gate. A smoke_exclude hit is a `WARN→judge` signal, never an
  auto-fail (substrings are a pre-filter, never the score).
- **Grounding is not yet falsifiable** — rule cards are real but small; the "cited card
  actually supports the claim" check needs the judge.
- **Fact extraction** is folded into the single reasoning call; no standalone extractor yet
  (facts do accumulate across turns via `TaxSession`, but from `facts_used`, not a dedicated pass).
- **Retrieval** is keyword-overlap, not embeddings.
- **Multi-turn + persistence** work (`TaxSession` / `taxagent chat --user`): history is threaded, a
  deduped fact store accumulates, and the per-user profile is written to disk **asynchronously**
  (background single-writer thread, coalesced bursts, atomic temp+rename, `flush()`/atexit so the last
  update is never lost). A returning user's profile loads before their first question.
  Not yet: a DB backend (JSON files only), history/context-window bounding, encryption-at-rest for PII,
  or a dedicated fact-extraction pass (facts come from `Recommendation.facts_used`).

## Notes / gotchas

- The nothink chat template requires the **system message first**; Pydantic AI's `prompted`
  mode appends a trailing system message and gets a 400. Use `native` output mode
  (`response_format: json_schema` → vLLM guided decoding) — reliable and keeps ordering valid.
  This is the default in `config.py`.
- `temperature=0` for reproducible tax reasoning. `facts_used` / `required_evidence` carry
  `min_length=1` so guided decoding guarantees the advisory contract is populated.

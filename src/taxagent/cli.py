"""taxagent CLI: ask / eval / rule-card / local return calculation."""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import importlib.util
import json
import os
from pathlib import Path
import sys
import urllib.request
from urllib.parse import urlsplit

from pydantic import ValidationError


START_APP = "taxagent.web.local_app:app"
DEFAULT_START_HOST = "127.0.0.1"
DEFAULT_START_PORT = 8056


def _default_profile_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") if os.name == "nt" else None
    if base:
        return Path(base) / "TaxAgent" / "profiles"
    return Path.home() / ".taxagent" / "profiles"


def _cmd_ask(args: argparse.Namespace) -> int:
    from .agent.reasoner import Reasoner
    from .agent.render import render_markdown

    rec, cards = Reasoner().answer(args.question, tax_year=args.tax_year)
    print(render_markdown(rec))
    if args.show_cards:
        print("\n[retrieved cards]", [c.id for c in cards])
    return 0


def _cmd_chat(args: argparse.Namespace) -> int:
    from .agent.render import render_markdown
    from .agent.session import TaxSession

    sess = TaxSession(default_tax_year=args.tax_year, user_id=args.user)
    who = f" (profile: {args.user})" if args.user else " (not persisted — pass --user to save)"
    print(f"TaxAgent chat{who} — ask follow-up questions freely.")
    if args.user and sess.known_facts:
        print(f"  loaded {len(sess.known_facts)} fact(s) from your saved profile.")
    print("  :facts  dump the accumulated fact store   |   :q  quit\n")
    try:
        while True:
            try:
                line = input("you> ").strip()
            except EOFError:
                break
            if not line:
                continue
            if line in (":q", ":quit", "exit"):
                break
            if line == ":facts":
                if not sess.known_facts:
                    print("  (no facts established yet)")
                for f in sess.known_facts:
                    print(f"  - {f.key}: {f.value}  [{f.evidence_status}]")
                continue
            rec = sess.ask(line)
            print("\n" + render_markdown(rec) + "\n")
    finally:
        sess.close()  # flush the async profile write before exit
    return 0


def _cmd_profile(args: argparse.Namespace) -> int:
    from .persistence import ProfileStore

    store = ProfileStore()
    p = store.path(args.user, tax_year=args.tax_year)
    profile = store.load(args.user, tax_year=args.tax_year)
    if not p.exists() and not profile.facts and profile.updated_at is None:
        print(f"no saved profile for {args.user!r} (looked in {p})")
        return 1
    print(f"profile {args.user}  tax_year={profile.tax_year}  updated={profile.updated_at}")
    print(f"file: {p}")
    for f in profile.facts.values():
        print(f"  - {f.key}: {f.value}  [{f.evidence_status}, confidence={f.confidence}]")
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    from .evals.run_evals import _print_report, run
    from .evals.scenarios import GOLDEN_SCENARIOS

    scenarios = GOLDEN_SCENARIOS
    if args.scenario:
        scenarios = [s for s in GOLDEN_SCENARIOS if s.scenario_id == args.scenario]
        if not scenarios:
            print(f"no scenario with id {args.scenario!r}", file=sys.stderr)
            return 2
    return _print_report(run(scenarios))


def _cmd_start(args: argparse.Namespace) -> int:
    if args.host not in {"127.0.0.1", "localhost"}:
        print(
            "Refusing to bind outside localhost; this release only supports local use.",
            file=sys.stderr,
        )
        return 2
    try:
        import uvicorn
    except ImportError:
        print("Missing web extra. Install with: python -m pip install .[web]", file=sys.stderr)
        return 1
    print(f"Starting TaxAgent local app at http://{args.host}:{args.port}")
    uvicorn.run(START_APP, host=args.host, port=args.port, reload=False)
    return 0


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _web_static_available() -> bool:
    from importlib import resources

    static = resources.files("taxagent").joinpath("web", "static")
    required_assets = ("local.html", "local.css", "local.js", "demo_scenarios.json")
    return static.is_dir() and all(static.joinpath(asset).is_file() for asset in required_assets)


def _safe_origin(url: str) -> str:
    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.hostname:
        return "configured endpoint"
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return f"{parsed.scheme}://{host}"


def _probe_live(settings) -> tuple[bool, str]:
    candidates = []
    if settings.base_url.endswith("/v1"):
        candidates.append(settings.base_url[:-3] + "/health")
    candidates.append(settings.base_url.rstrip("/") + "/models")
    headers = {}
    if settings.api_key and settings.api_key != "EMPTY":
        headers["Authorization"] = f"Bearer {settings.api_key}"
    for url in candidates:
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=3) as response:
                if response.status == 200:
                    return True, _safe_origin(url)
        except Exception:
            continue
    return False, _safe_origin(settings.base_url)


def _local_engine_available() -> bool:
    from .returns.engine import calculate_return
    from .returns.models import TaxReturnInput

    return callable(calculate_return) and TaxReturnInput.__name__ == "TaxReturnInput"


def _local_ui_available() -> bool:
    from importlib import resources

    return resources.files("taxagent").joinpath("web", "local_app.py").is_file() and _web_static_available()


def _pdf_intake_dependencies() -> list[str]:
    modules = {
        "pypdf": "pypdf",
        "pypdfium2": "pypdfium2",
        "rapidocr": "rapidocr",
        "onnxruntime": "onnxruntime",
        "cryptography": "cryptography",
    }
    return [label for label, module in modules.items() if not _has_module(module)]


def _cmd_doctor(args: argparse.Namespace) -> int:
    print("TaxAgent offline checks")
    failures: list[str] = []

    if sys.version_info < (3, 11):
        failures.append("Python 3.11 or newer is required")
    else:
        print(f"ok: Python {sys.version_info.major}.{sys.version_info.minor}")

    try:
        from .knowledge import load_default_store

        cards = load_default_store().cards
        print(f"ok: rule cards ({len(cards)})")
    except Exception as exc:
        failures.append(f"rule cards unavailable: {type(exc).__name__}: {exc}")

    if _web_static_available():
        print("ok: web static assets")
    else:
        failures.append("web static assets unavailable")

    missing_web = [name for name in ("fastapi", "uvicorn") if not _has_module(name)]
    if missing_web:
        failures.append("web extra missing (" + ", ".join(missing_web) + ")")
    else:
        print("ok: web extra")

    missing_pdf = _pdf_intake_dependencies()
    if missing_pdf:
        failures.append(
            "PDF intake dependency missing ("
            + ", ".join(missing_pdf)
            + "); reinstall the package with its default PDF dependencies"
        )
    else:
        print("ok: PDF intake dependencies")

    try:
        if _local_engine_available():
            print("ok: local engine")
    except Exception as exc:
        failures.append(f"local engine unavailable: {type(exc).__name__}: {exc}")

    try:
        if _local_ui_available():
            print("ok: local UI")
    except Exception as exc:
        failures.append(f"local UI unavailable: {type(exc).__name__}: {exc}")

    print(f"ok: profile storage is opt-in ({_default_profile_dir()})")

    if failures:
        for failure in failures:
            print(f"fail: {failure}", file=sys.stderr)
        return 1

    if args.live:
        try:
            from .config import settings as live_settings
        except ValueError as exc:
            print(f"fail: live configuration invalid: {exc}", file=sys.stderr)
            return 2
        ok, origin = _probe_live(live_settings)
        if ok:
            print(f"ok: live endpoint {origin}")
        else:
            print(f"fail: live endpoint unavailable at {origin}", file=sys.stderr)
            return 2

    return 0


def _same_file_path(first: Path, second: Path) -> bool:
    try:
        return first.resolve() == second.resolve()
    except OSError:
        return first.absolute() == second.absolute()


def _read_json_object(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"could not read input JSON: {type(exc).__name__}", file=sys.stderr)
        return None
    except (UnicodeDecodeError, json.JSONDecodeError):
        print("input is not valid UTF-8 JSON", file=sys.stderr)
        return None
    if not isinstance(payload, dict):
        print("input must be a TaxReturnInput JSON object", file=sys.stderr)
        return None
    return payload


def _decimalize_json_money(data):
    slips = []
    for slip in data.slips:
        fields = {}
        for box, value in slip.fields.items():
            if isinstance(value, str):
                try:
                    fields[box] = Decimal(value)
                    continue
                except InvalidOperation:
                    pass
            fields[box] = value
        slips.append(slip.model_copy(update={"fields": fields}))
    return data.model_copy(update={"slips": slips})


def _write_text_atomic(path: Path, text: str, *, force: bool) -> bool:
    if path.exists() and not force:
        print(f"output already exists: {path}; pass --force to overwrite", file=sys.stderr)
        return False
    tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(text, encoding="utf-8")
        os.replace(tmp_path, path)
    except OSError as exc:
        print(f"could not write output JSON: {type(exc).__name__}", file=sys.stderr)
        try:
            tmp_path.unlink()
        except OSError:
            pass
        return False
    return True


def _cmd_calculate(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output_path = Path(args.output)
    if _same_file_path(input_path, output_path):
        print("input and output paths must be different", file=sys.stderr)
        return 1
    if not input_path.exists():
        print(f"input file not found: {input_path}", file=sys.stderr)
        return 1
    if output_path.exists() and not args.force:
        print(f"output already exists: {output_path}; pass --force to overwrite", file=sys.stderr)
        return 1

    payload = _read_json_object(input_path)
    if payload is None:
        return 1

    try:
        from .returns.engine import calculate_return
        from .returns.models import TaxReturnInput
    except ImportError:
        print(
            "deterministic return engine is unavailable; calculation packet was not written",
            file=sys.stderr,
        )
        return 2

    try:
        data = _decimalize_json_money(TaxReturnInput.model_validate(payload))
    except ValidationError as exc:
        paths = sorted({".".join(str(part) for part in err["loc"]) for err in exc.errors()})
        location_hint = ", ".join(paths[:8]) if paths else "input"
        print(
            f"input does not match TaxReturnInput schema; check: {location_hint}",
            file=sys.stderr,
        )
        return 1

    result = calculate_return(data)
    if not _write_text_atomic(output_path, result.model_dump_json(indent=2), force=args.force):
        return 1
    print(f"wrote {output_path}")
    return 0 if result.status == "complete" else 2


def _cmd_rule_card(args: argparse.Namespace) -> int:
    from .knowledge import load_default_store

    store = load_default_store()
    for c in store.cards:
        if args.jurisdiction and c.jurisdiction != args.jurisdiction:
            continue
        print(f"{c.id}  [{c.jurisdiction}/{c.source_type}]  ty={c.tax_year}  - {c.topic}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="taxagent", description="TaxAgent Canada local return tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    ask = sub.add_parser("ask", help="answer a natural-language tax question")
    ask.add_argument("question")
    ask.add_argument("--tax-year", type=int, default=None)
    ask.add_argument("--show-cards", action="store_true")
    ask.set_defaults(func=_cmd_ask)

    ch = sub.add_parser("chat", help="multi-turn conversation with an accumulating fact store")
    ch.add_argument("--tax-year", type=int, default=None)
    ch.add_argument("--user", default=None, help="user id to persist a profile under")
    ch.set_defaults(func=_cmd_chat)

    pr = sub.add_parser("profile", help="inspect a persisted user profile")
    pr.add_argument("action", choices=["show"], nargs="?", default="show")
    pr.add_argument("--user", required=True)
    pr.add_argument("--tax-year", type=int, default=None, help="inspect a year-specific profile")
    pr.set_defaults(func=_cmd_profile)

    ev = sub.add_parser("eval", help="run golden scenario evals")
    ev.add_argument("--scenario", default=None, help="run a single scenario by id")
    ev.add_argument("--all", action="store_true", help="run all (default)")
    ev.set_defaults(func=_cmd_eval)

    st = sub.add_parser("start", help="start the local preparation UI")
    st.add_argument("--host", default=DEFAULT_START_HOST)
    st.add_argument("--port", type=int, default=DEFAULT_START_PORT)
    st.set_defaults(func=_cmd_start)

    doc = sub.add_parser("doctor", help="check the local installation")
    doc.add_argument("--live", action="store_true", help="also probe the configured live endpoint")
    doc.set_defaults(func=_cmd_doctor)

    calc = sub.add_parser("calculate", help="write a deterministic tax calculation packet")
    calc.add_argument("input", help="TaxReturnInput JSON path")
    calc.add_argument("--output", required=True, help="calculation packet JSON path")
    calc.add_argument("--force", action="store_true", help="overwrite an existing output file")
    calc.set_defaults(func=_cmd_calculate)

    rc = sub.add_parser("rule-card", help="inspect the rule-card knowledge base")
    rc.add_argument("action", choices=["list"], nargs="?", default="list")
    rc.add_argument("--jurisdiction", default=None)
    rc.set_defaults(func=_cmd_rule_card)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

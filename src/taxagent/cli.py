"""taxagent CLI — ask / eval / rule-card."""

from __future__ import annotations

import argparse
import sys


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
    p = store.path(args.user)
    if not p.exists():
        print(f"no saved profile for {args.user!r} (looked in {p})")
        return 1
    profile = store.load(args.user)
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


def _cmd_rule_card(args: argparse.Namespace) -> int:
    from .knowledge import load_default_store

    store = load_default_store()
    for c in store.cards:
        if args.jurisdiction and c.jurisdiction != args.jurisdiction:
            continue
        print(f"{c.id}  [{c.jurisdiction}/{c.source_type}]  ty={c.tax_year}  — {c.topic}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="taxagent", description="TaxAgent Canada MVP")
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
    pr.set_defaults(func=_cmd_profile)

    ev = sub.add_parser("eval", help="run golden scenario evals")
    ev.add_argument("--scenario", default=None, help="run a single scenario by id")
    ev.add_argument("--all", action="store_true", help="run all (default)")
    ev.set_defaults(func=_cmd_eval)

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

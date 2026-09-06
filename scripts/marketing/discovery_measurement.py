from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_SLUG = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
WINDOW = {
    "source": "GitHub traffic API",
    "days": 14,
    "timezone": "UTC",
}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON") from exc


def _integer_or_missing(payload: dict[str, Any], key: str, label: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} {key} must be an integer or missing")
    if value < 0:
        raise ValueError(f"{label} {key} must be zero or positive")
    return value


def _traffic_summary(path: Path | None, label: str) -> dict[str, int | bool | None]:
    if path is None:
        return {"available": False, "count": None, "uniques": None}

    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON must be an object")
    if "message" in payload and "count" not in payload and "uniques" not in payload:
        return {
            "available": False,
            "count": None,
            "uniques": None,
            "source_error": "github_api_error",
        }
    if "count" not in payload or "uniques" not in payload:
        return {"available": False, "count": None, "uniques": None}

    count = _integer_or_missing(payload, "count", label)
    uniques = _integer_or_missing(payload, "uniques", label)
    if count is None or uniques is None:
        return {"available": False, "count": None, "uniques": None}
    if uniques > count:
        raise ValueError(f"{label} uniques cannot exceed count")

    return {
        "available": True,
        "count": count,
        "uniques": uniques,
    }


def _top_items(path: Path | None, *, label: str, text_fields: tuple[str, ...]) -> list[dict[str, Any]] | None:
    if path is None:
        return None

    payload = _read_json(path)
    if isinstance(payload, dict) and "message" in payload:
        return None
    if not isinstance(payload, list):
        raise ValueError(f"{label} JSON must be a list")

    items: list[dict[str, Any]] = []
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            raise ValueError(f"{label} row {index} must be an object")
        item: dict[str, Any] = {}
        for field in text_fields:
            value = row.get(field)
            if not isinstance(value, str):
                raise ValueError(f"{label} row {index} {field} must be a string")
            item[field] = value
        item["count"] = _integer_or_missing(row, "count", f"{label} row {index}")
        item["uniques"] = _integer_or_missing(row, "uniques", f"{label} row {index}")
        if item["count"] is not None and item["uniques"] is not None and item["uniques"] > item["count"]:
            raise ValueError(f"{label} row {index} uniques cannot exceed count")
        items.append(item)
    return items


def _validate_repo_slug(repo: str) -> None:
    if not REPO_SLUG.fullmatch(repo):
        raise ValueError("Repository must be an owner/name slug, for example K-kiron/TaxAgent.")


def _validate_utc_iso(value: str) -> None:
    if not value.endswith("Z"):
        raise ValueError("collected-at must be a UTC ISO timestamp ending in Z.")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("collected-at must be a valid UTC ISO timestamp.") from exc


def build_snapshot(
    *,
    repo: str,
    collected_at: str,
    views_path: Path | None,
    clones_path: Path | None,
    referrers_path: Path | None,
    paths_path: Path | None,
) -> dict[str, Any]:
    return {
        "schema_version": "taxagent.discovery_measurement.v1",
        "repo": repo,
        "collected_at": collected_at,
        "window": WINDOW,
        "views": _traffic_summary(views_path, "views"),
        "clones": _traffic_summary(clones_path, "clones"),
        "top_referrers": _top_items(
            referrers_path,
            label="top_referrers",
            text_fields=("referrer",),
        ),
        "popular_paths": _top_items(
            paths_path,
            label="popular_paths",
            text_fields=("path", "title"),
        ),
        "notes": {
            "privacy": "Snapshot stores GitHub aggregate counts only; it does not store raw logs, visitor identities, user tax data, credentials, prompts, or uploaded documents.",
            "clones": "GitHub clone counts are aggregate repository clones, not installs.",
            "missing_vs_zero": "Unavailable inputs are null with available=false; reported zero counts remain numeric zero.",
        },
    }


def _default_collected_at() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an offline aggregate GitHub discovery snapshot from saved gh traffic JSON."
    )
    parser.add_argument("--repo", required=True, help="Repository slug, for example K-kiron/TaxAgent.")
    parser.add_argument("--output", required=True, type=Path, help="Dated local JSON snapshot path.")
    parser.add_argument("--views-json", type=Path, help="Saved gh /traffic/views JSON.")
    parser.add_argument("--clones-json", type=Path, help="Saved gh /traffic/clones JSON.")
    parser.add_argument("--referrers-json", type=Path, help="Saved gh /traffic/popular/referrers JSON.")
    parser.add_argument("--paths-json", type=Path, help="Saved gh /traffic/popular/paths JSON.")
    parser.add_argument("--collected-at", default=_default_collected_at(), help="UTC collection timestamp.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(argv or []))
    output_path = args.output.resolve()
    input_paths = [
        path.resolve()
        for path in (args.views_json, args.clones_json, args.referrers_json, args.paths_json)
        if path is not None
    ]

    if output_path in input_paths:
        print("Output path must be different from every input JSON path.", file=sys.stderr)
        return 1
    if output_path.exists():
        print(f"Output path already exists: {output_path}", file=sys.stderr)
        return 1

    try:
        _validate_repo_slug(args.repo)
        _validate_utc_iso(args.collected_at)
        snapshot = build_snapshot(
            repo=args.repo,
            collected_at=args.collected_at,
            views_path=args.views_json,
            clones_path=args.clones_json,
            referrers_path=args.referrers_json,
            paths_path=args.paths_json,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    except FileExistsError:
        print(f"Output path already exists: {output_path}", file=sys.stderr)
        return 1
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

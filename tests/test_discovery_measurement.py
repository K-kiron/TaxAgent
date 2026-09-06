from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.marketing.discovery_measurement import build_snapshot, main


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_snapshot_preserves_missing_sources_and_zero_counts(tmp_path):
    views_path = _write_json(
        tmp_path / "views.json",
        {
            "count": 0,
            "uniques": 0,
            "views": [],
        },
    )

    snapshot = build_snapshot(
        repo="K-kiron/TaxAgent",
        collected_at="2026-09-06T12:00:00Z",
        views_path=views_path,
        clones_path=None,
        referrers_path=None,
        paths_path=None,
    )

    assert snapshot["repo"] == "K-kiron/TaxAgent"
    assert snapshot["window"] == {
        "source": "GitHub traffic API",
        "days": 14,
        "timezone": "UTC",
    }
    assert snapshot["collected_at"] == "2026-09-06T12:00:00Z"
    assert snapshot["views"] == {"available": True, "count": 0, "uniques": 0}
    assert snapshot["clones"] == {"available": False, "count": None, "uniques": None}
    assert snapshot["notes"]["clones"] == "GitHub clone counts are aggregate repository clones, not installs."


def test_snapshot_treats_saved_github_api_error_as_unavailable(tmp_path):
    views_path = _write_json(
        tmp_path / "views.json",
        {
            "message": "Must have push access to repository",
            "documentation_url": "https://docs.github.com/rest/metrics/traffic",
        },
    )

    snapshot = build_snapshot(
        repo="K-kiron/TaxAgent",
        collected_at="2026-09-06T12:00:00Z",
        views_path=views_path,
        clones_path=None,
        referrers_path=None,
        paths_path=None,
    )

    assert snapshot["views"] == {
        "available": False,
        "count": None,
        "uniques": None,
        "source_error": "github_api_error",
    }


def test_snapshot_is_aggregate_only_and_drops_daily_rows(tmp_path):
    views_path = _write_json(
        tmp_path / "views.json",
        {
            "count": 8,
            "uniques": 3,
            "views": [
                {"timestamp": "2026-09-05T00:00:00Z", "count": 5, "uniques": 2},
                {"timestamp": "2026-09-06T00:00:00Z", "count": 3, "uniques": 1},
            ],
        },
    )
    clones_path = _write_json(
        tmp_path / "clones.json",
        {
            "count": 2,
            "uniques": 1,
            "clones": [{"timestamp": "2026-09-06T00:00:00Z", "count": 2, "uniques": 1}],
        },
    )
    referrers_path = _write_json(
        tmp_path / "referrers.json",
        [{"referrer": "example.test", "count": 4, "uniques": 2, "extra": "ignored"}],
    )
    paths_path = _write_json(
        tmp_path / "paths.json",
        [{"path": "/K-kiron/TaxAgent", "title": "TaxAgent", "count": 6, "uniques": 3}],
    )

    snapshot = build_snapshot(
        repo="K-kiron/TaxAgent",
        collected_at="2026-09-06T12:00:00Z",
        views_path=views_path,
        clones_path=clones_path,
        referrers_path=referrers_path,
        paths_path=paths_path,
    )

    encoded = json.dumps(snapshot)
    assert "2026-09-05T00:00:00Z" not in encoded
    assert "extra" not in encoded
    assert snapshot["views"] == {"available": True, "count": 8, "uniques": 3}
    assert snapshot["clones"] == {"available": True, "count": 2, "uniques": 1}
    assert snapshot["top_referrers"] == [
        {"referrer": "example.test", "count": 4, "uniques": 2}
    ]
    assert snapshot["popular_paths"] == [
        {"path": "/K-kiron/TaxAgent", "title": "TaxAgent", "count": 6, "uniques": 3}
    ]


def test_cli_requires_explicit_output_and_refuses_overwrite(tmp_path, capsys):
    views_path = _write_json(tmp_path / "views.json", {"count": 1, "uniques": 1, "views": []})
    output_path = tmp_path / "snapshot.json"
    output_path.write_text("keep me", encoding="utf-8")

    code = main(
        [
            "--repo",
            "K-kiron/TaxAgent",
            "--views-json",
            str(views_path),
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "already exists" in captured.err
    assert output_path.read_text(encoding="utf-8") == "keep me"


def test_snapshot_treats_partial_missing_counts_as_unavailable(tmp_path):
    views_path = _write_json(tmp_path / "views.json", {"count": 5, "views": []})

    snapshot = build_snapshot(
        repo="K-kiron/TaxAgent",
        collected_at="2026-09-06T12:00:00Z",
        views_path=views_path,
        clones_path=None,
        referrers_path=None,
        paths_path=None,
    )

    assert snapshot["views"] == {"available": False, "count": None, "uniques": None}


def test_snapshot_treats_null_counts_as_unavailable(tmp_path):
    views_path = _write_json(tmp_path / "views.json", {"count": None, "uniques": None})

    snapshot = build_snapshot(
        repo="K-kiron/TaxAgent",
        collected_at="2026-09-06T12:00:00Z",
        views_path=views_path,
        clones_path=None,
        referrers_path=None,
        paths_path=None,
    )

    assert snapshot["views"] == {"available": False, "count": None, "uniques": None}


def test_snapshot_rejects_negative_counts_and_uniques_over_count(tmp_path):
    negative_path = _write_json(tmp_path / "negative.json", {"count": -1, "uniques": 0})
    impossible_path = _write_json(tmp_path / "impossible.json", {"count": 1, "uniques": 2})

    with pytest.raises(ValueError, match="views count must be zero or positive"):
        build_snapshot(
            repo="K-kiron/TaxAgent",
            collected_at="2026-09-06T12:00:00Z",
            views_path=negative_path,
            clones_path=None,
            referrers_path=None,
            paths_path=None,
        )

    with pytest.raises(ValueError, match="views uniques cannot exceed count"):
        build_snapshot(
            repo="K-kiron/TaxAgent",
            collected_at="2026-09-06T12:00:00Z",
            views_path=impossible_path,
            clones_path=None,
            referrers_path=None,
            paths_path=None,
        )


def test_cli_writes_dated_snapshot(tmp_path):
    views_path = _write_json(tmp_path / "views.json", {"count": 1, "uniques": 1, "views": []})
    output_path = tmp_path / "2026-09-06-taxagent-discovery-snapshot.json"

    code = main(
        [
            "--repo",
            "K-kiron/TaxAgent",
            "--views-json",
            str(views_path),
            "--collected-at",
            "2026-09-06T12:00:00Z",
            "--output",
            str(output_path),
        ]
    )

    assert code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["repo"] == "K-kiron/TaxAgent"
    assert payload["views"]["count"] == 1


def test_cli_rejects_same_input_and_output_path(tmp_path, capsys):
    views_path = _write_json(tmp_path / "views.json", {"count": 1, "uniques": 1, "views": []})

    code = main(
        [
            "--repo",
            "K-kiron/TaxAgent",
            "--views-json",
            str(views_path),
            "--output",
            str(views_path),
        ]
    )

    assert code == 1
    assert "must be different" in capsys.readouterr().err


def test_snapshot_rejects_malformed_traffic_input(tmp_path):
    views_path = _write_json(tmp_path / "views.json", {"count": "one", "uniques": 1})

    with pytest.raises(ValueError, match="views count"):
        build_snapshot(
            repo="K-kiron/TaxAgent",
            collected_at="2026-09-06T12:00:00Z",
            views_path=views_path,
            clones_path=None,
            referrers_path=None,
            paths_path=None,
        )


def test_cli_validates_repo_slug_and_utc_timestamp(tmp_path, capsys):
    output_path = tmp_path / "snapshot.json"

    bad_repo = main(
        [
            "--repo",
            "https://github.com/K-kiron/TaxAgent",
            "--collected-at",
            "2026-09-06T12:00:00Z",
            "--output",
            str(output_path),
        ]
    )
    bad_timestamp = main(
        [
            "--repo",
            "K-kiron/TaxAgent",
            "--collected-at",
            "2026-09-06T12:00:00-04:00",
            "--output",
            str(output_path),
        ]
    )

    err = capsys.readouterr().err
    assert bad_repo == 1
    assert bad_timestamp == 1
    assert "owner/name" in err
    assert "UTC ISO" in err
    assert not output_path.exists()

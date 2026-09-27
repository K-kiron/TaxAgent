from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from scripts.release import provision_official_pdf_fixtures as provisioner


def _item(name: str, payload: bytes) -> dict[str, object]:
    return {
        "name": name,
        "url": f"https://example.invalid/{name}",
        "bytes": len(payload),
        "sha256": sha256(payload).hexdigest(),
    }


def test_offline_missing_official_fixture_fails_before_network(tmp_path: Path, monkeypatch) -> None:
    def unexpected_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("offline provisioning must not download missing official fixtures")

    monkeypatch.setattr(provisioner.urllib.request, "urlopen", unexpected_network)

    with pytest.raises(RuntimeError, match="offline"):
        provisioner._copy_or_download(_item("form.pdf", b"%PDF\n"), tmp_path, None, 30.0, True)

    assert not (tmp_path / "form.pdf").exists()


def test_offline_source_corpus_copy_keeps_manifest_sha_verification(tmp_path: Path) -> None:
    payload = b"%PDF source corpus fixture\n"
    source = tmp_path / "source" / "official"
    target = tmp_path / "target"
    source.mkdir(parents=True)
    (source / "form.pdf").write_bytes(payload)

    provisioner._copy_or_download(_item("form.pdf", payload), target, tmp_path / "source", 30.0, True)

    assert (target / "form.pdf").read_bytes() == payload


def test_offline_source_corpus_tampered_fixture_fails_manifest_check(tmp_path: Path) -> None:
    source = tmp_path / "source" / "official"
    target = tmp_path / "target"
    source.mkdir(parents=True)
    (source / "form.pdf").write_bytes(b"%PDF tampered\n")

    with pytest.raises(RuntimeError, match="does not match manifest"):
        provisioner._copy_or_download(_item("form.pdf", b"%PDF expected\n"), target, tmp_path / "source", 30.0, True)

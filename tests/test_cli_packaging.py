from __future__ import annotations

import json
import os
import pytest
import subprocess
import sys
import types
from importlib import resources
from pathlib import Path

from test_federal_return import _input


def test_packaged_knowledge_base_assets_exist():
    kb = resources.files("taxagent").joinpath("data", "knowledge_base")

    assert kb.is_dir()
    assert kb.joinpath("quebec", "qc_ramq_drug_premium_v1.json").is_file()


def test_packaged_ramq_cards_do_not_overclaim_registration_or_retroactivity():
    from taxagent.knowledge.rule_card import load_default_store

    store = load_default_store()
    drug_premium = store.get("qc_ramq_drug_premium_v1")
    pr_timing = store.get("qc_ramq_pr_timing_v1")

    assert drug_premium is not None
    assert pr_timing is not None
    assert "registered with the RAMQ public plan" not in drug_premium.rule_summary
    assert "qualifying prescription drug coverage" in drug_premium.rule_summary
    assert "statutory exemption" in drug_premium.rule_summary
    assert "retroactive" not in pr_timing.rule_summary.lower()
    assert "Health insurance and prescription drug insurance are distinct" in pr_timing.rule_summary


def test_rule_cards_are_read_as_utf8(monkeypatch, tmp_path):
    from taxagent.knowledge.rule_card import load_default_store

    card_dir = tmp_path / "kb"
    card_dir.mkdir()
    (card_dir / "card.json").write_text(
        json.dumps(
            {
                "id": "utf8_card",
                "jurisdiction": "quebec",
                "source_type": "government",
                "topic": "utf8",
                "tax_year": 2025,
                "rule_summary": "Québec test — UTF-8",
                "source_urls": [],
                "required_facts": [],
                "uncertainty_notes": [],
                "last_verified": None,
            }
        ),
        encoding="utf-8",
    )
    encodings: list[str | None] = []
    original = Path.read_text

    def read_text(self: Path, *args, **kwargs):
        if self.suffix == ".json":
            encodings.append(kwargs.get("encoding"))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)

    store = load_default_store(card_dir)

    assert store.get("utf8_card") is not None
    assert encodings == ["utf-8"]


def test_doctor_offline_does_not_probe_live_endpoint(monkeypatch, capsys):
    from taxagent import cli

    def fail_urlopen(*args, **kwargs):
        raise AssertionError("doctor must not probe live endpoint unless --live is passed")

    monkeypatch.setattr("urllib.request.urlopen", fail_urlopen)

    code = cli.main(["doctor"])

    out = capsys.readouterr().out
    assert code == 0
    assert "offline checks" in out
    assert "rule cards" in out
    assert "web static assets" in out
    assert "local engine" in out
    assert "local UI" in out


def test_offline_cli_ignores_invalid_live_temperature_env(tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    env["TAXAGENT_TEMPERATURE"] = "not-a-number"

    result = subprocess.run(
        [sys.executable, "-c", "from taxagent import cli; raise SystemExit(cli.main(['doctor']))"],
        text=True,
        capture_output=True,
        env=env,
        cwd=tmp_path,
        check=False,
    )

    assert result.returncode == 0
    assert "offline checks" in result.stdout
    assert "not-a-number" not in result.stdout + result.stderr


def test_live_endpoint_display_strips_credentials_and_query():
    from taxagent import cli

    origin = cli._safe_origin("https://user:pass@example.test:9443/v1/models?api_key=secret")

    assert origin == "https://example.test:9443"
    assert "pass" not in origin
    assert "secret" not in origin


def test_doctor_live_reports_invalid_config_without_raw_value(tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    env["TAXAGENT_TEMPERATURE"] = "not-a-number"

    result = subprocess.run(
        [sys.executable, "-c", "from taxagent import cli; raise SystemExit(cli.main(['doctor', '--live']))"],
        text=True,
        capture_output=True,
        env=env,
        cwd=tmp_path,
        check=False,
    )

    assert result.returncode == 2
    assert "TAXAGENT_TEMPERATURE must be a number" in result.stderr
    assert "not-a-number" not in result.stdout + result.stderr


def test_profile_command_reads_year_specific_profile(monkeypatch, tmp_path, capsys):
    from taxagent import cli
    from taxagent.models import UserFact
    from taxagent.persistence import ProfileStore, UserProfile

    monkeypatch.setenv("TAXAGENT_PROFILE_DIR", str(tmp_path))
    store = ProfileStore()
    store.save(
        UserProfile(
            user_id="profile-user",
            tax_year=2025,
            facts={"province": UserFact(key="province", value="Quebec")},
        )
    )

    code = cli.main(["profile", "--user", "profile-user", "--tax-year", "2025"])

    out = capsys.readouterr().out
    assert code == 0
    assert "profile profile-user" in out
    assert "tax_year=2025" in out
    assert "province: Quebec" in out
    assert str(store.path("profile-user", 2025)) in out


def test_profile_command_preserves_no_year_profile_lookup(monkeypatch, tmp_path, capsys):
    from taxagent import cli
    from taxagent.models import UserFact
    from taxagent.persistence import ProfileStore, UserProfile

    monkeypatch.setenv("TAXAGENT_PROFILE_DIR", str(tmp_path))
    store = ProfileStore()
    store.save(
        UserProfile(
            user_id="profile-user",
            tax_year=None,
            facts={"province": UserFact(key="province", value="No-year Quebec")},
        )
    )

    code = cli.main(["profile", "--user", "profile-user"])

    out = capsys.readouterr().out
    assert code == 0
    assert "tax_year=None" in out
    assert "province: No-year Quebec" in out
    assert str(store.path("profile-user")) in out


def test_start_defaults_to_local_app_and_localhost(monkeypatch):
    from taxagent import cli

    calls = []
    fake_uvicorn = types.SimpleNamespace(
        run=lambda app, **kwargs: calls.append((app, kwargs)),
    )
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)

    code = cli.main(["start"])

    assert code == 0
    assert calls == [
        (
            "taxagent.web.local_app:app",
            {"host": "127.0.0.1", "port": 8056, "reload": False},
        )
    ]


def test_start_rejects_removed_live_flag():
    from taxagent import cli

    with pytest.raises(SystemExit) as excinfo:
        cli.main(["start", "--live"])

    assert excinfo.value.code == 2


def test_start_rejects_public_bind_flag():
    from taxagent import cli

    with pytest.raises(SystemExit) as excinfo:
        cli.main(["start", "--host", "0.0.0.0", "--allow-public-bind"])

    assert excinfo.value.code == 2


def test_start_refuses_nonloopback_host_even_without_live_server(capsys):
    from taxagent import cli

    code = cli.main(["start", "--host", "0.0.0.0"])

    err = capsys.readouterr().err
    assert code == 2
    assert "Refusing to bind outside localhost" in err
    assert "allow-public-bind" not in err


def test_calculate_command_writes_complete_packet(tmp_path):
    from taxagent import cli

    input_path = tmp_path / "taxagent_input.v1.json"
    output_path = tmp_path / "taxagent_calculation_packet.v1.json"
    input_path.write_text(_input(employed=True).model_dump_json(indent=2), encoding="utf-8")

    code = cli.main(["calculate", str(input_path), "--output", str(output_path)])

    packet = json.loads(output_path.read_text(encoding="utf-8"))
    assert code == 0
    assert packet["status"] == "complete"
    assert packet["federal_refund_or_balance"] == "2546.70"
    assert packet["quebec_refund_or_balance"] == "863.84"


def test_calculate_ignores_invalid_live_temperature_env(monkeypatch, tmp_path):
    from taxagent import cli

    monkeypatch.setenv("TAXAGENT_TEMPERATURE", "not-a-number")
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "packet.json"
    input_path.write_text(_input(employed=True).model_dump_json(indent=2), encoding="utf-8")

    code = cli.main(["calculate", str(input_path), "--output", str(output_path)])

    packet = json.loads(output_path.read_text(encoding="utf-8"))
    assert code == 0
    assert packet["status"] == "complete"


def test_calculate_command_writes_blocked_packet_with_blocked_exit(tmp_path):
    from taxagent import cli

    blocked = _input(employed=True).model_copy(update={"province_dec31": "ON"})
    input_path = tmp_path / "blocked.json"
    output_path = tmp_path / "blocked-packet.json"
    input_path.write_text(blocked.model_dump_json(indent=2), encoding="utf-8")

    code = cli.main(["calculate", str(input_path), "--output", str(output_path)])

    packet = json.loads(output_path.read_text(encoding="utf-8"))
    assert code == 2
    assert packet["status"] == "blocked"
    assert packet["federal_refund_or_balance"] is None
    assert packet["quebec_refund_or_balance"] is None


def test_calculate_command_rejects_invalid_schema_without_echoing_payload(tmp_path, capsys):
    from taxagent import cli

    input_path = tmp_path / "invalid.json"
    output_path = tmp_path / "packet.json"
    input_path.write_text(
        json.dumps({"schema_version": "2025-qc-v1", "secret": "raw-tax-input"}),
        encoding="utf-8",
    )

    code = cli.main(["calculate", str(input_path), "--output", str(output_path)])

    err = capsys.readouterr().err
    assert code == 1
    assert "TaxReturnInput" in err
    assert "raw-tax-input" not in err
    assert not output_path.exists()


def test_calculate_command_rejects_same_input_output(tmp_path, capsys):
    from taxagent import cli

    path = tmp_path / "packet.json"
    path.write_text(_input(employed=True).model_dump_json(indent=2), encoding="utf-8")

    code = cli.main(["calculate", str(path), "--output", str(path)])

    err = capsys.readouterr().err
    assert code == 1
    assert "must be different" in err


def test_calculate_command_guards_overwrite_unless_forced(tmp_path):
    from taxagent import cli

    input_path = tmp_path / "input.json"
    output_path = tmp_path / "packet.json"
    input_path.write_text(_input(employed=True).model_dump_json(indent=2), encoding="utf-8")
    output_path.write_text("keep me", encoding="utf-8")

    blocked = cli.main(["calculate", str(input_path), "--output", str(output_path)])
    forced = cli.main(["calculate", str(input_path), "--output", str(output_path), "--force"])

    packet = json.loads(output_path.read_text(encoding="utf-8"))
    assert blocked == 1
    assert forced == 0
    assert packet["status"] == "complete"

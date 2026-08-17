"""Tests for the mcp-data-tools CLI entrypoint."""

from __future__ import annotations

from mcp_data_tools.server.cli import main


def test_validate_config_success(tmp_path, capsys) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("server:\n  name: cli-test\n", encoding="utf-8")

    exit_code = main(["validate-config", "--config", str(config_path)])

    assert exit_code == 0
    assert "OK" in capsys.readouterr().out


def test_validate_config_missing_file(tmp_path, capsys) -> None:
    exit_code = main(["validate-config", "--config", str(tmp_path / "missing.yaml")])
    assert exit_code == 1
    assert "Configuration error" in capsys.readouterr().err


def test_validate_config_malformed(tmp_path, capsys) -> None:
    config_path = tmp_path / "bad.yaml"
    config_path.write_text("guardrails:\n  max_bytes_billed: -1\n", encoding="utf-8")
    exit_code = main(["validate-config", "--config", str(config_path)])
    assert exit_code == 1


def test_version_flag(capsys) -> None:
    try:
        main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
    out = capsys.readouterr().out
    assert out.strip()

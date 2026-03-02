"""Tests for ai_webops.py - Web operations and site management."""

import os
import json
import pytest
import yaml
import shutil
from unittest.mock import patch, MagicMock

from cbinder_gbfs.ai_webops import (
    command_exists,
    run_cmd,
    run_json_cmd,
    find_config_path,
    load_config,
    save_config,
    get_site_config,
    check_tools,
    ensure_tool,
    DEFAULT_CONFIG,
    CONFIG_PATHS,
)


# ─── command_exists ───────────────────────────────────────────────────────────


class TestCommandExists:
    def test_python_exists(self):
        # python or python3 should exist on any test system
        assert command_exists("python") or command_exists("python3")

    def test_nonexistent_command(self):
        assert command_exists("definitely_not_a_real_command_xyz") is False


# ─── run_cmd ──────────────────────────────────────────────────────────────────


class TestRunCmd:
    def test_successful_command(self):
        result = run_cmd(["python", "--version"])
        assert result is not None
        assert result.returncode == 0

    def test_missing_command(self, capsys):
        result = run_cmd(["nonexistent_cmd_xyz"])
        assert result is None

    def test_timeout(self, capsys):
        # Very short timeout on a long command
        import subprocess
        with patch("cbinder_gbfs.ai_webops.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="test", timeout=1)):
            result = run_cmd(["sleep", "100"], timeout=1)
        assert result is None


# ─── run_json_cmd ─────────────────────────────────────────────────────────────


class TestRunJsonCmd:
    def test_parses_json_output(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"key": "value"}'

        with patch("cbinder_gbfs.ai_webops.subprocess.run", return_value=mock_result):
            result = run_json_cmd(["echo", '{"key": "value"}'])
        assert result == {"key": "value"}

    def test_returns_none_on_non_json(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not json"

        with patch("cbinder_gbfs.ai_webops.subprocess.run", return_value=mock_result):
            result = run_json_cmd(["echo", "not json"])
        assert result is None

    def test_returns_none_on_failure(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("cbinder_gbfs.ai_webops.subprocess.run", return_value=mock_result):
            result = run_json_cmd(["false"])
        assert result is None


# ─── find_config_path ─────────────────────────────────────────────────────────


class TestFindConfigPath:
    def test_returns_existing_path(self, tmp_path, monkeypatch):
        config_file = tmp_path / "webops-sites.yml"
        config_file.write_text("sites: {}")

        import cbinder_gbfs.ai_webops as mod
        fallback = str(tmp_path / "fallback.yml")
        monkeypatch.setattr(mod, "CONFIG_PATHS", [str(config_file), fallback])

        result = find_config_path()
        assert result == str(config_file)

    def test_returns_fallback_when_none_exist(self, monkeypatch):
        import cbinder_gbfs.ai_webops as mod
        monkeypatch.setattr(mod, "CONFIG_PATHS", [
            "/nonexistent/path1.yml",
            "/nonexistent/path2.yml"
        ])
        result = find_config_path()
        assert result is not None  # returns fallback path


# ─── load_config ──────────────────────────────────────────────────────────────


class TestLoadConfig:
    def test_loads_existing_config(self, tmp_path, monkeypatch):
        config_file = tmp_path / "webops-sites.yml"
        config_data = {
            "sites": {"example.com": {"hosting": "vercel"}},
            "defaults": {"framework": "nextjs"}
        }
        config_file.write_text(yaml.dump(config_data))

        import cbinder_gbfs.ai_webops as mod
        fallback = str(tmp_path / "fallback.yml")
        monkeypatch.setattr(mod, "CONFIG_PATHS", [str(config_file), fallback])

        result = load_config()
        assert "example.com" in result["sites"]

    def test_returns_defaults_when_no_file(self, monkeypatch):
        import cbinder_gbfs.ai_webops as mod
        monkeypatch.setattr(mod, "CONFIG_PATHS", [
            "/nonexistent/path.yml", "/nonexistent/fallback.yml"
        ])
        result = load_config()
        assert "defaults" in result
        assert "sites" in result

    def test_returns_defaults_on_yaml_error(self, tmp_path, monkeypatch):
        bad_file = tmp_path / "bad.yml"
        bad_file.write_text(": [[[ invalid yaml")

        import cbinder_gbfs.ai_webops as mod
        fallback = str(tmp_path / "fallback.yml")
        monkeypatch.setattr(mod, "CONFIG_PATHS", [str(bad_file), fallback])

        result = load_config()
        assert "defaults" in result


# ─── save_config ──────────────────────────────────────────────────────────────


class TestSaveConfig:
    def test_saves_valid_config(self, tmp_path, monkeypatch):
        # find_config_path falls back to CONFIG_PATHS[1] when no file exists
        sys_path = str(tmp_path / "sys" / "webops-sites.yml")
        user_path = str(tmp_path / "user" / "webops-sites.yml")

        import cbinder_gbfs.ai_webops as mod
        monkeypatch.setattr(mod, "CONFIG_PATHS", [sys_path, user_path])

        save_config({"sites": {"test.com": {"hosting": "vercel"}}})

        # Config saved at fallback (user) path
        assert os.path.exists(user_path)
        with open(user_path) as f:
            loaded = yaml.safe_load(f)
        assert "test.com" in loaded["sites"]

    def test_handles_permission_error(self, tmp_path, monkeypatch, capsys):
        import cbinder_gbfs.ai_webops as mod
        config_file = str(tmp_path / "webops-sites.yml")
        fallback = str(tmp_path / "fallback.yml")
        monkeypatch.setattr(mod, "CONFIG_PATHS", [config_file, fallback])

        # Mock open to raise PermissionError (cross-platform)
        with patch("builtins.open", side_effect=PermissionError("denied")):
            save_config({"test": True})
        out = capsys.readouterr().out
        assert "yazilamadi" in out


# ─── get_site_config ──────────────────────────────────────────────────────────


class TestGetSiteConfig:
    def test_returns_site_config(self):
        config = {"sites": {"example.com": {"hosting": "vercel"}}}
        result = get_site_config(config, "example.com")
        assert result == {"hosting": "vercel"}

    def test_returns_none_for_unknown_site(self, capsys):
        config = {"sites": {"example.com": {"hosting": "vercel"}}}
        result = get_site_config(config, "unknown.com")
        assert result is None
        out = capsys.readouterr().out
        assert "bulunamadi" in out

    def test_empty_sites(self, capsys):
        config = {"sites": {}}
        result = get_site_config(config, "test.com")
        assert result is None


# ─── check_tools ──────────────────────────────────────────────────────────────


class TestCheckTools:
    def test_returns_dict(self):
        tools = check_tools()
        assert isinstance(tools, dict)
        assert "curl" in tools
        assert "vercel" in tools

    def test_values_are_boolean(self):
        tools = check_tools()
        for name, available in tools.items():
            assert isinstance(available, bool), f"{name} should be bool"


# ─── ensure_tool ──────────────────────────────────────────────────────────────


class TestEnsureTool:
    def test_returns_true_for_existing(self, monkeypatch):
        monkeypatch.setattr("cbinder_gbfs.ai_webops.command_exists", lambda cmd: True)
        assert ensure_tool("curl") is True

    def test_returns_false_for_missing(self, monkeypatch, capsys):
        monkeypatch.setattr("cbinder_gbfs.ai_webops.command_exists", lambda cmd: False)
        assert ensure_tool("vercel") is False
        out = capsys.readouterr().out
        assert "bulunamadi" in out


# ─── DEFAULT_CONFIG ───────────────────────────────────────────────────────────


class TestDefaultConfig:
    def test_has_sites_key(self):
        assert "sites" in DEFAULT_CONFIG
        assert isinstance(DEFAULT_CONFIG["sites"], dict)

    def test_has_defaults_key(self):
        assert "defaults" in DEFAULT_CONFIG
        assert "framework" in DEFAULT_CONFIG["defaults"]

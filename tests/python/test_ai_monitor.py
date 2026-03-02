"""Tests for ai_monitor.py - System and web monitoring daemon."""

import os
import json
import pytest
from unittest.mock import patch, MagicMock

from cbinder_gbfs.ai_monitor import (
    log_event,
    load_yaml,
    check_system,
    check_ollama,
    check_kernel_module,
    check_tailscale,
    _check_memory,
    DEFAULT_ALERT_THRESHOLDS,
)


# ─── log_event ────────────────────────────────────────────────────────────────


class TestLogEvent:
    def test_writes_to_log_file(self, tmp_path, monkeypatch):
        log_path = str(tmp_path / "monitor.log")
        import cbinder_gbfs.ai_monitor as mod
        monkeypatch.setattr(mod, "LOG_PATH", log_path)

        log_event("INFO", "Test message")

        with open(log_path) as f:
            content = f.read()
        assert "[INFO]" in content
        assert "Test message" in content

    def test_appends_multiple_entries(self, tmp_path, monkeypatch):
        log_path = str(tmp_path / "monitor.log")
        import cbinder_gbfs.ai_monitor as mod
        monkeypatch.setattr(mod, "LOG_PATH", log_path)

        log_event("INFO", "first")
        log_event("WARN", "second")

        with open(log_path) as f:
            lines = f.readlines()
        assert len(lines) == 2

    def test_handles_permission_error(self, monkeypatch):
        import cbinder_gbfs.ai_monitor as mod
        monkeypatch.setattr(mod, "LOG_PATH", "/root/impossible/path.log")
        # Should not raise
        log_event("ERROR", "cannot write")


# ─── load_yaml ────────────────────────────────────────────────────────────────


class TestLoadYaml:
    def test_loads_valid_yaml(self, tmp_path):
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text("key: value\nnested:\n  a: 1")
        result = load_yaml(str(yaml_file))
        assert result["key"] == "value"
        assert result["nested"]["a"] == 1

    def test_returns_empty_on_missing_file(self):
        result = load_yaml("/nonexistent/path.yml")
        assert result == {}

    def test_returns_empty_on_invalid_yaml(self, tmp_path):
        bad = tmp_path / "bad.yml"
        bad.write_text(": : [[[invalid")
        result = load_yaml(str(bad))
        assert result == {}

    def test_returns_empty_on_empty_file(self, tmp_path):
        empty = tmp_path / "empty.yml"
        empty.write_text("")
        result = load_yaml(str(empty))
        assert result == {}


# ─── check_system ─────────────────────────────────────────────────────────────


class TestCheckSystem:
    def test_returns_status_and_alerts(self):
        status, alerts = check_system()
        assert isinstance(status, dict)
        assert isinstance(alerts, list)
        assert "cpu_percent" in status
        assert "ram_percent" in status
        assert "disk_percent" in status

    def test_status_values_are_numeric(self):
        status, _ = check_system()
        assert isinstance(status["cpu_percent"], (int, float))
        assert isinstance(status["ram_used_mb"], int)
        assert isinstance(status["disk_used_gb"], int)

    def test_high_cpu_triggers_alert(self, monkeypatch):
        # Simulate high CPU
        mock_cpu = MagicMock(return_value=95.0)
        mock_mem = MagicMock()
        mock_mem.percent = 50
        mock_mem.used = 2 * 1024 * 1024 * 1024
        mock_mem.total = 8 * 1024 * 1024 * 1024
        mock_disk = MagicMock()
        mock_disk.used = 50 * 1024 * 1024 * 1024
        mock_disk.total = 100 * 1024 * 1024 * 1024
        mock_disk.percent = 50
        mock_freq = MagicMock()
        mock_freq.current = 2400

        import cbinder_gbfs.ai_monitor as mod
        monkeypatch.setattr(mod.psutil, "cpu_percent", mock_cpu)
        monkeypatch.setattr(mod.psutil, "virtual_memory", lambda: mock_mem)
        monkeypatch.setattr(mod.psutil, "disk_usage", lambda p: mock_disk)
        monkeypatch.setattr(mod.psutil, "cpu_freq", lambda: mock_freq)

        status, alerts = check_system()
        assert any("CPU" in a for a in alerts)


# ─── check_ollama ─────────────────────────────────────────────────────────────


class TestCheckOllama:
    def test_running(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "200"

        with patch("cbinder_gbfs.ai_monitor.subprocess.run", return_value=mock_result):
            status = check_ollama()
        assert status["ollama"] == "running"

    def test_stopped(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "000"

        with patch("cbinder_gbfs.ai_monitor.subprocess.run", return_value=mock_result):
            status = check_ollama()
        assert status["ollama"] == "stopped"

    def test_unreachable(self):
        with patch("cbinder_gbfs.ai_monitor.subprocess.run", side_effect=FileNotFoundError):
            status = check_ollama()
        assert status["ollama"] == "unreachable"

    def test_timeout(self):
        import subprocess
        with patch("cbinder_gbfs.ai_monitor.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="curl", timeout=5)):
            status = check_ollama()
        assert status["ollama"] == "unreachable"


# ─── check_kernel_module ─────────────────────────────────────────────────────


class TestCheckKernelModule:
    def test_not_loaded(self):
        with patch("cbinder_gbfs.ai_monitor.os.path.exists", return_value=False):
            status = check_kernel_module()
        assert status["kernel_module"] == "not_loaded"

    def test_loaded_with_dev(self):
        def fake_exists(path):
            if path == "/dev/ai_ctl":
                return True
            if path == "/proc/ai_status":
                return False
            return False

        with patch("cbinder_gbfs.ai_monitor.os.path.exists", side_effect=fake_exists):
            status = check_kernel_module()
        assert status["kernel_module"] == "loaded"


# ─── check_tailscale ─────────────────────────────────────────────────────────


class TestCheckTailscale:
    def test_not_installed(self):
        with patch("cbinder_gbfs.ai_monitor.subprocess.run", side_effect=FileNotFoundError):
            status = check_tailscale()
        assert "tailscale" in status

    def test_connected(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "Self": {"Online": True, "HostName": "testhost"},
            "Peer": {"peer1": {}, "peer2": {}}
        })

        with patch("cbinder_gbfs.ai_monitor.subprocess.run", return_value=mock_result):
            status = check_tailscale()
        assert status.get("tailscale_online") is True or "tailscale" in status


# ─── _check_memory ────────────────────────────────────────────────────────────


class TestCheckMemory:
    def test_returns_float(self):
        result = _check_memory()
        assert isinstance(result, float)
        assert result > 0


# ─── Thresholds ───────────────────────────────────────────────────────────────


class TestThresholds:
    def test_default_thresholds_exist(self):
        assert "cpu_percent" in DEFAULT_ALERT_THRESHOLDS
        assert "ram_percent" in DEFAULT_ALERT_THRESHOLDS
        assert "disk_percent" in DEFAULT_ALERT_THRESHOLDS
        assert "temp_celsius" in DEFAULT_ALERT_THRESHOLDS
        assert "response_time_ms" in DEFAULT_ALERT_THRESHOLDS

    def test_thresholds_are_reasonable(self):
        assert 50 < DEFAULT_ALERT_THRESHOLDS["cpu_percent"] <= 100
        assert 50 < DEFAULT_ALERT_THRESHOLDS["ram_percent"] <= 100
        assert 50 < DEFAULT_ALERT_THRESHOLDS["disk_percent"] <= 100

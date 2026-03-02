"""Tests for ai_cpufregd.py and ai_affinity.py - CPU daemons."""

import os
import pytest
import yaml
from unittest.mock import patch, MagicMock

from cbinder_gbfs.ai_cpufregd import (
    load_config,
    get_config_mtime,
    notify_kernel_reload,
    check_memory_usage as cpufreqd_check_memory,
)
from cbinder_gbfs.ai_affinity import (
    load_runtime_config,
    safe_renice,
    apply_affinity,
    check_memory_usage as affinity_check_memory,
)


# ─── ai_cpufregd ──────────────────────────────────────────────────────────────


class TestCpufreqdLoadConfig:
    def test_loads_valid_yaml(self, tmp_path, monkeypatch):
        config_file = tmp_path / "AI-runtime.yml"
        config_data = {"cpu": {"governor": "performance"}, "poll_interval": 5}
        config_file.write_text(yaml.dump(config_data))

        import cbinder_gbfs.ai_cpufregd as mod
        monkeypatch.setattr(mod, "CONFIG_PATH", str(config_file))

        result = load_config()
        assert result["cpu"]["governor"] == "performance"

    def test_returns_empty_on_missing_file(self, monkeypatch):
        import cbinder_gbfs.ai_cpufregd as mod
        monkeypatch.setattr(mod, "CONFIG_PATH", "/nonexistent/path.yml")
        assert load_config() == {}

    def test_returns_empty_on_invalid_yaml(self, tmp_path, monkeypatch):
        bad_file = tmp_path / "bad.yml"
        bad_file.write_text(": : : not valid yaml [[[")

        import cbinder_gbfs.ai_cpufregd as mod
        monkeypatch.setattr(mod, "CONFIG_PATH", str(bad_file))
        assert load_config() == {}


class TestGetConfigMtime:
    def test_returns_mtime_for_existing_file(self, tmp_path, monkeypatch):
        config_file = tmp_path / "AI-runtime.yml"
        config_file.write_text("test: true")

        import cbinder_gbfs.ai_cpufregd as mod
        monkeypatch.setattr(mod, "CONFIG_PATH", str(config_file))

        mtime = get_config_mtime()
        assert mtime > 0

    def test_returns_zero_for_missing_file(self, monkeypatch):
        import cbinder_gbfs.ai_cpufregd as mod
        monkeypatch.setattr(mod, "CONFIG_PATH", "/nonexistent/path.yml")
        assert get_config_mtime() == 0


class TestNotifyKernelReload:
    def test_writes_reload_when_sysfs_exists(self, tmp_path, monkeypatch):
        sysfs_path = tmp_path / "freqctl"
        sysfs_path.write_text("")

        import cbinder_gbfs.ai_cpufregd as mod
        monkeypatch.setattr(mod, "SYS_RELOAD", str(sysfs_path))

        notify_kernel_reload()
        assert sysfs_path.read_text() == "reload"

    def test_noop_when_sysfs_missing(self, monkeypatch):
        import cbinder_gbfs.ai_cpufregd as mod
        monkeypatch.setattr(mod, "SYS_RELOAD", "/nonexistent/path")
        # Should not raise
        notify_kernel_reload()


class TestCpufreqdMemory:
    def test_returns_positive_float(self):
        result = cpufreqd_check_memory()
        assert isinstance(result, float)
        assert result > 0


# ─── ai_affinity ──────────────────────────────────────────────────────────────


class TestLoadRuntimeConfig:
    def test_loads_valid_config(self, tmp_path, monkeypatch):
        config_file = tmp_path / "AI-runtime.yml"
        config_data = {
            "affinity": {
                "python3": {"cores": [0, 1], "nice": 5},
            }
        }
        config_file.write_text(yaml.dump(config_data))

        import cbinder_gbfs.ai_affinity as mod
        monkeypatch.setattr(mod, "RUNTIME_PROFILE", str(config_file))

        result = load_runtime_config()
        assert "affinity" in result
        assert result["affinity"]["python3"]["cores"] == [0, 1]

    def test_returns_empty_on_missing(self, monkeypatch):
        import cbinder_gbfs.ai_affinity as mod
        monkeypatch.setattr(mod, "RUNTIME_PROFILE", "/nonexistent/path.yml")
        assert load_runtime_config() == {}

    def test_returns_empty_on_yaml_error(self, tmp_path, monkeypatch):
        bad_file = tmp_path / "bad.yml"
        bad_file.write_text(": invalid [[[")

        import cbinder_gbfs.ai_affinity as mod
        monkeypatch.setattr(mod, "RUNTIME_PROFILE", str(bad_file))
        assert load_runtime_config() == {}


class TestSafeRenice:
    def test_clamps_nice_value_high(self):
        """Nice value above 19 should be clamped."""
        with patch("cbinder_gbfs.ai_affinity.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            safe_renice(1234, 50)
            args = mock_run.call_args[0][0]
            assert args[2] == "19"  # clamped to max

    def test_clamps_nice_value_low(self):
        """Nice value below -20 should be clamped."""
        with patch("cbinder_gbfs.ai_affinity.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            safe_renice(1234, -50)
            args = mock_run.call_args[0][0]
            assert args[2] == "-20"  # clamped to min

    def test_falls_back_to_psutil_on_missing_renice(self):
        """When renice command not found, uses psutil fallback."""
        with patch("cbinder_gbfs.ai_affinity.subprocess.run", side_effect=FileNotFoundError):
            with patch("cbinder_gbfs.ai_affinity.psutil.Process") as mock_proc:
                mock_proc.return_value.nice = MagicMock()
                safe_renice(1234, 5)
                mock_proc.return_value.nice.assert_called_once_with(5)


class TestApplyAffinity:
    def test_applies_cores_from_config(self, tmp_path, monkeypatch):
        import cbinder_gbfs.ai_affinity as mod
        config_data = {
            "affinity": {
                "test_proc": {"cores": [0, 1], "nice": 5}
            }
        }
        config_file = tmp_path / "AI-runtime.yml"
        config_file.write_text(yaml.dump(config_data))
        monkeypatch.setattr(mod, "RUNTIME_PROFILE", str(config_file))

        mock_proc = MagicMock()
        mock_proc.info = {"pid": 1234, "name": "test_proc"}
        mock_proc.cpu_affinity = MagicMock()

        with patch("cbinder_gbfs.ai_affinity.psutil.process_iter", return_value=[mock_proc]):
            with patch("cbinder_gbfs.ai_affinity.psutil.cpu_count", return_value=4):
                with patch("cbinder_gbfs.ai_affinity.safe_renice") as mock_renice:
                    apply_affinity()
                    mock_proc.cpu_affinity.assert_called_once_with([0, 1])
                    mock_renice.assert_called_once_with(1234, 5)

    def test_skips_invalid_core_numbers(self, tmp_path, monkeypatch):
        import cbinder_gbfs.ai_affinity as mod
        config_data = {
            "affinity": {
                "test_proc": {"cores": [0, 1, 99]}  # core 99 invalid on 4-core
            }
        }
        config_file = tmp_path / "AI-runtime.yml"
        config_file.write_text(yaml.dump(config_data))
        monkeypatch.setattr(mod, "RUNTIME_PROFILE", str(config_file))

        mock_proc = MagicMock()
        mock_proc.info = {"pid": 1234, "name": "test_proc"}
        mock_proc.cpu_affinity = MagicMock()

        with patch("cbinder_gbfs.ai_affinity.psutil.process_iter", return_value=[mock_proc]):
            with patch("cbinder_gbfs.ai_affinity.psutil.cpu_count", return_value=4):
                apply_affinity()
                mock_proc.cpu_affinity.assert_called_once_with([0, 1])  # 99 filtered out

    def test_empty_config_no_crash(self, monkeypatch):
        import cbinder_gbfs.ai_affinity as mod
        monkeypatch.setattr(mod, "RUNTIME_PROFILE", "/nonexistent/path.yml")
        apply_affinity()  # Should not raise

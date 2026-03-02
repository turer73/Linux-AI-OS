"""Tests for ai_dashboard.py - Bloomberg-style terminal dashboard."""

import os
import time
import pytest
from unittest.mock import patch, MagicMock

from cbinder_gbfs.ai_dashboard import (
    get_cpu_info,
    get_memory_info,
    get_disk_info,
    get_network_info,
    get_top_processes,
    get_service_status,
    VERSION,
    COLORS,
    _SVC_CACHE_TTL,
)


# ─── get_cpu_info ─────────────────────────────────────────────────────────────


class TestGetCpuInfo:
    def test_returns_expected_keys(self):
        info = get_cpu_info()
        assert "percent" in info
        assert "freq" in info
        assert "cores" in info
        assert "per_cpu" in info

    def test_percent_is_numeric(self):
        info = get_cpu_info()
        assert isinstance(info["percent"], (int, float))

    def test_cores_positive(self):
        info = get_cpu_info()
        assert info["cores"] > 0

    def test_handles_no_psutil(self, monkeypatch):
        import cbinder_gbfs.ai_dashboard as mod
        monkeypatch.setattr(mod, "psutil", None)
        info = get_cpu_info()
        assert info["percent"] == 0
        assert info["cores"] == 0


# ─── get_memory_info ──────────────────────────────────────────────────────────


class TestGetMemoryInfo:
    def test_returns_expected_keys(self):
        info = get_memory_info()
        assert "total" in info
        assert "used" in info
        assert "percent" in info
        assert "swap_percent" in info

    def test_total_greater_than_zero(self):
        info = get_memory_info()
        assert info["total"] > 0

    def test_percent_in_range(self):
        info = get_memory_info()
        assert 0 <= info["percent"] <= 100

    def test_handles_no_psutil(self, monkeypatch):
        import cbinder_gbfs.ai_dashboard as mod
        monkeypatch.setattr(mod, "psutil", None)
        info = get_memory_info()
        assert info["total"] == 0


# ─── get_disk_info ────────────────────────────────────────────────────────────


class TestGetDiskInfo:
    def test_returns_list(self):
        disks = get_disk_info()
        assert isinstance(disks, list)

    def test_disks_have_mount_info(self):
        disks = get_disk_info()
        if disks:
            assert "mount" in disks[0]
            assert "total" in disks[0]
            assert "percent" in disks[0]

    def test_handles_no_psutil(self, monkeypatch):
        import cbinder_gbfs.ai_dashboard as mod
        monkeypatch.setattr(mod, "psutil", None)
        assert get_disk_info() == []


# ─── get_network_info ─────────────────────────────────────────────────────────


class TestGetNetworkInfo:
    def test_returns_expected_keys(self):
        info = get_network_info()
        assert "sent" in info
        assert "recv" in info
        assert "connections" in info

    def test_handles_no_psutil(self, monkeypatch):
        import cbinder_gbfs.ai_dashboard as mod
        monkeypatch.setattr(mod, "psutil", None)
        info = get_network_info()
        assert info["sent"] == 0


# ─── get_top_processes ────────────────────────────────────────────────────────


class TestGetTopProcesses:
    def test_returns_list(self):
        procs = get_top_processes(n=5)
        assert isinstance(procs, list)
        assert len(procs) <= 5

    def test_processes_have_info(self):
        procs = get_top_processes(n=3)
        if procs:
            assert "pid" in procs[0]
            assert "name" in procs[0]

    def test_handles_no_psutil(self, monkeypatch):
        import cbinder_gbfs.ai_dashboard as mod
        monkeypatch.setattr(mod, "psutil", None)
        assert get_top_processes() == []


# ─── get_service_status ───────────────────────────────────────────────────────


class TestGetServiceStatus:
    def test_active_service(self):
        mock_result = MagicMock()
        mock_result.stdout = "active\n"

        import cbinder_gbfs.ai_dashboard as mod
        # Reset cache
        mod._svc_cache.clear()
        mod._svc_cache_time = 0.0

        with patch("cbinder_gbfs.ai_dashboard.subprocess.run", return_value=mock_result):
            state, color = get_service_status("test.service")
        assert state == "active"
        assert color == "ok"

    def test_inactive_service(self):
        mock_result = MagicMock()
        mock_result.stdout = "inactive\n"

        import cbinder_gbfs.ai_dashboard as mod
        mod._svc_cache.clear()
        mod._svc_cache_time = 0.0

        with patch("cbinder_gbfs.ai_dashboard.subprocess.run", return_value=mock_result):
            state, color = get_service_status("test.service")
        assert state == "inactive"
        assert color == "dim"

    def test_cache_reuses_result(self):
        mock_result = MagicMock()
        mock_result.stdout = "active\n"

        import cbinder_gbfs.ai_dashboard as mod
        mod._svc_cache.clear()
        mod._svc_cache_time = 0.0

        with patch("cbinder_gbfs.ai_dashboard.subprocess.run", return_value=mock_result) as mock_run:
            get_service_status("svc1")
            get_service_status("svc1")  # second call should use cache
            assert mock_run.call_count == 1

    def test_cache_expires(self):
        mock_result = MagicMock()
        mock_result.stdout = "active\n"

        import cbinder_gbfs.ai_dashboard as mod
        mod._svc_cache.clear()
        mod._svc_cache_time = time.time() - _SVC_CACHE_TTL - 10  # expired

        with patch("cbinder_gbfs.ai_dashboard.subprocess.run", return_value=mock_result) as mock_run:
            get_service_status("svc2")
            assert mock_run.call_count == 1

    def test_handles_systemctl_error(self):
        import cbinder_gbfs.ai_dashboard as mod
        mod._svc_cache.clear()
        mod._svc_cache_time = 0.0

        with patch("cbinder_gbfs.ai_dashboard.subprocess.run", side_effect=Exception("fail")):
            state, color = get_service_status("bad.service")
        assert state == "?"


# ─── Constants ────────────────────────────────────────────────────────────────


class TestConstants:
    def test_version_format(self):
        assert "." in VERSION

    def test_colors_dict(self):
        assert "ok" in COLORS
        assert "warn" in COLORS
        assert "crit" in COLORS

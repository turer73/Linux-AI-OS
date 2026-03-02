"""Tests for ai_lfs.py - AI Log File System inference engine."""

import os
import csv
import pytest
from unittest.mock import patch, MagicMock

from cbinder_gbfs.ai_lfs import (
    parse_io_stats,
    predict_rules,
    log_decision,
    collect_system_metrics,
    check_memory_usage,
    LABELS,
    LOG_FILE,
)


# ─── parse_io_stats ──────────────────────────────────────────────────────────


class TestParseIOStats:
    def test_valid_input(self):
        text = "read: 45000\nwrite: 12000\n"
        assert parse_io_stats(text) == [45000, 12000]

    def test_zero_values(self):
        text = "read: 0\nwrite: 0\n"
        assert parse_io_stats(text) == [0, 0]

    def test_large_values(self):
        text = "read: 999999999\nwrite: 888888888"
        assert parse_io_stats(text) == [999999999, 888888888]

    def test_extra_whitespace(self):
        text = "  read:   45000  \n  write:  12000  "
        assert parse_io_stats(text) == [45000, 12000]

    def test_invalid_text_returns_zeros(self):
        assert parse_io_stats("garbage text") == [0, 0]

    def test_empty_string_returns_zeros(self):
        assert parse_io_stats("") == [0, 0]

    def test_partial_data_returns_zeros(self):
        assert parse_io_stats("read: 100") == [0, 0]


# ─── predict_rules ───────────────────────────────────────────────────────────


class TestPredictRules:
    def test_idle_low_activity(self):
        assert predict_rules([500, 500]) == "IDLE"

    def test_idle_zero(self):
        assert predict_rules([0, 0]) == "IDLE"

    def test_read_focus(self):
        # read > write * 3
        assert predict_rules([10000, 1000]) == "READ_FOCUS"

    def test_write_priority(self):
        # write > read * 3
        assert predict_rules([1000, 10000]) == "WRITE_PRIORITY"

    def test_optimize_balance(self):
        # Neither dominates, total > 2000
        assert predict_rules([5000, 5000]) == "OPTIMIZE_BALANCE"

    def test_boundary_idle(self):
        # total exactly 2000 is still IDLE (< 2000 check)
        assert predict_rules([1000, 999]) == "IDLE"

    def test_boundary_total_above_2000(self):
        # total = 2001, equal reads/writes
        result = predict_rules([1001, 1000])
        assert result == "OPTIMIZE_BALANCE"


# ─── LABELS ───────────────────────────────────────────────────────────────────


class TestLabels:
    def test_label_count(self):
        assert len(LABELS) == 4

    def test_expected_labels(self):
        assert "IDLE" in LABELS
        assert "READ_FOCUS" in LABELS
        assert "WRITE_PRIORITY" in LABELS
        assert "OPTIMIZE_BALANCE" in LABELS


# ─── log_decision ─────────────────────────────────────────────────────────────


class TestLogDecision:
    def test_log_csv_write(self, tmp_path, monkeypatch):
        csv_path = str(tmp_path / "ai_lfs_log.csv")
        # Create header
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["timestamp", "read_bytes", "write_bytes", "ai_decision"])

        # Monkeypatch the module-level USE_COMPRESSED_LOG to False
        import cbinder_gbfs.ai_lfs as lfs_mod
        monkeypatch.setattr(lfs_mod, "USE_COMPRESSED_LOG", False)
        monkeypatch.setattr(lfs_mod, "LOG_FILE", str(tmp_path / "ai_lfs_log"))

        log_decision([1000, 2000], "READ_FOCUS")

        with open(csv_path) as f:
            rows = list(csv.reader(f))
        assert len(rows) == 2
        assert rows[1][3] == "READ_FOCUS"


# ─── collect_system_metrics ───────────────────────────────────────────────────


class TestCollectSystemMetrics:
    def test_returns_expected_keys(self):
        metrics = collect_system_metrics()
        assert "cpu_percent" in metrics
        assert "mem_percent" in metrics
        assert "load_avg" in metrics

    def test_cpu_percent_type(self):
        metrics = collect_system_metrics()
        assert isinstance(metrics["cpu_percent"], (int, float))

    def test_load_avg_is_list(self):
        metrics = collect_system_metrics()
        assert isinstance(metrics["load_avg"], list)
        assert len(metrics["load_avg"]) == 3


# ─── check_memory_usage ──────────────────────────────────────────────────────


class TestCheckMemoryUsage:
    def test_returns_float(self):
        result = check_memory_usage()
        assert isinstance(result, float)
        assert result > 0

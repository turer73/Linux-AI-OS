"""Tests for cbinder_gbfs.simulate_io_stats module."""

import os
import csv
import pytest
from unittest.mock import patch

from cbinder_gbfs.simulate_io_stats import generate_scenario, simulate_entries, LABELS


class TestGenerateScenario:
    def test_returns_tuple_of_three(self):
        result = generate_scenario()
        assert len(result) == 3

    def test_returns_valid_label(self):
        for _ in range(50):
            read, write, label = generate_scenario()
            assert label in LABELS

    def test_read_and_write_are_positive(self):
        for _ in range(50):
            read, write, _ = generate_scenario()
            assert read >= 0
            assert write >= 0

    def test_idle_has_low_values(self):
        # Run many times and check IDLE scenarios
        for _ in range(200):
            read, write, label = generate_scenario()
            if label == "IDLE":
                assert read <= 1000
                assert write <= 1000


class TestSimulateEntries:
    def test_creates_csv_file(self, tmp_path):
        log_file = str(tmp_path / "test_log.csv")
        with patch("cbinder_gbfs.simulate_io_stats.LOG_FILE", log_file):
            simulate_entries(count=10)
        assert os.path.exists(log_file)

    def test_correct_row_count(self, tmp_path):
        log_file = str(tmp_path / "test_log.csv")
        with patch("cbinder_gbfs.simulate_io_stats.LOG_FILE", log_file):
            simulate_entries(count=25)
        with open(log_file) as f:
            reader = csv.reader(f)
            rows = list(reader)
        # 1 header + 25 data rows
        assert len(rows) == 26

    def test_csv_has_correct_headers(self, tmp_path):
        log_file = str(tmp_path / "test_log.csv")
        with patch("cbinder_gbfs.simulate_io_stats.LOG_FILE", log_file):
            simulate_entries(count=5)
        with open(log_file) as f:
            reader = csv.reader(f)
            headers = next(reader)
        assert headers == ["timestamp", "read_bytes", "write_bytes", "ai_decision"]

    def test_appends_to_existing_file(self, tmp_path):
        log_file = str(tmp_path / "test_log.csv")
        with patch("cbinder_gbfs.simulate_io_stats.LOG_FILE", log_file):
            simulate_entries(count=5)
            simulate_entries(count=5)
        with open(log_file) as f:
            reader = csv.reader(f)
            rows = list(reader)
        # 1 header + 10 data rows (no duplicate header)
        assert len(rows) == 11

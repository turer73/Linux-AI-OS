"""Tests for cbinder_gbfs.ai_analyzer module."""

import os
import json
import pytest
from unittest.mock import patch

from cbinder_gbfs.ai_analyzer import (
    fetch_historical_metrics,
    score_affinity,
    recommend_affinity,
    list_services,
)


class TestFetchHistoricalMetrics:
    def test_returns_empty_when_no_file(self, tmp_path):
        fake_path = str(tmp_path / "nonexistent.csv")
        with patch("cbinder_gbfs.ai_analyzer.DATASET_FILE", fake_path):
            result = fetch_historical_metrics("test_service")
        assert result == []

    def test_loads_metrics_for_service(self, sample_dataset_csv):
        with patch("cbinder_gbfs.ai_analyzer.DATASET_FILE", str(sample_dataset_csv)):
            result = fetch_historical_metrics("test_service")
        assert len(result) == 3
        assert result[0]["cpu_usage"] == 45.2
        assert result[0]["assigned_cores"] == [0, 1]

    def test_filters_by_service_id(self, sample_dataset_csv):
        with patch("cbinder_gbfs.ai_analyzer.DATASET_FILE", str(sample_dataset_csv)):
            result = fetch_historical_metrics("nonexistent_service")
        assert result == []

    def test_skips_malformed_rows(self, tmp_path):
        path = tmp_path / "bad_data.csv"
        with open(path, "w", newline="") as f:
            f.write("service_id,cpu_usage,io_read,io_write,assigned_cores,nice_level,outcome_score,power_watts,cpu_temp\n")
            f.write("svc1,not_a_number,100,200,[0],0,0.5,10,50\n")
            f.write("svc1,50.0,100,200,[0],0,0.8,10,50\n")
        with patch("cbinder_gbfs.ai_analyzer.DATASET_FILE", str(path)):
            result = fetch_historical_metrics("svc1")
        assert len(result) == 1


class TestScoreAffinity:
    def test_score_calculation(self):
        entries = [
            {"outcome_score": 0.8, "power_watts": 10.0, "cpu_temp": 50.0},
            {"outcome_score": 0.9, "power_watts": 12.0, "cpu_temp": 55.0},
        ]
        score = score_affinity(entries)
        assert isinstance(score, float)

    def test_higher_outcome_means_higher_score(self):
        good = [{"outcome_score": 0.95, "power_watts": 10.0, "cpu_temp": 50.0}]
        bad = [{"outcome_score": 0.20, "power_watts": 10.0, "cpu_temp": 50.0}]
        assert score_affinity(good) > score_affinity(bad)

    def test_higher_power_reduces_score(self):
        low_power = [{"outcome_score": 0.8, "power_watts": 5.0, "cpu_temp": 50.0}]
        high_power = [{"outcome_score": 0.8, "power_watts": 50.0, "cpu_temp": 50.0}]
        assert score_affinity(low_power) > score_affinity(high_power)


class TestRecommendAffinity:
    def test_fallback_to_profile_when_no_history(self, sample_service_profile, tmp_path):
        fake_dataset = str(tmp_path / "empty.csv")
        with patch("cbinder_gbfs.ai_analyzer.SERVICE_DIR", str(sample_service_profile.parent) + "/"), \
             patch("cbinder_gbfs.ai_analyzer.DATASET_FILE", fake_dataset):
            affinity, nice, score = recommend_affinity("test_service")
        assert affinity == [0, 1]
        assert nice == 5
        assert score == 0.0

    def test_uses_history_when_available(self, sample_dataset_csv, sample_service_profile):
        with patch("cbinder_gbfs.ai_analyzer.SERVICE_DIR", str(sample_service_profile.parent) + "/"), \
             patch("cbinder_gbfs.ai_analyzer.DATASET_FILE", str(sample_dataset_csv)):
            affinity, nice, score = recommend_affinity("test_service")
        assert isinstance(affinity, list)
        assert isinstance(nice, int)
        assert score != 0.0


class TestListServices:
    def test_lists_service_files(self, tmp_path):
        svc_dir = tmp_path / "services"
        svc_dir.mkdir()
        (svc_dir / "web.svc.yml").touch()
        (svc_dir / "db.svc.yml").touch()
        (svc_dir / "not_a_service.txt").touch()
        with patch("cbinder_gbfs.ai_analyzer.SERVICE_DIR", str(svc_dir) + "/"):
            services = list_services()
        assert sorted(services) == ["db", "web"]

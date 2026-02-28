"""Shared pytest fixtures for Linux-AI test suite."""

import os
import sys
import csv
import tempfile
import pytest
import yaml

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "proc-utils-AI"))


@pytest.fixture
def tmp_config_dir(tmp_path):
    """Create a temporary /var/AI-stump/ equivalent."""
    config_dir = tmp_path / "AI-stump"
    services_dir = config_dir / "services"
    services_dir.mkdir(parents=True)
    return config_dir


@pytest.fixture
def sample_runtime_yml(tmp_config_dir):
    """Create a sample AI-runtime.yml for testing."""
    config = {
        "version": "0.1.0",
        "mode": "user",
        "cpu": {
            "governor": "ondemand",
            "min_freq_mhz": 800,
            "max_freq_mhz": 3600,
        },
        "affinity": {
            "python3": {"cores": [0, 1], "nice": 5},
            "firefox": {"cores": [2, 3], "nice": 0},
        },
        "logging": {
            "level": "info",
            "file": "/tmp/ai-runtime.log",
        },
    }
    path = tmp_config_dir / "AI-runtime.yml"
    with open(path, "w") as f:
        yaml.dump(config, f)
    return path


@pytest.fixture
def sample_service_profile(tmp_config_dir):
    """Create a sample service profile (.svc.yml)."""
    services_dir = tmp_config_dir / "services"
    profile = {
        "service_id": "test_service",
        "process_name": "test_proc",
        "ai_guidance": {
            "default_affinity": [0, 1],
            "preferred_nice": 5,
            "io_priority": "normal",
        },
    }
    path = services_dir / "test_service.svc.yml"
    with open(path, "w") as f:
        yaml.dump(profile, f)
    return path


@pytest.fixture
def sample_dataset_csv(tmp_path):
    """Create a sample ai_dataset.csv for testing."""
    path = tmp_path / "ai_dataset.csv"
    fieldnames = [
        "service_id", "cpu_usage", "io_read", "io_write",
        "assigned_cores", "nice_level", "outcome_score",
        "power_watts", "cpu_temp",
    ]
    rows = [
        {
            "service_id": "test_service",
            "cpu_usage": "45.2",
            "io_read": "15000",
            "io_write": "8000",
            "assigned_cores": "[0, 1]",
            "nice_level": "5",
            "outcome_score": "0.85",
            "power_watts": "12.5",
            "cpu_temp": "55.0",
        },
        {
            "service_id": "test_service",
            "cpu_usage": "62.1",
            "io_read": "22000",
            "io_write": "12000",
            "assigned_cores": "[0, 1, 2]",
            "nice_level": "0",
            "outcome_score": "0.72",
            "power_watts": "18.3",
            "cpu_temp": "68.0",
        },
        {
            "service_id": "test_service",
            "cpu_usage": "30.0",
            "io_read": "5000",
            "io_write": "3000",
            "assigned_cores": "[0, 1]",
            "nice_level": "5",
            "outcome_score": "0.90",
            "power_watts": "10.0",
            "cpu_temp": "48.0",
        },
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture
def sample_io_log_csv(tmp_path):
    """Create a sample ai_lfs_log.csv for testing."""
    path = tmp_path / "ai_lfs_log.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "read_bytes", "write_bytes", "ai_decision"])
        writer.writerow(["2026-01-01T00:00:00", "500", "300", "IDLE"])
        writer.writerow(["2026-01-01T00:01:00", "25000", "3000", "READ_FOCUS"])
        writer.writerow(["2026-01-01T00:02:00", "2000", "30000", "WRITE_PRIORITY"])
        writer.writerow(["2026-01-01T00:03:00", "20000", "18000", "OPTIMIZE_BALANCE"])
    return path

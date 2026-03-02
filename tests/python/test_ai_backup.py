"""Tests for cbinder_gbfs.ai_backup module - utility functions."""

import os
import pytest
import yaml
from unittest.mock import patch

from cbinder_gbfs.ai_backup import (
    timestamp_str,
    human_size,
    load_backup_config,
    DEFAULT_CONFIG,
)


class TestTimestampStr:
    """Test timestamp string generation."""

    def test_returns_string(self):
        result = timestamp_str()
        assert isinstance(result, str)

    def test_format_is_filename_safe(self):
        result = timestamp_str()
        # Should not contain characters unsafe for filenames
        unsafe = set('<>:"/\\|?*')
        assert not unsafe.intersection(set(result))

    def test_length_is_reasonable(self):
        result = timestamp_str()
        # YYYYMMDD_HHMMSS = 15 chars
        assert 8 <= len(result) <= 25

    def test_different_calls_may_differ(self):
        r1 = timestamp_str()
        r2 = timestamp_str()
        assert isinstance(r1, str)
        assert isinstance(r2, str)


class TestHumanSize:
    """Test byte to human-readable size conversion."""

    def test_zero(self):
        result = human_size(0)
        assert "0" in result and "B" in result

    def test_bytes(self):
        result = human_size(100)
        assert "B" in result

    def test_kilobytes(self):
        result = human_size(2048)
        assert "K" in result

    def test_megabytes(self):
        result = human_size(5 * 1024 * 1024)
        assert "M" in result

    def test_gigabytes(self):
        result = human_size(3 * 1024 ** 3)
        assert "G" in result


class TestDefaultConfig:
    """Test default configuration structure."""

    def test_is_dict(self):
        assert isinstance(DEFAULT_CONFIG, dict)

    def test_has_backup_dir(self):
        assert any(
            "backup" in str(v).lower() or "dir" in str(k).lower()
            for k, v in DEFAULT_CONFIG.items()
        )


class TestLoadBackupConfig:
    """Test config loading with mock filesystem."""

    def test_returns_dict_with_valid_config(self, tmp_path):
        config_file = tmp_path / "backup.yml"
        config = {"backup_dir": str(tmp_path / "backups"), "retention_days": 7}
        with open(config_file, "w") as f:
            yaml.dump(config, f)

        with patch("cbinder_gbfs.ai_backup.BACKUP_CONFIG_PATH", str(config_file)):
            result = load_backup_config()
        assert isinstance(result, dict)
        assert result["retention_days"] == 7

    def test_missing_file_returns_defaults(self, tmp_path):
        fake_path = str(tmp_path / "nonexistent.yml")
        with patch("cbinder_gbfs.ai_backup.BACKUP_CONFIG_PATH", fake_path):
            result = load_backup_config()
        assert isinstance(result, dict)
        # Should return DEFAULT_CONFIG when file doesn't exist
        assert result == DEFAULT_CONFIG

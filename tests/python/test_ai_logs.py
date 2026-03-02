"""Tests for cbinder_gbfs.ai_logs module - log parsing and formatting."""

import pytest
from datetime import datetime

from cbinder_gbfs.ai_logs import (
    LogEntry,
    parse_log_line,
    format_entry,
    _human_size,
)


class TestHumanSize:
    """Test byte size to human-readable conversion."""

    def test_zero_bytes(self):
        result = _human_size(0)
        assert "0" in result and "B" in result

    def test_bytes(self):
        result = _human_size(500)
        assert "B" in result

    def test_kilobytes(self):
        result = _human_size(1024)
        assert "KB" in result or "K" in result

    def test_megabytes(self):
        result = _human_size(1024 * 1024)
        assert "MB" in result or "M" in result

    def test_gigabytes(self):
        result = _human_size(1024 ** 3)
        assert "GB" in result or "G" in result

    def test_large_value(self):
        result = _human_size(1024 ** 4)
        assert "TB" in result or "T" in result


class TestLogEntry:
    """Test LogEntry data class."""

    def test_creation(self):
        entry = LogEntry(
            timestamp="2026-03-01 10:00:00",
            level="INFO",
            message="Test message",
            source="test",
            raw="[2026-03-01 10:00:00] [INFO] Test message",
        )
        assert entry.timestamp == "2026-03-01 10:00:00"
        assert entry.level == "INFO"
        assert entry.message == "Test message"
        assert entry.source == "test"

    def test_to_dict(self):
        entry = LogEntry(
            timestamp="2026-03-01 10:00:00",
            level="ERROR",
            message="Something failed",
            source="ai-monitor",
            raw="raw line",
        )
        d = entry.to_dict()
        assert isinstance(d, dict)
        assert d["level"] == "ERROR"
        assert d["source"] == "ai-monitor"
        assert d["message"] == "Something failed"


class TestParseLogLine:
    """Test log line parsing with [timestamp] [LEVEL] message format."""

    def test_standard_format(self):
        # Actual log format: [YYYY-MM-DD HH:MM:SS] [LEVEL] message
        line = "[2026-03-01 10:00:00] [INFO] System started"
        entry = parse_log_line(line, source="test")
        assert entry is not None
        assert entry.level == "INFO"
        assert "System started" in entry.message

    def test_error_level(self):
        line = "[2026-03-01 10:00:00] [ERROR] Connection failed"
        entry = parse_log_line(line, source="test")
        assert entry is not None
        assert entry.level == "ERROR"

    def test_warning_level(self):
        line = "[2026-03-01 10:00:00] [WARNING] Low memory"
        entry = parse_log_line(line, source="test")
        assert entry is not None
        assert entry.level == "WARNING"

    def test_empty_line_returns_none(self):
        result = parse_log_line("", source="test")
        assert result is None

    def test_unparseable_line_falls_back_to_info(self):
        # Unstructured lines are captured as INFO level (fallback behavior)
        result = parse_log_line("random text without format", source="test")
        assert result is not None
        assert result.level == "INFO"
        assert "random text" in result.message

    def test_source_is_preserved(self):
        line = "[2026-03-01 10:00:00] [INFO] msg"
        entry = parse_log_line(line, source="ai-backup")
        assert entry is not None
        assert entry.source == "ai-backup"

    def test_raw_is_preserved(self):
        line = "[2026-03-01 10:00:00] [INFO] original line content"
        entry = parse_log_line(line, source="test")
        assert entry is not None
        assert entry.raw == line


class TestFormatEntry:
    """Test log entry formatting."""

    def test_format_includes_level(self):
        entry = LogEntry(
            timestamp="2026-03-01 10:00:00",
            level="INFO",
            message="Test",
            source="test",
            raw="raw",
        )
        result = format_entry(entry, show_source=False)
        assert "INFO" in result

    def test_format_with_source(self):
        entry = LogEntry(
            timestamp="2026-03-01 10:00:00",
            level="ERROR",
            message="Fail",
            source="ai-monitor",
            raw="raw",
        )
        result = format_entry(entry, show_source=True)
        assert "ai-monitor" in result

    def test_format_without_source(self):
        entry = LogEntry(
            timestamp="2026-03-01 10:00:00",
            level="INFO",
            message="Test",
            source="hidden",
            raw="raw",
        )
        result = format_entry(entry, show_source=False)
        assert isinstance(result, str)

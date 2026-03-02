"""Tests for compressed_log.py - Delta encoding, gzip compression, binary metrics."""

import os
import gzip
import struct
import pytest

from cbinder_gbfs.compressed_log import (
    DeltaEncoder,
    CompressedLogger,
    BinaryMetricWriter,
)


# ─── DeltaEncoder ─────────────────────────────────────────────────────────────


class TestDeltaEncoder:
    def test_first_value_is_absolute(self):
        enc = DeltaEncoder()
        vals, is_delta, run = enc.encode([100, 200], "IDLE")
        assert vals == [100, 200]
        assert is_delta is False
        assert run == 1

    def test_second_value_is_delta(self):
        enc = DeltaEncoder()
        enc.encode([100, 200], "IDLE")
        vals, is_delta, run = enc.encode([110, 190], "IDLE")
        assert vals == [10, -10]
        assert is_delta is True

    def test_run_length_same_label(self):
        enc = DeltaEncoder()
        enc.encode([100, 200], "IDLE")
        _, _, run = enc.encode([100, 200], "IDLE")
        assert run == 2
        _, _, run = enc.encode([100, 200], "IDLE")
        assert run == 3

    def test_run_length_resets_on_label_change(self):
        enc = DeltaEncoder()
        enc.encode([100, 200], "IDLE")
        enc.encode([100, 200], "IDLE")
        _, _, run = enc.encode([500, 100], "READ_FOCUS")
        assert run == 1

    def test_decode_absolute(self):
        enc = DeltaEncoder()
        result = enc.decode([100, 200], False, [0, 0])
        assert result == [100, 200]

    def test_decode_delta(self):
        enc = DeltaEncoder()
        result = enc.decode([10, -10], True, [100, 200])
        assert result == [110, 190]

    def test_reset(self):
        enc = DeltaEncoder()
        enc.encode([100, 200], "IDLE")
        enc.reset()
        assert enc.prev_values is None
        assert enc.run_count == 0
        vals, is_delta, _ = enc.encode([50, 60], "IDLE")
        assert is_delta is False
        assert vals == [50, 60]


# ─── CompressedLogger ─────────────────────────────────────────────────────────


class TestCompressedLogger:
    def test_creates_gz_file(self, tmp_path):
        base = str(tmp_path / "test_log")
        logger = CompressedLogger(base, max_size_mb=1)
        assert os.path.exists(f"{base}.csv.gz")
        logger.close()

    def test_write_and_read_single_entry(self, tmp_path):
        base = str(tmp_path / "test_log")
        logger = CompressedLogger(base, max_size_mb=1)
        logger.write([1000, 2000], "IDLE")
        logger.flush()
        entries = logger.read_all()
        assert len(entries) == 1
        assert entries[0]["read_bytes"] == 1000
        assert entries[0]["write_bytes"] == 2000
        assert entries[0]["decision"] == "IDLE"
        logger.close()

    def test_write_multiple_entries_delta(self, tmp_path):
        base = str(tmp_path / "test_log")
        logger = CompressedLogger(base, max_size_mb=1)
        logger.write([1000, 2000], "IDLE")
        logger.write([1100, 2200], "READ_FOCUS")
        logger.flush()
        entries = logger.read_all()
        assert len(entries) == 2
        assert entries[1]["read_bytes"] == 1100
        assert entries[1]["write_bytes"] == 2200
        assert entries[1]["decision"] == "READ_FOCUS"
        logger.close()

    def test_label_map_coverage(self):
        assert CompressedLogger.LABEL_MAP["IDLE"] == 0
        assert CompressedLogger.LABEL_MAP["READ_FOCUS"] == 1
        assert CompressedLogger.LABEL_MAP["WRITE_PRIORITY"] == 2
        assert CompressedLogger.LABEL_MAP["OPTIMIZE_BALANCE"] == 3

    def test_label_reverse_map(self):
        for label, idx in CompressedLogger.LABEL_MAP.items():
            assert CompressedLogger.LABEL_REVERSE[idx] == label

    def test_rotation_triggers_on_large_file(self, tmp_path, monkeypatch):
        base = str(tmp_path / "rot_log")
        # Patch os.rename to os.replace for Windows compatibility
        import cbinder_gbfs.compressed_log as cl_mod
        monkeypatch.setattr(cl_mod.os, "rename", os.replace)
        # max_size_mb very small so rotation triggers quickly
        logger = CompressedLogger(base, max_size_mb=0.0001)
        # Write enough entries to exceed ~100 bytes
        for i in range(50):
            logger.write([i * 100, i * 50], "IDLE")
        logger.close()
        # Should have rotated at least once (old file renamed)
        rotated = [f for f in os.listdir(tmp_path) if ".csv.gz" in f and f != "rot_log.csv.gz"]
        assert len(rotated) >= 1

    def test_close_and_reopen(self, tmp_path):
        base = str(tmp_path / "test_log")
        logger = CompressedLogger(base, max_size_mb=1)
        logger.write([500, 600], "IDLE")
        logger.close()
        assert logger._fh is None
        # read_all should still work after close
        entries = logger.read_all()
        assert len(entries) == 1

    def test_stats_no_file(self, tmp_path, capsys):
        base = str(tmp_path / "nonexistent")
        logger = CompressedLogger.__new__(CompressedLogger)
        logger.gz_path = f"{base}.csv.gz"
        logger.stats()
        out = capsys.readouterr().out
        assert "No log file" in out

    def test_read_all_empty_file(self, tmp_path):
        base = str(tmp_path / "empty_log")
        logger = CompressedLogger(base, max_size_mb=1)
        entries = logger.read_all()
        assert entries == []
        logger.close()


# ─── BinaryMetricWriter ──────────────────────────────────────────────────────


class TestBinaryMetricWriter:
    def test_write_and_read_single(self, tmp_path):
        path = str(tmp_path / "metrics.bin")
        writer = BinaryMetricWriter(path)
        writer.write({
            "timestamp": 1700000000,
            "read_kb": 100,
            "write_kb": 200,
            "cpu_percent": 50,
            "ram_percent": 60,
            "cpu_temp": 55,
            "decision_id": 1,
            "cpu_freq_mhz": 2400,
            "gpu_temp": 45,
        })
        writer.flush()
        writer.close()

        entries = writer.read_all()
        assert len(entries) == 1
        assert entries[0]["timestamp"] == 1700000000
        assert entries[0]["read_kb"] == 100
        assert entries[0]["write_kb"] == 200
        assert entries[0]["cpu_percent"] == 50
        assert entries[0]["decision_id"] == 1

    def test_delta_encoding_io(self, tmp_path):
        path = str(tmp_path / "metrics.bin")
        writer = BinaryMetricWriter(path)
        writer.write({"read_kb": 100, "write_kb": 200})
        writer.write({"read_kb": 250, "write_kb": 300})
        writer.flush()
        writer.close()

        entries = writer.read_all()
        assert len(entries) == 2
        assert entries[0]["io_read_delta"] == 100   # first: delta from 0
        assert entries[1]["io_read_delta"] == 150   # 250-100

    def test_clamp_values(self, tmp_path):
        path = str(tmp_path / "metrics.bin")
        writer = BinaryMetricWriter(path)
        writer.write({
            "read_kb": 999999,   # should clamp to 65535
            "cpu_percent": 200,  # should clamp to 100
            "decision_id": 10,   # should clamp to 3
        })
        writer.flush()
        writer.close()

        entries = writer.read_all()
        assert entries[0]["read_kb"] == 65535
        assert entries[0]["cpu_percent"] == 100
        assert entries[0]["decision_id"] == 3

    def test_read_all_empty(self, tmp_path):
        path = str(tmp_path / "empty.bin")
        writer = BinaryMetricWriter(path)
        writer.close()
        entries = writer.read_all()
        assert entries == []

    def test_close_sets_fh_none(self, tmp_path):
        path = str(tmp_path / "metrics.bin")
        writer = BinaryMetricWriter(path)
        writer.close()
        assert writer._fh is None

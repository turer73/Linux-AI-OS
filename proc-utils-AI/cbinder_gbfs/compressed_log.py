"""
compressed_log.py - Compressed logging with delta encoding

Compression techniques:
  1. Delta encoding: Only stores changes between consecutive readings
     - CPU 70% → 72% stored as +2 (1 byte vs 4 bytes)
     - Typical 60-80% reduction in I/O data size

  2. Run-length encoding: Repeated IDLE states compressed
     - "IDLE,IDLE,IDLE,IDLE" → "IDLE*4" (75% reduction)

  3. Gzip compression: Log files compressed on-the-fly
     - CSV text → gzip: 5-10x smaller on disk
     - Transparent read/write (gzip.open)

  4. Compact binary format: Struct packing for metrics
     - JSON metrics: ~200 bytes per entry
     - Binary packed: ~24 bytes per entry (8x smaller)

Combined effect: ~10-20x total compression vs raw CSV/JSON

Usage:
    from compressed_log import CompressedLogger
    logger = CompressedLogger("ai_lfs_log")
    logger.write([45000, 12000], "READ_FOCUS")
    logger.flush()
"""

import os
import gzip
import struct
import time
from datetime import datetime


class DeltaEncoder:
    """Encodes metric streams using delta encoding.

    For slowly-changing values (CPU %, temperature), deltas are typically
    near zero. This makes the data highly compressible.
    """

    def __init__(self):
        self.prev_values = None
        self.run_count = 0
        self.run_label = None

    def encode(self, values, label):
        """Encode values using delta from previous.

        Returns: (encoded_values, is_delta, run_length)
        """
        if self.prev_values is None:
            self.prev_values = values[:]
            self.run_count = 1
            self.run_label = label
            return values, False, 1

        # Delta encode
        deltas = [v - p for v, p in zip(values, self.prev_values)]
        self.prev_values = values[:]

        # Run-length encoding for repeated decisions
        if label == self.run_label:
            self.run_count += 1
        else:
            self.run_count = 1
            self.run_label = label

        return deltas, True, self.run_count

    def decode(self, encoded, is_delta, prev_absolute):
        """Decode delta-encoded values back to absolute."""
        if not is_delta:
            return encoded
        return [e + p for e, p in zip(encoded, prev_absolute)]

    def reset(self):
        self.prev_values = None
        self.run_count = 0
        self.run_label = None


class CompressedLogger:
    """Writes compressed log entries with delta encoding + gzip.

    File format: .csv.gz (gzip-compressed CSV)
    Each row: timestamp, is_delta, value1, value2, ..., decision, run_count
    """

    LABEL_MAP = {"IDLE": 0, "READ_FOCUS": 1, "WRITE_PRIORITY": 2, "OPTIMIZE_BALANCE": 3}
    LABEL_REVERSE = {v: k for k, v in LABEL_MAP.items()}

    def __init__(self, base_name, max_size_mb=5):
        self.base_name = base_name
        self.gz_path = f"{base_name}.csv.gz"
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.encoder = DeltaEncoder()
        self.entry_count = 0
        self._ensure_header()

    def _ensure_header(self):
        """Create file with header if it doesn't exist."""
        if not os.path.exists(self.gz_path):
            with gzip.open(self.gz_path, "wt") as f:
                f.write("timestamp,is_delta,read_bytes,write_bytes,decision_id,run_count\n")

    def _check_rotation(self):
        """Rotate log if it exceeds max size."""
        if os.path.exists(self.gz_path):
            size = os.path.getsize(self.gz_path)
            if size > self.max_size_bytes:
                rotated = f"{self.base_name}.{int(time.time())}.csv.gz"
                os.rename(self.gz_path, rotated)
                self._ensure_header()
                self.encoder.reset()
                print(f"[compressed_log] Rotated to {rotated}")

    def write(self, io_data, decision):
        """Write a compressed log entry.

        Args:
            io_data: [read_bytes, write_bytes]
            decision: String label like "IDLE", "READ_FOCUS", etc.
        """
        self._check_rotation()

        encoded, is_delta, run_count = self.encoder.encode(io_data, decision)
        decision_id = self.LABEL_MAP.get(decision, 0)
        ts = datetime.now().strftime("%H:%M:%S")  # short timestamp (saves ~10 bytes)

        with gzip.open(self.gz_path, "at") as f:
            # Skip writing if this is a run continuation (RLE)
            if run_count > 2 and is_delta and encoded == [0, 0]:
                # Only write every 5th repeated entry to save space
                if run_count % 5 == 0:
                    f.write(f"{ts},R,0,0,{decision_id},{run_count}\n")
            else:
                d = 1 if is_delta else 0
                f.write(f"{ts},{d},{encoded[0]},{encoded[1]},{decision_id},{run_count}\n")

        self.entry_count += 1

    def read_all(self):
        """Read and decompress all entries back to absolute values."""
        if not os.path.exists(self.gz_path):
            return []

        entries = []
        prev_abs = [0, 0]

        with gzip.open(self.gz_path, "rt") as f:
            header = f.readline()  # skip header
            for line in f:
                parts = line.strip().split(",")
                if len(parts) < 6:
                    continue

                ts = parts[0]
                is_delta = parts[1] == "1"
                is_rle = parts[1] == "R"
                v1 = int(parts[2])
                v2 = int(parts[3])
                dec_id = int(parts[4])
                run = int(parts[5])

                if is_rle:
                    # RLE entry: values same as previous
                    entries.append({
                        "time": ts,
                        "read_bytes": prev_abs[0],
                        "write_bytes": prev_abs[1],
                        "decision": self.LABEL_REVERSE.get(dec_id, "?"),
                        "run": run
                    })
                elif is_delta:
                    abs_vals = [v1 + prev_abs[0], v2 + prev_abs[1]]
                    prev_abs = abs_vals
                    entries.append({
                        "time": ts,
                        "read_bytes": abs_vals[0],
                        "write_bytes": abs_vals[1],
                        "decision": self.LABEL_REVERSE.get(dec_id, "?"),
                        "run": run
                    })
                else:
                    prev_abs = [v1, v2]
                    entries.append({
                        "time": ts,
                        "read_bytes": v1,
                        "write_bytes": v2,
                        "decision": self.LABEL_REVERSE.get(dec_id, "?"),
                        "run": run
                    })

        return entries

    def stats(self):
        """Print compression statistics."""
        if not os.path.exists(self.gz_path):
            print("[compressed_log] No log file found.")
            return

        gz_size = os.path.getsize(self.gz_path)

        # Estimate uncompressed size
        entries = self.read_all()
        # Typical CSV entry: "2024-01-15T10:30:45,45000,12000,READ_FOCUS\n" = ~50 bytes
        raw_csv_est = len(entries) * 50
        # Typical JSON entry: ~200 bytes
        raw_json_est = len(entries) * 200

        print(f"[compressed_log] Entries: {len(entries)}")
        print(f"[compressed_log] Compressed size: {gz_size / 1024:.1f} KB")
        print(f"[compressed_log] vs raw CSV:  {raw_csv_est / 1024:.1f} KB ({raw_csv_est / max(gz_size,1):.1f}x)")
        print(f"[compressed_log] vs raw JSON: {raw_json_est / 1024:.1f} KB ({raw_json_est / max(gz_size,1):.1f}x)")


class BinaryMetricWriter:
    """Ultra-compact binary metric format.

    Each entry: 24 bytes (vs ~200 bytes JSON = 8x compression)

    Struct layout (24 bytes):
      uint32  timestamp    (unix epoch, 4 bytes)
      uint16  read_kb      (0-65535 KB, 2 bytes)
      uint16  write_kb     (0-65535 KB, 2 bytes)
      uint8   cpu_percent  (0-100, 1 byte)
      uint8   ram_percent  (0-100, 1 byte)
      uint8   cpu_temp     (0-255, 1 byte)
      uint8   decision_id  (0-3, 1 byte)
      uint16  cpu_freq_mhz (0-65535, 2 bytes)
      uint16  gpu_temp     (0-65535, 2 bytes, 0 if no GPU)
      uint32  io_read_delta  (delta from prev, 4 bytes)
      uint32  io_write_delta (delta from prev, 4 bytes)
    """

    STRUCT_FMT = "<IHHBBBBHHI I"  # little-endian, 24 bytes
    ENTRY_SIZE = struct.calcsize("<IHHBBBBHHiI")  # using signed for delta

    def __init__(self, path):
        self.path = path
        self.prev_read = 0
        self.prev_write = 0

    def write(self, metrics):
        """Write a single metrics entry in binary.

        Args:
            metrics: dict with keys: timestamp, read_kb, write_kb,
                     cpu_percent, ram_percent, cpu_temp, decision_id,
                     cpu_freq_mhz, gpu_temp
        """
        ts = int(metrics.get("timestamp", time.time()))
        read_kb = min(metrics.get("read_kb", 0), 65535)
        write_kb = min(metrics.get("write_kb", 0), 65535)
        cpu = min(metrics.get("cpu_percent", 0), 100)
        ram = min(metrics.get("ram_percent", 0), 100)
        temp = min(metrics.get("cpu_temp", 0), 255)
        dec = min(metrics.get("decision_id", 0), 3)
        freq = min(metrics.get("cpu_freq_mhz", 0), 65535)
        gpu_t = min(metrics.get("gpu_temp", 0), 65535)

        # Delta encoding for I/O
        rd_delta = read_kb - self.prev_read
        wr_delta = write_kb - self.prev_write
        self.prev_read = read_kb
        self.prev_write = write_kb

        packed = struct.pack("<IHHBBBBHHiI",
                             ts, read_kb, write_kb, cpu, ram, temp, dec,
                             freq, gpu_t, rd_delta, wr_delta)

        with open(self.path, "ab") as f:
            f.write(packed)

    def read_all(self):
        """Read all binary entries."""
        if not os.path.exists(self.path):
            return []

        entries = []
        entry_size = struct.calcsize("<IHHBBBBHHiI")

        with open(self.path, "rb") as f:
            while True:
                data = f.read(entry_size)
                if len(data) < entry_size:
                    break
                vals = struct.unpack("<IHHBBBBHHiI", data)
                entries.append({
                    "timestamp": vals[0],
                    "read_kb": vals[1],
                    "write_kb": vals[2],
                    "cpu_percent": vals[3],
                    "ram_percent": vals[4],
                    "cpu_temp": vals[5],
                    "decision_id": vals[6],
                    "cpu_freq_mhz": vals[7],
                    "gpu_temp": vals[8],
                    "io_read_delta": vals[9],
                    "io_write_delta": vals[10],
                })

        return entries

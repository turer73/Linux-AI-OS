"""
ai_lfs.py - AI Log File System engine

Reads I/O stats, runs AI inference, writes decisions to /dev/ai_ctl.

Inference backends (auto-detected in order):
  1. TFLite quantized (ai_model_q8.tflite) - fastest, smallest
  2. scikit-learn (ai_model.pkl) - lightweight, recommended
  3. PyTorch (ai_model.pt) - optional, heavier
  4. Rule-based fallback - zero dependencies

Compression features:
  - Delta encoding for I/O metrics (60-80% data reduction)
  - Gzip compressed logs (5-10x smaller on disk)
  - Run-length encoding for repeated decisions
"""

import time
import re
import os
import csv
import pickle
import psutil
from datetime import datetime

# Try to use compressed logging
try:
    from compressed_log import CompressedLogger
    USE_COMPRESSED_LOG = True
except ImportError:
    USE_COMPRESSED_LOG = False

# Paths
AI_DEVICE = "/dev/ai_ctl"
IO_STATS_PROC = "/proc/ai_status"
LOG_FILE = "ai_lfs_log"
TFLITE_MODEL_PATH = "ai_model_q8.tflite"
SKLEARN_MODEL_PATH = "ai_model.pkl"
TORCH_MODEL_PATH = "ai_model.pt"
SCALER_PATH = "ai_scaler.pkl"

# Decision labels
LABELS = ["IDLE", "READ_FOCUS", "WRITE_PRIORITY", "OPTIMIZE_BALANCE"]

# Resource limits for i7-M640 class hardware
MAX_MEMORY_MB = 200  # max RSS for this process
POLL_INTERVAL = 5    # seconds between cycles

# Initialize logger
if USE_COMPRESSED_LOG:
    _logger = CompressedLogger(LOG_FILE, max_size_mb=5)
else:
    _csv_path = f"{LOG_FILE}.csv"
    if not os.path.exists(_csv_path):
        with open(_csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "read_bytes", "write_bytes", "ai_decision"])


def log_decision(io_data, decision):
    if USE_COMPRESSED_LOG:
        _logger.write(io_data, decision)
    else:
        with open(f"{LOG_FILE}.csv", "a", newline="") as f:
            writer = csv.writer(f)
            timestamp = datetime.now().isoformat()
            writer.writerow([timestamp, io_data[0], io_data[1], decision])


def parse_io_stats(io_text):
    try:
        read_val = int(re.search(r"read:\s*(\d+)", io_text).group(1))
        write_val = int(re.search(r"write:\s*(\d+)", io_text).group(1))
        return [read_val, write_val]
    except (AttributeError, ValueError):
        return [0, 0]


def check_memory_usage():
    """Warn if process exceeds memory limit."""
    proc = psutil.Process(os.getpid())
    rss_mb = proc.memory_info().rss / (1024 * 1024)
    if rss_mb > MAX_MEMORY_MB:
        print(f"[AI-LFS] UYARI: Bellek kullanimi {rss_mb:.0f} MB (limit: {MAX_MEMORY_MB} MB)")
    return rss_mb


# --- Backend: TFLite quantized (fastest, smallest) ---

def load_tflite_model():
    if not os.path.exists(TFLITE_MODEL_PATH):
        return None, None
    try:
        try:
            import tflite_runtime.interpreter as tflite
        except ImportError:
            import tensorflow as tf
            tflite = tf.lite
        interpreter = tflite.Interpreter(model_path=TFLITE_MODEL_PATH)
        interpreter.allocate_tensors()
        with open(SCALER_PATH, "rb") as f:
            scaler = pickle.load(f)
        print("[AI-LFS] TFLite quantized model yuklendi (en hizli).")
        return interpreter, scaler
    except (ImportError, Exception) as e:
        print(f"[AI-LFS] TFLite yuklenemedi: {e}")
        return None, None


def predict_tflite(interpreter, scaler, stats):
    import numpy as np  # lazy: only loaded when tflite backend is active
    scaled = scaler.transform([stats]).astype(np.float32)
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    interpreter.set_tensor(input_details[0]['index'], scaled)
    interpreter.invoke()
    output = interpreter.get_tensor(output_details[0]['index'])[0]
    return LABELS[int(np.argmax(output))]


# --- Backend: scikit-learn (default, lightweight) ---

def load_sklearn_model():
    if not os.path.exists(SKLEARN_MODEL_PATH):
        return None, None
    try:
        with open(SKLEARN_MODEL_PATH, "rb") as f:
            model = pickle.load(f)
        with open(SCALER_PATH, "rb") as f:
            scaler = pickle.load(f)
        print("[AI-LFS] sklearn modeli yuklendi.")
        return model, scaler
    except Exception as e:
        print(f"[AI-LFS] sklearn model yukleme hatasi: {e}")
        return None, None


def predict_sklearn(model, scaler, stats):
    scaled = scaler.transform([stats])
    predicted = model.predict(scaled)[0]
    return LABELS[predicted]


# --- Backend: PyTorch (optional, heavy) ---

def load_torch_model():
    if not os.path.exists(TORCH_MODEL_PATH):
        return None, None
    try:
        import torch
        import torch.nn as nn

        class IOModel(nn.Module):
            def __init__(self, input_size=2, hidden_size=32, output_size=4):
                super(IOModel, self).__init__()
                self.lstm = nn.LSTM(input_size, hidden_size, batch_first=True)
                self.fc = nn.Linear(hidden_size, output_size)

            def forward(self, x):
                out, _ = self.lstm(x)
                out = self.fc(out[:, -1, :])
                return out

        model = IOModel(input_size=2, hidden_size=32, output_size=4)
        model.load_state_dict(torch.load(TORCH_MODEL_PATH, map_location="cpu"))
        model.eval()

        with open(SCALER_PATH, "rb") as f:
            scaler = pickle.load(f)

        print("[AI-LFS] PyTorch modeli yuklendi.")
        return model, scaler
    except ImportError:
        return None, None
    except Exception as e:
        print(f"[AI-LFS] torch model yukleme hatasi: {e}")
        return None, None


def predict_torch(model, scaler, stats):
    import torch
    scaled = scaler.transform([stats])
    tensor_in = torch.tensor(scaled, dtype=torch.float32).unsqueeze(0)
    output = model(tensor_in)
    predicted = torch.argmax(output, dim=1).item()
    return LABELS[predicted]


# --- Backend: Rule-based fallback (zero dependencies) ---

def predict_rules(stats):
    """Simple rule-based I/O classifier - no ML needed."""
    read_val, write_val = stats
    total = read_val + write_val

    if total < 2000:
        return "IDLE"
    elif read_val > write_val * 3:
        return "READ_FOCUS"
    elif write_val > read_val * 3:
        return "WRITE_PRIORITY"
    else:
        return "OPTIMIZE_BALANCE"


def collect_system_metrics():
    cpu_percent = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    try:
        load1, load5, load15 = psutil.getloadavg()
    except (AttributeError, OSError):
        load1 = load5 = load15 = 0.0
    return {
        "cpu_percent": cpu_percent,
        "mem_percent": mem.percent,
        "load_avg": [round(load1, 2), round(load5, 2), round(load15, 2)]
    }


def main_loop():
    print("[AI-LFS] AI LFS motoru baslatiliyor...")
    if USE_COMPRESSED_LOG:
        print("[AI-LFS] Sikistirilmis log aktif (delta + gzip)")

    # Auto-detect best available backend (fastest first)
    model, scaler = load_tflite_model()
    backend = "tflite"

    if model is None:
        model, scaler = load_sklearn_model()
        backend = "sklearn"

    if model is None:
        model, scaler = load_torch_model()
        backend = "torch"

    if model is None:
        print("[AI-LFS] Model bulunamadi, kural tabanli mod aktif.")
        backend = "rules"
    else:
        print(f"[AI-LFS] Backend: {backend}")

    rss = check_memory_usage()
    print(f"[AI-LFS] Baslangic bellek: {rss:.0f} MB")

    cycle_count = 0

    while True:
        try:
            # Read I/O stats
            if os.path.exists(IO_STATS_PROC):
                with open(IO_STATS_PROC, "r") as f:
                    stats_text = f.read()
                io_data = parse_io_stats(stats_text)
            else:
                # Fallback: use disk I/O from psutil
                disk = psutil.disk_io_counters()
                io_data = [disk.read_bytes % 100000, disk.write_bytes % 100000] if disk else [0, 0]

            # Run prediction
            if backend == "tflite":
                decision = predict_tflite(model, scaler, io_data)
            elif backend == "sklearn":
                decision = predict_sklearn(model, scaler, io_data)
            elif backend == "torch":
                decision = predict_torch(model, scaler, io_data)
            else:
                decision = predict_rules(io_data)

            # Write to device if available
            if os.path.exists(AI_DEVICE):
                with open(AI_DEVICE, "w") as f:
                    f.write(decision)

            print(f"[AI-LFS] IO: {io_data} -> {decision}")
            log_decision(io_data, decision)
            cycle_count += 1

            # Periodic metrics (every 3rd cycle to save CPU on 2-core)
            if cycle_count % 3 == 0:
                metrics = collect_system_metrics()
                print(f"[AI-LFS] CPU: {metrics['cpu_percent']}%, "
                      f"RAM: {metrics['mem_percent']}%, "
                      f"Load: {metrics['load_avg']}")

            # Compression stats every 20 cycles
            if USE_COMPRESSED_LOG and cycle_count % 20 == 0:
                _logger.stats()

            # Memory watchdog (every 5th cycle)
            if cycle_count % 5 == 0:
                check_memory_usage()

        except Exception as e:
            print(f"[AI-LFS] Hata: {e}")

        time.sleep(POLL_INTERVAL)


def main():
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\n[AI-LFS] Kapatiliyor...")
        if USE_COMPRESSED_LOG:
            _logger.flush()
            _logger.close()


if __name__ == "__main__":
    main()

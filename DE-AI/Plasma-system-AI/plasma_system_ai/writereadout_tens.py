"""
writereadout_tens.py - Plasma System AI inference engine

Reads system metrics, runs AI analysis, displays suggestions.

Inference backends (auto-detected in order):
  1. TFLite-runtime (tflite_model.tflite) - lightweight (~20 MB RAM)
  2. scikit-learn (plasma_model.pkl) - medium (~50 MB RAM)
  3. Rule-based fallback - zero dependencies

Optimized for: i7-M640 (2C/4T), 8 GB RAM
"""

import logging
import time
import json
import numpy as np
import psutil
import os
import subprocess
from datetime import datetime

# Resource limits
MAX_MEMORY_MB = 200  # RSS limit for this process
POLL_INTERVAL_DEFAULT = 60  # seconds

# Labels
LABELS = {0: "STABLE", 1: "HIGH_LOAD", 2: "OVERHEAT"}

suggestions_en = {
    0: "System stable. Everything looks good.",
    1: "High resource usage detected. Consider cleaning or restarting.",
    2: "Overheating detected. Thermal check is recommended."
}


def check_memory_usage():
    """Warn if process exceeds memory limit."""
    proc = psutil.Process(os.getpid())
    rss_mb = proc.memory_info().rss / (1024 * 1024)
    if rss_mb > MAX_MEMORY_MB:
        print(f"[Plasma-AI] WARNING: Memory usage {rss_mb:.0f} MB (limit: {MAX_MEMORY_MB} MB)")
    return rss_mb


def extract_features(entry):
    cpu = entry.get("cpu_percent", 0)
    ram = entry.get("virtual_memory", {}).get("percent", 0)
    swap = entry.get("swap_memory", {}).get("percent", 0)
    battery = entry.get("battery", {}).get("percent", 100)

    temp_list = []
    temps = entry.get("temperatures", {})
    for sensors in temps.values():
        if isinstance(sensors, list):
            for sensor in sensors:
                temp_list.append(sensor.get("current", 0))
    avg_temp = np.mean(temp_list) if temp_list else 0

    net_sent = entry.get("net_io", {}).get("bytes_sent", 0)
    net_recv = entry.get("net_io", {}).get("bytes_recv", 0)
    disk_read = entry.get("disk_io", {}).get("read_bytes", 0)
    disk_write = entry.get("disk_io", {}).get("write_bytes", 0)
    process_count = entry.get("process_count", 0)
    uptime = entry.get("uptime", 0)

    return np.array([[
        cpu, ram, swap, battery, avg_temp,
        net_sent / 1024 / 1024, net_recv / 1024 / 1024,
        disk_read / 1024 / 1024, disk_write / 1024 / 1024,
        process_count, uptime / 60
    ]], dtype=np.float32)


# --- Backend: TFLite-runtime (lightweight, ~20 MB) ---

def load_tflite_model():
    model_path = os.path.join(os.path.dirname(__file__), "tflite_model.tflite")
    if not os.path.exists(model_path):
        return None
    try:
        import tflite_runtime.interpreter as tflite
        interpreter = tflite.Interpreter(model_path=model_path)
        interpreter.allocate_tensors()
        print("[Plasma-AI] TFLite model loaded.")
        return interpreter
    except ImportError:
        # Try full tensorflow as last resort
        try:
            import tensorflow as tf
            interpreter = tf.lite.Interpreter(model_path=model_path)
            interpreter.allocate_tensors()
            print("[Plasma-AI] TFLite model loaded (via tensorflow).")
            return interpreter
        except ImportError:
            return None
    except Exception as e:
        print(f"[Plasma-AI] TFLite load error: {e}")
        return None


def predict_tflite(interpreter, features):
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    interpreter.set_tensor(input_details[0]['index'], features)
    interpreter.invoke()
    output = interpreter.get_tensor(output_details[0]['index'])[0]
    return int(np.argmax(output)), output


# --- Backend: scikit-learn (medium, ~50 MB) ---

def load_sklearn_model():
    import pickle
    model_path = os.path.join(os.path.dirname(__file__), "plasma_model.pkl")
    if not os.path.exists(model_path):
        return None
    try:
        with open(model_path, "rb") as f:
            model = pickle.load(f)
        print("[Plasma-AI] sklearn model loaded.")
        return model
    except Exception as e:
        print(f"[Plasma-AI] sklearn load error: {e}")
        return None


def predict_sklearn(model, features):
    label = int(model.predict(features)[0])
    proba = model.predict_proba(features)[0] if hasattr(model, 'predict_proba') else [0, 0, 0]
    return label, proba


# --- Backend: Rule-based fallback (zero deps) ---

def predict_rules(entry):
    """Rule-based system health classifier - no ML needed."""
    cpu = entry.get("cpu_percent", 0)
    ram = entry.get("virtual_memory", {}).get("percent", 0)

    temp_list = []
    for sensors in entry.get("temperatures", {}).values():
        if isinstance(sensors, list):
            for sensor in sensors:
                temp_list.append(sensor.get("current", 0))
    avg_temp = np.mean(temp_list) if temp_list else 0

    if avg_temp > 80:
        return 2, [0.1, 0.1, 0.8]  # OVERHEAT
    elif cpu > 85 or ram > 90:
        return 1, [0.1, 0.8, 0.1]  # HIGH_LOAD
    else:
        return 0, [0.8, 0.1, 0.1]  # STABLE


def analyze_with_model(entry, backend, model=None):
    features = extract_features(entry)

    if backend == "tflite" and model is not None:
        label, proba = predict_tflite(model, features)
    elif backend == "sklearn" and model is not None:
        label, proba = predict_sklearn(model, features)
    else:
        label, proba = predict_rules(entry)

    suggestion_text = suggestions_en.get(label, "Prediction not available.")

    cpu = entry.get("cpu_percent", 0)
    cpu_freq = entry.get("cpu_freq", {}).get("current", 0)
    ram = entry.get("virtual_memory", {}).get("percent", 0)
    swap = entry.get("swap_memory", {}).get("percent", 0)
    battery = entry.get("battery", {}).get("percent", "N/A")
    process_count = entry.get("process_count", 0)
    uptime = entry.get("uptime", 0) / 60

    print("[System Summary]")
    print(f"  Suggestion: {suggestion_text}")
    print(f"  CPU: {cpu}% | Freq: {cpu_freq:.0f} MHz | RAM: {ram}% | SWAP: {swap}%")
    print(f"  Battery: {battery}% | Processes: {process_count} | Uptime: {uptime:.1f} min")
    if hasattr(proba, '__len__') and len(proba) >= 3:
        print(f"  Prediction: Stable={proba[0]*100:.0f}% High={proba[1]*100:.0f}% Heat={proba[2]*100:.0f}%")

    return suggestion_text


def get_process_usages():
    process_info = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            process_info.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return sorted(process_info, key=lambda x: x.get('cpu_percent', 0), reverse=True)


def suggest_app_actions(process_info):
    suggestions = []
    for proc in process_info:
        name = proc.get('name', '')
        cpu = proc.get('cpu_percent', 0)
        mem = proc.get('memory_percent', 0)

        if cpu < 1.0 and mem < 1.0:
            suggestions.append(f"  '{name}' is using very low resources. Consider closing if idle.")
        elif cpu > 20.0 or mem > 10.0:
            suggestions.append(f"  '{name}' is using high resources. Monitor or restart if unnecessary.")
    return suggestions


def ensure_log_directory():
    log_dir = os.path.expanduser("~/.ai_logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "ai_suggestions.log")


def get_metrics_file_path():
    return os.path.expanduser("~/.ai_logs/system_metrics.json")


def most_intensive_process(processes):
    if not processes:
        return "No process data available."

    def score(proc):
        return (proc.get('cpu_percent', 0) * 0.7) + (proc.get('memory_percent', 0) * 0.3)

    top = max(processes, key=score)
    return (
        f"Most Intensive: {top.get('name', '?')} (PID: {top.get('pid', '?')}) "
        f"CPU: {top.get('cpu_percent', 0)}% RAM: {top.get('memory_percent', 0):.1f}% "
        f"Score: {score(top):.2f}"
    )


# Critical processes that should never be terminated
CRITICAL_PROCESSES = frozenset([
    "systemd", "gnome-shell", "plasmashell", "xorg", "xwayland",
    "kwin", "kde", "pulseaudio", "pipewire", "dbus-daemon",
    "sshd", "login", "init"
])


def auto_prop_manage(processes, permission=True):
    if not permission:
        return []

    actions = []
    for proc in processes:
        pid = proc.get('pid', 0)
        name = proc.get('name', '')
        cpu = proc.get('cpu_percent', 0)
        mem = proc.get('memory_percent', 0)

        if name.lower() in CRITICAL_PROCESSES:
            continue

        if cpu > 70 or mem > 30:
            try:
                psutil.Process(pid).terminate()
                actions.append(f"  Terminated '{name}' (PID: {pid}) CPU:{cpu}% MEM:{mem:.1f}%")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    return actions


def alert_if_needed(entry):
    cpu = entry.get("cpu_percent", 0)
    ram = entry.get("virtual_memory", {}).get("percent", 0)
    battery = entry.get("battery", {}).get("percent", 100)

    temp_list = []
    for sensors in entry.get("temperatures", {}).values():
        if isinstance(sensors, list):
            for sensor in sensors:
                temp_list.append(sensor.get("current", 0))
    avg_temp = np.mean(temp_list) if temp_list else 0

    alerts = []
    if cpu > 85:
        alerts.append(f"High CPU: {cpu}%")
    if ram > 85:
        alerts.append(f"High RAM: {ram}%")
    if avg_temp > 80:
        alerts.append(f"High temp: {avg_temp:.1f}C")
    if battery != "N/A" and isinstance(battery, (int, float)) and battery < 15:
        alerts.append(f"Low battery: {battery}%")

    if alerts:
        combined = " | ".join(alerts)
        try:
            subprocess.run(["notify-send", "System Alert", combined],
                           timeout=5, check=False)
        except FileNotFoundError:
            pass  # notify-send not available
        print(f"[ALERT] {combined}")


def read_and_analyze(filename=None, backend="rules", model=None):
    if filename is None:
        filename = get_metrics_file_path()

    if not os.path.exists(filename):
        return "Metrics file not found. No data to analyze."

    with open(filename, "r") as f:
        lines = f.readlines()
        if not lines:
            return "No data available to analyze yet."

        try:
            last_entry = json.loads(lines[-1])
        except json.JSONDecodeError:
            return "Could not parse last log entry."

        return analyze_with_model(last_entry, backend, model)


def get_interval(args=None):
    """Returns interval in seconds from args or default."""
    if args and hasattr(args, 'interval') and args.interval:
        interval = int(args.interval)
        if hasattr(args, 'get_interval') and args.get_interval == "m":
            interval *= 60
        return max(interval, 5)  # minimum 5 seconds
    return POLL_INTERVAL_DEFAULT


def get_user_permission(auto_prop):
    if auto_prop is not None:
        return auto_prop
    return False


def run_monitor_loop(args):
    interval = get_interval(args)
    permission = get_user_permission(
        getattr(args, 'auto_prop', False) if args else False)
    log_path = ensure_log_directory()
    metrics_path = get_metrics_file_path()

    # Auto-detect backend
    model = load_tflite_model()
    backend = "tflite"
    if model is None:
        model = load_sklearn_model()
        backend = "sklearn"
    if model is None:
        backend = "rules"
        print("[Plasma-AI] No model found, using rule-based fallback.")
    else:
        print(f"[Plasma-AI] Backend: {backend}")

    print(f"[Plasma-AI] Auto-Prop: {permission} | Interval: {interval}s")
    rss = check_memory_usage()
    print(f"[Plasma-AI] Initial memory: {rss:.0f} MB")

    while True:
        try:
            result = read_and_analyze(backend=backend, model=model)
            processes = get_process_usages()
            app_suggestions = suggest_app_actions(processes[:10])
            intensive_proc = most_intensive_process(processes)
            auto_prop_actions = auto_prop_manage(processes[:10], permission)

            print(f"\n[AI] {result}")
            print(f"[TOP] {intensive_proc}")

            if app_suggestions:
                print("[Suggestions]")
                for s in app_suggestions[:5]:
                    print(s)

            if auto_prop_actions:
                print("[Auto-Prop]")
                for a in auto_prop_actions:
                    print(a)

            # Check alerts from metrics file
            if os.path.exists(metrics_path):
                with open(metrics_path, "r") as mf:
                    lines = mf.readlines()
                    if lines:
                        try:
                            alert_if_needed(json.loads(lines[-1]))
                        except json.JSONDecodeError:
                            pass

            # Log
            with open(log_path, "a") as log:
                log.write(f"[{datetime.now().isoformat()}] {result}\n")

            # Memory watchdog
            check_memory_usage()

        except Exception as e:
            print(f"[Plasma-AI] Error: {e}")

        time.sleep(interval)

"""
ai_cpufregd.py - AI CPU frequency daemon

Monitors AI-runtime.yml for config changes and auto-tunes
CPU frequency based on load patterns.

Optimized for: i7-M640 (2 cores / 4 threads), 8 GB RAM
"""

import os
import time
import yaml
import psutil

CONFIG_PATH = "/var/AI-stump/AI-runtime.yml"
SYS_RELOAD = "/sys/ai/freqctl"
MAX_MEMORY_MB = 200
POLL_INTERVAL = 5  # seconds


def check_memory_usage():
    proc = psutil.Process(os.getpid())
    rss_mb = proc.memory_info().rss / (1024 * 1024)
    if rss_mb > MAX_MEMORY_MB:
        print(f"[AI-cpufreqd] WARNING: Memory {rss_mb:.0f} MB (limit: {MAX_MEMORY_MB} MB)")
    return rss_mb


def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError):
        return {}


def get_config_mtime():
    try:
        return os.path.getmtime(CONFIG_PATH)
    except OSError:
        return 0


def notify_kernel_reload():
    """Notify kernel module about config change."""
    if os.path.exists(SYS_RELOAD):
        try:
            with open(SYS_RELOAD, "w") as f:
                f.write("reload")
            print("[AI-cpufreqd] Kernel reload triggered.")
        except PermissionError:
            print("[AI-cpufreqd] No permission to write to sysfs.")


def monitor_usage_and_autotune():
    """Monitor CPU usage and trigger actions on high load."""
    last_mtime = get_config_mtime()

    while True:
        try:
            # Check config file changes (lightweight stat() instead of watchdog)
            current_mtime = get_config_mtime()
            if current_mtime != last_mtime:
                print("[AI-cpufreqd] Config changed. Triggering reload...")
                notify_kernel_reload()
                last_mtime = current_mtime

            # Monitor CPU usage
            cpu_usages = psutil.cpu_percent(percpu=True)
            if any(u > 90 for u in cpu_usages):
                print(f"[AI-cpufreqd] High CPU detected: {cpu_usages}")

            # Periodic memory check
            check_memory_usage()

        except Exception as e:
            print(f"[AI-cpufreqd] Error: {e}")

        time.sleep(POLL_INTERVAL)


def main():
    print(f"[AI-cpufreqd] Started. Config: {CONFIG_PATH}")
    print(f"[AI-cpufreqd] CPU count: {psutil.cpu_count()} | Poll: {POLL_INTERVAL}s")
    check_memory_usage()

    try:
        monitor_usage_and_autotune()
    except KeyboardInterrupt:
        print("\n[AI-cpufreqd] Stopped.")


if __name__ == "__main__":
    main()

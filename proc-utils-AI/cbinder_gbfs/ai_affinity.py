"""
ai_affinity.py - AI-driven CPU core affinity manager

Assigns processes to specific CPU cores based on runtime profile.
Optimized for: i7-M640 (2 cores / 4 threads), 8 GB RAM
"""

import psutil
import os
import yaml
import time
import subprocess

RUNTIME_PROFILE = "/var/AI-stump/AI-runtime.yml"
MAX_MEMORY_MB = 200
POLL_INTERVAL = 10  # seconds (increased from 5 for 2-core system)


def check_memory_usage():
    proc = psutil.Process(os.getpid())
    rss_mb = proc.memory_info().rss / (1024 * 1024)
    if rss_mb > MAX_MEMORY_MB:
        print(f"[ai-affinity] WARNING: Memory {rss_mb:.0f} MB (limit: {MAX_MEMORY_MB} MB)")
    return rss_mb


def load_runtime_config():
    try:
        with open(RUNTIME_PROFILE, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"[ai-affinity] Config not found: {RUNTIME_PROFILE}")
        return {}
    except yaml.YAMLError as e:
        print(f"[ai-affinity] YAML parse error: {e}")
        return {}


def safe_renice(pid, nice_val):
    """Set process priority without shell injection risk."""
    nice_val = max(-20, min(19, int(nice_val)))
    pid = int(pid)
    try:
        subprocess.run(
            ["renice", "-n", str(nice_val), "-p", str(pid)],
            capture_output=True, timeout=5, check=False
        )
    except FileNotFoundError:
        # renice not available, try psutil
        try:
            psutil.Process(pid).nice(nice_val)
        except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError):
            pass


def apply_affinity():
    config = load_runtime_config()
    if not config:
        return

    cpu_count = psutil.cpu_count()
    affinity_cfg = config.get("affinity", {})

    for proc in psutil.process_iter(attrs=['pid', 'name']):
        try:
            pname = proc.info['name']
            pid = proc.info['pid']

            if pname in affinity_cfg:
                rule = affinity_cfg[pname]
                if not isinstance(rule, dict):
                    continue

                cores = rule.get("cores", [])
                nice = rule.get("nice")

                if cores and isinstance(cores, list):
                    # Validate core numbers
                    valid_cores = [c for c in cores if isinstance(c, int) and 0 <= c < cpu_count]
                    if valid_cores:
                        proc.cpu_affinity(valid_cores)
                        print(f"[ai-affinity] {pname} -> cores: {valid_cores}")

                if nice is not None:
                    safe_renice(pid, nice)
                    print(f"[ai-affinity] {pname} -> nice: {nice}")

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def main():
    print(f"[ai-affinity] Started. CPU count: {psutil.cpu_count()} | Poll: {POLL_INTERVAL}s")
    check_memory_usage()

    while True:
        try:
            apply_affinity()
            check_memory_usage()
        except Exception as e:
            print(f"[ai-affinity] Error: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[ai-affinity] Stopped.")

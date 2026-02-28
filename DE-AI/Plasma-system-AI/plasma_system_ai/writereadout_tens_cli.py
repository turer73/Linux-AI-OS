"""
writereadout_tens_cli.py - CLI for Plasma System AI Monitor

Usage:
  plasma-system-ai --analyze       # One-shot analysis
  plasma-system-ai --loop          # Continuous monitoring
  plasma-system-ai --loop -i 30    # Every 30 seconds
  plasma-system-ai --suggest       # Process suggestions
"""

import argparse
import time
import subprocess
from datetime import datetime
from writereadout_tens import (
    read_and_analyze,
    get_process_usages,
    suggest_app_actions,
    most_intensive_process,
    auto_prop_manage,
    ensure_log_directory,
    run_monitor_loop,
    load_tflite_model,
    load_sklearn_model,
    check_memory_usage,
)


def log_results(log_path, result, suggestions):
    with open(log_path, "a") as log:
        log.write(f"[{datetime.now().isoformat()}] {result}\n")
        for s in suggestions:
            log.write(f"  {s}\n")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Plasma System AI Monitor")
    parser.add_argument("--interval", "-i", type=int, default=60,
                        help="Monitoring interval in seconds (default: 60)")
    parser.add_argument("--get-interval", choices=["s", "m"],
                        help="Time unit: s for seconds, m for minutes")
    parser.add_argument("--auto-prop", "-a", action="store_true",
                        help="Enable automatic process management")
    parser.add_argument("--analyze", "-z", action="store_true",
                        help="Analyze latest system metrics")
    parser.add_argument("--most-intensive", "-m", action="store_true",
                        help="Show most resource-intensive process")
    parser.add_argument("--suggest", "-s", action="store_true",
                        help="Suggest actions for top processes")
    parser.add_argument("--loop", "-l", action="store_true",
                        help="Run continuous monitoring loop")
    return parser.parse_args()


def main():
    args = parse_arguments()

    # Handle interval unit conversion
    if args.get_interval == "m":
        args.interval *= 60

    # Detect backend
    model = load_tflite_model()
    backend = "tflite"
    if model is None:
        model = load_sklearn_model()
        backend = "sklearn"
    if model is None:
        backend = "rules"
        print("[Plasma-AI] Using rule-based fallback (no model found).")
    else:
        print(f"[Plasma-AI] Backend: {backend}")

    log_path = ensure_log_directory()
    processes = get_process_usages()

    if args.analyze:
        result = read_and_analyze(backend=backend, model=model)
        print(f"\n[AI] {result}\n")
        try:
            subprocess.run(["notify-send", "Plasma System AI", str(result)],
                           timeout=5, check=False)
        except FileNotFoundError:
            pass
    else:
        result = "No analysis run."

    if args.most_intensive:
        print(f"\n{most_intensive_process(processes)}")

    if args.suggest:
        print("\n[Suggestions]")
        for s in suggest_app_actions(processes[:10]):
            print(s)

    if args.auto_prop:
        print("[Auto-Prop] Active.")
        actions = auto_prop_manage(processes, permission=True)
        for a in actions:
            print(a)

    log_results(log_path, result, suggest_app_actions(processes[:10]) if args.suggest else [])

    if args.loop:
        print(f"\n[Plasma-AI] Starting monitor loop (interval: {args.interval}s)...")
        run_monitor_loop(args)
    else:
        print(f"[Plasma-AI] Interval: {args.interval}s (use --loop to activate continuous monitoring)")

    check_memory_usage()


if __name__ == "__main__":
    main()

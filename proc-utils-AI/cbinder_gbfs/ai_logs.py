"""
ai_logs.py - Centralized log aggregation and viewer for Linux-AI

Collects logs from all Linux-AI components into a unified view.
Supports filtering, searching, tailing, and exporting.

Log sources:
  - /var/AI-stump/ai-agent.log       (Agent operations)
  - /var/AI-stump/ai-monitor.log      (System monitoring)
  - /var/AI-stump/ai-backup.log       (Backup operations)
  - /var/AI-stump/ai-webops.log       (Web operations)
  - /var/log/syslog / journalctl      (System + kernel module)
  - Custom paths from config

Usage:
  ai-logs tail                       # Live tail all logs
  ai-logs view                       # View recent logs (last 100 lines)
  ai-logs view --source agent        # Filter by source
  ai-logs view --level error         # Filter by level
  ai-logs search "pattern"           # Search across all logs
  ai-logs stats                      # Log statistics summary
  ai-logs export [--format json]     # Export logs
  ai-logs clean [--days 30]          # Clean old logs
"""

import os
import sys
import re
import json
import glob
import argparse
from datetime import datetime, timedelta
from collections import defaultdict

# --- Constants ---

TAG = "[ai-logs]"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"

LOG_DIR = "/var/AI-stump"

# Source name -> log file path
LOG_SOURCES = {
    "agent":   os.path.join(LOG_DIR, "ai-agent.log"),
    "monitor": os.path.join(LOG_DIR, "ai-monitor.log"),
    "backup":  os.path.join(LOG_DIR, "ai-backup.log"),
    "webops":  os.path.join(LOG_DIR, "ai-webops.log"),
    "deploy":  os.path.join(LOG_DIR, "deploy.log"),
}

# Regex to parse standard log lines: [2025-01-15 10:30:45] [INFO] message
LOG_PATTERN = re.compile(
    r"\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s*\[(\w+)\]\s*(.*)"
)

LEVEL_COLORS = {
    "DEBUG": DIM,
    "INFO": GREEN,
    "WARN": YELLOW,
    "WARNING": YELLOW,
    "ERROR": RED,
    "CRITICAL": RED,
}

LEVEL_PRIORITY = {
    "DEBUG": 0,
    "INFO": 1,
    "WARN": 2,
    "WARNING": 2,
    "ERROR": 3,
    "CRITICAL": 4,
}


# --- Utility ---

def info(msg):
    print(f"{GREEN}{TAG}{NC} {msg}")


def warn(msg):
    print(f"{YELLOW}{TAG}{NC} {msg}")


def error(msg):
    print(f"{RED}{TAG}{NC} {msg}")


# --- Log Entry ---

class LogEntry:
    """Parsed log entry."""
    __slots__ = ("timestamp", "level", "message", "source", "raw")

    def __init__(self, timestamp, level, message, source, raw):
        self.timestamp = timestamp
        self.level = level.upper()
        self.message = message
        self.source = source
        self.raw = raw

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "message": self.message,
            "source": self.source,
        }


def parse_log_line(line, source=""):
    """Parse a log line into a LogEntry."""
    line = line.rstrip("\n\r")
    if not line:
        return None

    match = LOG_PATTERN.match(line)
    if match:
        ts, level, message = match.groups()
        return LogEntry(ts, level, message, source, line)

    # Fallback: unstructured log line
    return LogEntry("", "INFO", line, source, line)


# --- Log Reading ---

def read_log_file(filepath, source_name, limit=0, level_filter="", search=""):
    """Read and parse a log file. Returns list of LogEntry."""
    if not os.path.exists(filepath):
        return []

    entries = []
    min_priority = LEVEL_PRIORITY.get(level_filter.upper(), 0) if level_filter else 0

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        # Read from end if limit specified
        if limit > 0:
            lines = lines[-limit:]

        for line in lines:
            entry = parse_log_line(line, source_name)
            if entry is None:
                continue

            # Level filter
            if level_filter:
                entry_priority = LEVEL_PRIORITY.get(entry.level, 1)
                if entry_priority < min_priority:
                    continue

            # Search filter
            if search and search.lower() not in entry.message.lower():
                continue

            entries.append(entry)

    except (IOError, PermissionError) as e:
        error(f"{filepath} okunamadi: {e}")

    return entries


def collect_all_logs(sources=None, limit=0, level_filter="", search=""):
    """Collect logs from all sources, merge and sort by timestamp."""
    all_entries = []

    targets = LOG_SOURCES
    if sources:
        targets = {k: v for k, v in LOG_SOURCES.items() if k in sources}

    for source_name, filepath in targets.items():
        entries = read_log_file(filepath, source_name, limit=limit,
                                level_filter=level_filter, search=search)
        all_entries.extend(entries)

    # Also check for extra log files
    extra_logs = glob.glob(os.path.join(LOG_DIR, "*.log"))
    known_paths = set(LOG_SOURCES.values())
    for logpath in extra_logs:
        if logpath not in known_paths:
            basename = os.path.basename(logpath).replace(".log", "")
            if sources and basename not in sources:
                continue
            entries = read_log_file(logpath, basename, limit=limit,
                                    level_filter=level_filter, search=search)
            all_entries.extend(entries)

    # Sort by timestamp
    all_entries.sort(key=lambda e: e.timestamp or "")

    return all_entries


# --- Display ---

def format_entry(entry, show_source=True):
    """Format a log entry for terminal display."""
    color = LEVEL_COLORS.get(entry.level, NC)
    source_str = f"{DIM}[{entry.source:8s}]{NC} " if show_source else ""

    if entry.timestamp:
        ts_short = entry.timestamp[11:19]  # HH:MM:SS
        date_str = entry.timestamp[:10]
        return (f"{DIM}{date_str} {ts_short}{NC} "
                f"{source_str}"
                f"{color}[{entry.level:5s}]{NC} "
                f"{entry.message}")
    else:
        return f"{source_str}{color}{entry.message}{NC}"


def print_entries(entries, show_source=True):
    """Print log entries to terminal."""
    for entry in entries:
        print(format_entry(entry, show_source))


# --- Commands ---

def cmd_view(args):
    """View recent logs."""
    sources = [args.source] if args.source else None
    limit_per_file = args.lines or 100

    entries = collect_all_logs(
        sources=sources,
        limit=limit_per_file,
        level_filter=args.level or "",
        search=""
    )

    if not entries:
        warn("Log kaydi bulunamadi.")
        return

    # Apply total limit
    total_limit = args.lines or 100
    if len(entries) > total_limit:
        entries = entries[-total_limit:]

    show_source = args.source is None
    print(f"\n{BOLD}--- Linux-AI Loglar (son {len(entries)} satir) ---{NC}\n")
    print_entries(entries, show_source=show_source)
    print("")


def cmd_tail(args):
    """Live tail of log files (poll-based)."""
    import time

    sources = [args.source] if args.source else None
    info("Log takibi baslatildi (Ctrl+C ile dur)...")

    # Track file positions
    positions = {}
    for name, path in LOG_SOURCES.items():
        if sources and name not in sources:
            continue
        if os.path.exists(path):
            positions[name] = (path, os.path.getsize(path))

    try:
        while True:
            for name, (path, last_pos) in list(positions.items()):
                if not os.path.exists(path):
                    continue

                current_size = os.path.getsize(path)
                if current_size > last_pos:
                    try:
                        with open(path, "r", encoding="utf-8", errors="replace") as f:
                            f.seek(last_pos)
                            new_lines = f.readlines()

                        for line in new_lines:
                            entry = parse_log_line(line, name)
                            if entry:
                                if args.level:
                                    ep = LEVEL_PRIORITY.get(entry.level, 1)
                                    mp = LEVEL_PRIORITY.get(args.level.upper(), 0)
                                    if ep < mp:
                                        continue
                                print(format_entry(entry))

                        positions[name] = (path, current_size)

                    except (IOError, PermissionError):
                        pass
                elif current_size < last_pos:
                    # File was truncated/rotated
                    positions[name] = (path, 0)

            time.sleep(1)

    except KeyboardInterrupt:
        info("Log takibi durduruldu.")


def cmd_search(args):
    """Search across all logs."""
    pattern = args.pattern
    if not pattern:
        error("Arama deseni gerekli.")
        return

    info(f'Araniyor: "{pattern}"')

    entries = collect_all_logs(search=pattern)

    if not entries:
        warn("Eslesme bulunamadi.")
        return

    print(f"\n{BOLD}--- Arama Sonuclari: \"{pattern}\" ({len(entries)} eslesme) ---{NC}\n")
    print_entries(entries)
    print("")


def cmd_stats(args):
    """Show log statistics summary."""
    print(f"\n{BOLD}{'=' * 55}{NC}")
    print(f"{BOLD}  Linux-AI Log Istatistikleri{NC}")
    print(f"{BOLD}{'=' * 55}{NC}\n")

    total_lines = 0
    total_size = 0
    level_counts = defaultdict(int)
    source_counts = defaultdict(int)

    for source_name, filepath in LOG_SOURCES.items():
        if not os.path.exists(filepath):
            print(f"  {DIM}{source_name:12s}: dosya yok{NC}")
            continue

        size = os.path.getsize(filepath)
        total_size += size

        entries = read_log_file(filepath, source_name)
        count = len(entries)
        total_lines += count
        source_counts[source_name] = count

        for entry in entries:
            level_counts[entry.level] += 1

        size_str = _human_size(size)
        print(f"  {CYAN}{source_name:12s}{NC}: {count:>6} satir  ({size_str})")

    print(f"\n  {BOLD}Toplam:{NC} {total_lines} satir ({_human_size(total_size)})")

    if level_counts:
        print(f"\n  {BOLD}Seviye Dagilimi:{NC}")
        for level in ["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"]:
            count = level_counts.get(level, 0)
            if count > 0:
                color = LEVEL_COLORS.get(level, NC)
                bar_len = min(count * 40 // max(total_lines, 1), 40)
                bar = "█" * bar_len
                print(f"    {color}{level:8s}{NC} {count:>6}  {color}{bar}{NC}")

    # Recent errors
    error_entries = collect_all_logs(level_filter="ERROR", limit=50)
    if error_entries:
        recent_errors = error_entries[-5:]
        print(f"\n  {RED}Son Hatalar ({len(error_entries)} toplam):{NC}")
        for entry in recent_errors:
            print(f"    {DIM}{entry.timestamp}{NC} [{entry.source}] {entry.message[:70]}")

    print(f"\n{'=' * 55}\n")


def cmd_export(args):
    """Export logs to JSON or plain text."""
    fmt = args.format or "json"
    output = args.output

    entries = collect_all_logs(
        sources=[args.source] if args.source else None,
        level_filter=args.level or "",
    )

    if not entries:
        warn("Aktarilacak log bulunamadi.")
        return

    if fmt == "json":
        data = [e.to_dict() for e in entries]
        content = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        lines = [format_entry(e, show_source=True) for e in entries]
        # Strip ANSI codes for plain text
        ansi_escape = re.compile(r'\033\[[0-9;]*m')
        content = "\n".join(ansi_escape.sub("", l) for l in lines)

    if output:
        try:
            with open(output, "w", encoding="utf-8") as f:
                f.write(content)
            info(f"Loglar aktarildi: {output} ({len(entries)} kayit)")
        except (IOError, PermissionError) as e:
            error(f"Dosya yazilamadi: {e}")
    else:
        print(content)


def cmd_clean(args):
    """Clean old log entries."""
    days = args.days or 30
    cutoff = datetime.now() - timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    info(f">{days} gunluk loglar temizleniyor (< {cutoff_str[:10]})...")

    total_removed = 0

    for source_name, filepath in LOG_SOURCES.items():
        if not os.path.exists(filepath):
            continue

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            original = len(lines)
            kept = []
            for line in lines:
                entry = parse_log_line(line, source_name)
                if entry and entry.timestamp:
                    if entry.timestamp >= cutoff_str:
                        kept.append(line)
                else:
                    kept.append(line)

            removed = original - len(kept)
            total_removed += removed

            if removed > 0:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.writelines(kept)
                info(f"  {source_name}: {removed} satir silindi")

        except (IOError, PermissionError) as e:
            warn(f"  {source_name}: temizlenemedi ({e})")

    info(f"Toplam: {total_removed} satir temizlendi.")


# --- Helpers ---

def _human_size(size_bytes):
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


# --- CLI ---

def build_parser():
    parser = argparse.ArgumentParser(
        prog="ai-logs",
        description="Linux-AI: Merkezi log toplama ve goruntuleme"
    )
    sub = parser.add_subparsers(dest="command", help="Alt komutlar")

    # view
    p_view = sub.add_parser("view", help="Son loglari goruntule")
    p_view.add_argument("-n", "--lines", type=int, default=100,
                        help="Gosterilecek satir sayisi (varsayilan: 100)")
    p_view.add_argument("-s", "--source",
                        choices=list(LOG_SOURCES.keys()),
                        help="Kaynak filtresi")
    p_view.add_argument("-l", "--level",
                        choices=["debug", "info", "warn", "error", "critical"],
                        help="Minimum log seviyesi")
    p_view.set_defaults(func=cmd_view)

    # tail
    p_tail = sub.add_parser("tail", help="Canli log takibi")
    p_tail.add_argument("-s", "--source",
                        choices=list(LOG_SOURCES.keys()),
                        help="Kaynak filtresi")
    p_tail.add_argument("-l", "--level",
                        choices=["debug", "info", "warn", "error", "critical"],
                        help="Minimum log seviyesi")
    p_tail.set_defaults(func=cmd_tail)

    # search
    p_search = sub.add_parser("search", help="Loglarda ara")
    p_search.add_argument("pattern", help="Arama deseni")
    p_search.set_defaults(func=cmd_search)

    # stats
    p_stats = sub.add_parser("stats", help="Log istatistikleri")
    p_stats.set_defaults(func=cmd_stats)

    # export
    p_export = sub.add_parser("export", help="Loglari aktar")
    p_export.add_argument("-f", "--format", choices=["json", "text"],
                          default="json", help="Cikti formati")
    p_export.add_argument("-o", "--output", help="Cikti dosyasi")
    p_export.add_argument("-s", "--source",
                          choices=list(LOG_SOURCES.keys()),
                          help="Kaynak filtresi")
    p_export.add_argument("-l", "--level",
                          choices=["debug", "info", "warn", "error", "critical"],
                          help="Minimum log seviyesi")
    p_export.set_defaults(func=cmd_export)

    # clean
    p_clean = sub.add_parser("clean", help="Eski loglari temizle")
    p_clean.add_argument("-d", "--days", type=int, default=30,
                         help="Kac gunluk loglar tutulusu (varsayilan: 30)")
    p_clean.set_defaults(func=cmd_clean)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        # Default: stats
        cmd_stats(args)
        return

    args.func(args)


if __name__ == "__main__":
    main()

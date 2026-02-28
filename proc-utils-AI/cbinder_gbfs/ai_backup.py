"""
ai_backup.py - Automated backup tool for Linux-AI

Backs up configuration files, Supabase databases, and Coolify resources.
Supports local and remote (S3-compatible) storage targets.

Backup targets:
  - /var/AI-stump/ config files (YAML, logs)
  - Supabase project database dumps (via management API)
  - Coolify application configs
  - Custom paths from backup config

Usage:
  ai-backup run                  # Run all configured backups
  ai-backup config               # Backup config files only
  ai-backup supabase             # Dump Supabase databases
  ai-backup coolify              # Backup Coolify app configs
  ai-backup list                 # List existing backups
  ai-backup restore <archive>    # Restore from backup archive
  ai-backup cron [--enable|--disable]  # Manage daily cron job
"""

import os
import sys
import json
import glob
import shutil
import tarfile
import argparse
import subprocess
from datetime import datetime, timedelta

import yaml

# --- Constants ---

TAG = "[ai-backup]"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"

CONFIG_DIR = "/var/AI-stump"
BACKUP_DIR = "/var/AI-stump/backups"
BACKUP_CONFIG_PATH = "/var/AI-stump/ai-backup.yml"
LOG_PATH = "/var/AI-stump/ai-backup.log"
CRON_MARKER = "# ai-backup-daily"

DEFAULT_CONFIG = {
    "backup_dir": BACKUP_DIR,
    "retention_days": 7,
    "compress": True,
    "paths": [
        "/var/AI-stump/*.yml",
        "/var/AI-stump/*.yaml",
    ],
    "exclude_patterns": [
        "*.log",
        "backups/",
    ],
    "supabase": {
        "enabled": False,
        "projects": [],  # Auto-detect from API
    },
    "coolify": {
        "enabled": False,
    },
}


# --- Utility ---

def info(msg):
    print(f"{GREEN}{TAG}{NC} {msg}")


def warn(msg):
    print(f"{YELLOW}{TAG}{NC} {msg}")


def error(msg):
    print(f"{RED}{TAG}{NC} {msg}")


def log_event(level, message):
    """Append event to backup log file."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] [{level}] {message}\n"
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a") as f:
            f.write(entry)
    except (IOError, PermissionError):
        pass


def load_backup_config():
    """Load backup configuration from YAML."""
    try:
        if os.path.exists(BACKUP_CONFIG_PATH):
            with open(BACKUP_CONFIG_PATH, "r") as f:
                user_cfg = yaml.safe_load(f) or {}
            # Merge with defaults
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(user_cfg)
            return cfg
    except (yaml.YAMLError, IOError) as e:
        warn(f"Config yuklenemedi: {e}")
    return DEFAULT_CONFIG.copy()


def get_backup_dir(cfg):
    """Ensure backup directory exists and return path."""
    backup_dir = cfg.get("backup_dir", BACKUP_DIR)
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


def timestamp_str():
    """Return a timestamp string for filenames."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def human_size(size_bytes):
    """Convert bytes to human readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


# --- Config Backup ---

def backup_configs(cfg):
    """Backup all configuration files from /var/AI-stump/."""
    backup_dir = get_backup_dir(cfg)
    ts = timestamp_str()
    archive_name = f"config-backup-{ts}.tar.gz"
    archive_path = os.path.join(backup_dir, archive_name)

    paths = cfg.get("paths", DEFAULT_CONFIG["paths"])
    exclude = cfg.get("exclude_patterns", DEFAULT_CONFIG["exclude_patterns"])
    files_to_backup = []

    for pattern in paths:
        matched = glob.glob(pattern, recursive=True)
        for fpath in matched:
            skip = False
            for exc in exclude:
                if exc.endswith("/"):
                    if exc.rstrip("/") in fpath:
                        skip = True
                        break
                elif glob.fnmatch.fnmatch(os.path.basename(fpath), exc):
                    skip = True
                    break
            if not skip and os.path.isfile(fpath):
                files_to_backup.append(fpath)

    if not files_to_backup:
        warn("Yedeklenecek config dosyasi bulunamadi.")
        return None

    info(f"{len(files_to_backup)} dosya yedekleniyor...")

    try:
        with tarfile.open(archive_path, "w:gz") as tar:
            for fpath in files_to_backup:
                arcname = os.path.relpath(fpath, "/")
                tar.add(fpath, arcname=arcname)
                info(f"  + {fpath}")

        size = os.path.getsize(archive_path)
        info(f"Config yedegi: {archive_path} ({human_size(size)})")
        log_event("INFO", f"Config backup created: {archive_name} ({len(files_to_backup)} files)")
        return archive_path

    except (IOError, PermissionError, tarfile.TarError) as e:
        error(f"Yedekleme hatasi: {e}")
        log_event("ERROR", f"Config backup failed: {e}")
        return None


# --- Supabase Backup ---

def backup_supabase(cfg):
    """Backup Supabase project data via Management API."""
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not token:
        warn("SUPABASE_ACCESS_TOKEN ayarlanmamis. Supabase yedegi atlanıyor.")
        return None

    backup_dir = get_backup_dir(cfg)
    ts = timestamp_str()
    api_base = "https://api.supabase.com/v1"

    # Get projects list
    info("Supabase projeleri listeleniyor...")
    try:
        result = subprocess.run(
            ["curl", "-s", "-H", f"Authorization: Bearer {token}",
             f"{api_base}/projects"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            error("Supabase API'ye baglanilamadi.")
            return None

        projects = json.loads(result.stdout)
        if not isinstance(projects, list):
            error(f"Supabase API hatasi: {result.stdout[:200]}")
            return None

    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        error(f"Supabase listesi alinamadi: {e}")
        return None

    if not projects:
        warn("Supabase projesi bulunamadi.")
        return None

    backup_files = []
    for proj in projects:
        proj_id = proj.get("id", "")
        proj_name = proj.get("name", "unknown")
        info(f"  Proje: {proj_name} ({proj_id})")

        # Export project config (settings, tables metadata)
        config_file = os.path.join(backup_dir, f"supabase-{proj_name}-{ts}.json")
        try:
            # Get project details
            result = subprocess.run(
                ["curl", "-s", "-H", f"Authorization: Bearer {token}",
                 f"{api_base}/projects/{proj_id}"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                proj_data = json.loads(result.stdout)
                # Get database info
                db_result = subprocess.run(
                    ["curl", "-s", "-H", f"Authorization: Bearer {token}",
                     f"{api_base}/projects/{proj_id}/database/backups"],
                    capture_output=True, text=True, timeout=30
                )
                db_backups = []
                if db_result.returncode == 0:
                    try:
                        db_backups = json.loads(db_result.stdout)
                    except json.JSONDecodeError:
                        pass

                backup_data = {
                    "project": proj_data,
                    "database_backups": db_backups,
                    "exported_at": datetime.now().isoformat(),
                }

                with open(config_file, "w") as f:
                    json.dump(backup_data, f, indent=2)

                backup_files.append(config_file)
                info(f"  -> {config_file}")

        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, IOError) as e:
            warn(f"  Proje {proj_name} yedeklenemedi: {e}")

    if backup_files:
        info(f"Supabase: {len(backup_files)} proje yedeklendi.")
        log_event("INFO", f"Supabase backup: {len(backup_files)} projects")
    return backup_files


# --- Coolify Backup ---

def backup_coolify(cfg):
    """Backup Coolify application configs and database list."""
    token = os.environ.get("COOLIFY_API_TOKEN", "")
    api_base = os.environ.get("COOLIFY_API_BASE", "http://localhost:8000/api/v1")

    if not token:
        warn("COOLIFY_API_TOKEN ayarlanmamis. Coolify yedegi atlaniyor.")
        return None

    backup_dir = get_backup_dir(cfg)
    ts = timestamp_str()
    backup_file = os.path.join(backup_dir, f"coolify-backup-{ts}.json")

    info("Coolify verileri yedekleniyor...")

    coolify_data = {
        "exported_at": datetime.now().isoformat(),
        "api_base": api_base,
    }

    endpoints = {
        "servers": "/servers",
        "applications": "/applications",
        "databases": "/databases",
        "services": "/services",
    }

    for key, endpoint in endpoints.items():
        try:
            result = subprocess.run(
                ["curl", "-s", "-H", f"Authorization: Bearer {token}",
                 "-H", "Accept: application/json",
                 f"{api_base}{endpoint}"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and result.stdout:
                coolify_data[key] = json.loads(result.stdout)
                count = len(coolify_data[key]) if isinstance(coolify_data[key], list) else 1
                info(f"  {key}: {count} kayit")
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            warn(f"  {key} alinamadi: {e}")
            coolify_data[key] = {"error": str(e)}

    try:
        with open(backup_file, "w") as f:
            json.dump(coolify_data, f, indent=2)

        size = os.path.getsize(backup_file)
        info(f"Coolify yedegi: {backup_file} ({human_size(size)})")
        log_event("INFO", f"Coolify backup: {backup_file}")
        return backup_file

    except (IOError, PermissionError) as e:
        error(f"Coolify yedegi yazilamadi: {e}")
        return None


# --- Cleanup / Retention ---

def cleanup_old_backups(cfg):
    """Remove backups older than retention_days."""
    backup_dir = get_backup_dir(cfg)
    retention = cfg.get("retention_days", 7)
    cutoff = datetime.now() - timedelta(days=retention)
    removed = 0

    for fname in os.listdir(backup_dir):
        fpath = os.path.join(backup_dir, fname)
        if not os.path.isfile(fpath):
            continue

        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            if mtime < cutoff:
                os.remove(fpath)
                removed += 1
                info(f"  Eski yedek silindi: {fname}")
        except (OSError, ValueError):
            pass

    if removed:
        info(f"{removed} eski yedek temizlendi (>{retention} gun).")
        log_event("INFO", f"Cleanup: {removed} old backups removed")
    return removed


# --- List Backups ---

def list_backups(cfg):
    """List all existing backup files."""
    backup_dir = get_backup_dir(cfg)

    if not os.path.exists(backup_dir):
        warn("Yedek dizini bulunamadi.")
        return

    files = []
    for fname in sorted(os.listdir(backup_dir)):
        fpath = os.path.join(backup_dir, fname)
        if os.path.isfile(fpath):
            size = os.path.getsize(fpath)
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            files.append((fname, size, mtime))

    if not files:
        info("Henuz yedek yok.")
        return

    print(f"\n{BOLD}{'=' * 65}{NC}")
    print(f"{BOLD}  Linux-AI Yedekler  {DIM}{backup_dir}{NC}")
    print(f"{BOLD}{'=' * 65}{NC}\n")

    total_size = 0
    for fname, size, mtime in files:
        total_size += size
        age = (datetime.now() - mtime).days
        age_str = f"{age}g" if age > 0 else "bugun"

        if "config" in fname:
            icon = f"{CYAN}[CFG]{NC}"
        elif "supabase" in fname:
            icon = f"{GREEN}[SUP]{NC}"
        elif "coolify" in fname:
            icon = f"{YELLOW}[CLF]{NC}"
        else:
            icon = f"{DIM}[???]{NC}"

        print(f"  {icon} {fname:45s} {human_size(size):>10s}  {DIM}{age_str}{NC}")

    print(f"\n  Toplam: {len(files)} yedek, {human_size(total_size)}")
    retention = cfg.get("retention_days", 7)
    print(f"  Saklama suresi: {retention} gun")
    print("")


# --- Restore ---

def restore_backup(archive_path):
    """Restore from a tar.gz backup archive."""
    if not os.path.exists(archive_path):
        # Try in backup dir
        full_path = os.path.join(BACKUP_DIR, archive_path)
        if os.path.exists(full_path):
            archive_path = full_path
        else:
            error(f"Yedek bulunamadi: {archive_path}")
            return False

    if not tarfile.is_tarfile(archive_path):
        error("Bu dosya bir tar arsivi degil. Sadece .tar.gz config yedekleri geri yuklenebilir.")
        return False

    info(f"Geri yukleniyor: {archive_path}")

    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            # Security: check for path traversal
            for member in tar.getmembers():
                if member.name.startswith("/") or ".." in member.name:
                    error(f"Guvenlik: Gecersiz yol tespit edildi: {member.name}")
                    return False

            # List contents
            members = tar.getmembers()
            info(f"  {len(members)} dosya geri yuklenecek:")
            for m in members:
                print(f"    /{m.name}")

            # Extract to root (paths are relative from /)
            tar.extractall(path="/", filter="data")

        info("Geri yukleme tamamlandi.")
        log_event("INFO", f"Restore completed: {archive_path}")
        return True

    except (tarfile.TarError, IOError, PermissionError) as e:
        error(f"Geri yukleme hatasi: {e}")
        log_event("ERROR", f"Restore failed: {e}")
        return False


# --- Cron Management ---

def manage_cron(enable=True):
    """Enable or disable daily backup cron job."""
    cron_line = f"0 3 * * * /usr/local/bin/ai-backup run --quiet {CRON_MARKER}"

    # Read current crontab
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True, text=True, timeout=5
        )
        current_cron = result.stdout if result.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        current_cron = ""

    # Remove existing ai-backup entries
    lines = [l for l in current_cron.strip().split("\n")
             if l.strip() and CRON_MARKER not in l]

    if enable:
        lines.append(cron_line)
        info("Gunluk yedekleme cron'u etkinlestirildi (her gun 03:00)")
    else:
        info("Gunluk yedekleme cron'u devre disi birakildi.")

    new_cron = "\n".join(lines) + "\n" if lines else ""

    try:
        proc = subprocess.run(
            ["crontab", "-"],
            input=new_cron, capture_output=True, text=True, timeout=5
        )
        if proc.returncode == 0:
            info("Cron guncellendi.")
            log_event("INFO", f"Cron {'enabled' if enable else 'disabled'}")
        else:
            error(f"Cron guncellenemedi: {proc.stderr}")
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        error(f"Cron komutu calistirilamadi: {e}")


# --- Run All Backups ---

def run_all_backups(cfg, quiet=False):
    """Execute all configured backup tasks."""
    ts_start = datetime.now()
    if not quiet:
        info("Tam yedekleme baslatiliyor...")
    log_event("INFO", "Full backup started")

    results = {"config": None, "supabase": None, "coolify": None}

    # 1. Config backup (always)
    results["config"] = backup_configs(cfg)

    # 2. Supabase (if enabled or token available)
    sup_cfg = cfg.get("supabase", {})
    if sup_cfg.get("enabled", False) or os.environ.get("SUPABASE_ACCESS_TOKEN"):
        results["supabase"] = backup_supabase(cfg)

    # 3. Coolify (if enabled or token available)
    clf_cfg = cfg.get("coolify", {})
    if clf_cfg.get("enabled", False) or os.environ.get("COOLIFY_API_TOKEN"):
        results["coolify"] = backup_coolify(cfg)

    # 4. Cleanup old backups
    cleanup_old_backups(cfg)

    elapsed = (datetime.now() - ts_start).total_seconds()

    if not quiet:
        print(f"\n{BOLD}--- Yedekleme Ozeti ---{NC}")
        for key, val in results.items():
            status = f"{GREEN}OK{NC}" if val else f"{DIM}atlandi{NC}"
            print(f"  {key:12s}: {status}")
        print(f"  Sure: {elapsed:.1f}s\n")

    log_event("INFO", f"Full backup completed in {elapsed:.1f}s")
    return results


# --- CLI ---

def cmd_run(args):
    cfg = load_backup_config()
    quiet = getattr(args, "quiet", False)
    run_all_backups(cfg, quiet=quiet)


def cmd_config(args):
    cfg = load_backup_config()
    backup_configs(cfg)


def cmd_supabase(args):
    cfg = load_backup_config()
    backup_supabase(cfg)


def cmd_coolify(args):
    cfg = load_backup_config()
    backup_coolify(cfg)


def cmd_list(args):
    cfg = load_backup_config()
    list_backups(cfg)


def cmd_restore(args):
    restore_backup(args.archive)


def cmd_cron(args):
    if args.disable:
        manage_cron(enable=False)
    else:
        manage_cron(enable=True)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="ai-backup",
        description="Linux-AI: Otomatik yedekleme araci"
    )
    sub = parser.add_subparsers(dest="command", help="Alt komutlar")

    p_run = sub.add_parser("run", help="Tum yedeklemeleri calistir")
    p_run.add_argument("--quiet", action="store_true", help="Sessiz mod")
    p_run.set_defaults(func=cmd_run)

    p_cfg = sub.add_parser("config", help="Sadece config dosyalarini yedekle")
    p_cfg.set_defaults(func=cmd_config)

    p_sup = sub.add_parser("supabase", help="Supabase proje verilerini yedekle")
    p_sup.set_defaults(func=cmd_supabase)

    p_clf = sub.add_parser("coolify", help="Coolify yapilandirmasini yedekle")
    p_clf.set_defaults(func=cmd_coolify)

    p_list = sub.add_parser("list", help="Mevcut yedekleri listele")
    p_list.set_defaults(func=cmd_list)

    p_restore = sub.add_parser("restore", help="Yedekten geri yukle")
    p_restore.add_argument("archive", help="Arsiv dosyasi yolu veya adi")
    p_restore.set_defaults(func=cmd_restore)

    p_cron = sub.add_parser("cron", help="Gunluk cron zamanlamasi")
    p_cron.add_argument("--enable", action="store_true", default=True,
                        help="Cron'u etkinlestir (varsayilan)")
    p_cron.add_argument("--disable", action="store_true",
                        help="Cron'u devre disi birak")
    p_cron.set_defaults(func=cmd_cron)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        # Default: list backups
        cfg = load_backup_config()
        list_backups(cfg)
        return

    args.func(args)


if __name__ == "__main__":
    main()

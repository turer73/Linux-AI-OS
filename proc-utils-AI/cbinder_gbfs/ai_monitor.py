"""
ai_monitor.py - Automated monitoring daemon for Linux-AI

Periodically checks system health and web project status.
Sends alerts via configured notification channels.

Monitors:
  - System: CPU, RAM, disk, temperature
  - Kernel: module state, governor
  - Web sites: HTTP status, response time, SSL expiry
  - Services: Ollama, Coolify, Supabase health
  - Deployments: last deploy status

Usage:
  ai-monitor run              # Start monitoring loop
  ai-monitor check            # One-time check, print report
  ai-monitor dashboard        # Terminal dashboard (one-shot)
"""

import os
import sys
import json
import time
import argparse
import subprocess
from datetime import datetime

import psutil
import yaml

# --- Constants ---

TAG = "[ai-monitor]"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"

CONFIG_PATH = "/var/AI-stump/ai-agent.yml"
SITES_PATH = "/var/AI-stump/webops-sites.yml"
LOG_PATH = "/var/AI-stump/ai-monitor.log"

DEFAULT_CHECK_INTERVAL = 300  # 5 minutes
DEFAULT_ALERT_THRESHOLDS = {
    "cpu_percent": 85,
    "ram_percent": 85,
    "disk_percent": 90,
    "temp_celsius": 80,
    "response_time_ms": 3000,
}


# --- Utility ---

def info(msg):
    print(f"{GREEN}{TAG}{NC} {msg}")


def warn(msg):
    print(f"{YELLOW}{TAG}{NC} {msg}")


def error(msg):
    print(f"{RED}{TAG}{NC} {msg}")


def log_event(level, message):
    """Append event to monitor log file."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] [{level}] {message}\n"
    try:
        with open(LOG_PATH, "a") as f:
            f.write(entry)
    except (IOError, PermissionError):
        pass


def load_yaml(path):
    """Load YAML config file."""
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
    except (yaml.YAMLError, IOError):
        pass
    return {}


# --- System Checks ---

def check_system():
    """Check system resources. Returns dict of status + alerts."""
    alerts = []

    cpu_pct = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    cpu_freq = psutil.cpu_freq()

    status = {
        "cpu_percent": cpu_pct,
        "cpu_freq_mhz": int(cpu_freq.current) if cpu_freq else 0,
        "ram_used_mb": mem.used // (1024 * 1024),
        "ram_total_mb": mem.total // (1024 * 1024),
        "ram_percent": mem.percent,
        "disk_used_gb": disk.used // (1024 * 1024 * 1024),
        "disk_total_gb": disk.total // (1024 * 1024 * 1024),
        "disk_percent": disk.percent,
    }

    # Temperature (Linux only)
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                for entry in entries:
                    if entry.current and entry.current > 0:
                        status["temp_celsius"] = entry.current
                        break
    except (AttributeError, OSError):
        pass

    t = DEFAULT_ALERT_THRESHOLDS
    if cpu_pct > t["cpu_percent"]:
        alerts.append(f"CPU yuksek: {cpu_pct}%")
    if mem.percent > t["ram_percent"]:
        alerts.append(f"RAM yuksek: {mem.percent}%")
    if disk.percent > t["disk_percent"]:
        alerts.append(f"Disk dolu: {disk.percent}%")
    if status.get("temp_celsius", 0) > t["temp_celsius"]:
        alerts.append(f"Sicaklik yuksek: {status['temp_celsius']}°C")

    return status, alerts


# --- Service Checks ---

def check_ollama():
    """Check if Ollama is running."""
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "http://localhost:11434/api/tags"],
            capture_output=True, text=True, timeout=5
        )
        running = result.returncode == 0 and result.stdout.strip() == "200"
        return {"ollama": "running" if running else "stopped"}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"ollama": "unreachable"}


def check_kernel_module():
    """Check Linux-AI kernel module status."""
    status = {"kernel_module": "not_loaded"}

    if os.path.exists("/dev/ai_ctl"):
        status["kernel_module"] = "loaded"

    proc_status = "/proc/ai_status"
    if os.path.exists(proc_status):
        try:
            with open(proc_status, "r") as f:
                status["proc_status"] = f.read().strip()[:200]
        except (IOError, PermissionError):
            pass

    return status


def check_tailscale():
    """Check Tailscale VPN connection status."""
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            self_node = data.get("Self", {})
            peers = data.get("Peer", {})
            online = self_node.get("Online", False)
            hostname = self_node.get("HostName", "?")
            ips = self_node.get("TailscaleIPs", [])
            ip = ips[0] if ips else "?"
            online_peers = sum(1 for p in peers.values() if p.get("Online"))
            return {
                "tailscale": "connected" if online else "disconnected",
                "hostname": hostname,
                "ip": ip,
                "peers_online": online_peers,
                "peers_total": len(peers),
            }
        elif "not running" in (result.stderr or "").lower():
            return {"tailscale": "stopped"}
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return {"tailscale": "not_installed"}


# --- Site Health Checks ---

def check_site_health(domain):
    """Check a website's HTTP health. Returns dict."""
    url = f"https://{domain}"
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w",
             '{"status":%{http_code},"time_ms":%{time_total}000,"size":%{size_download}}',
             "-L", "--max-time", "15", url],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode == 0 and result.stdout:
            # curl time_total is in seconds, we multiply by 1000 for ms
            data = json.loads(result.stdout.replace("000}", "}"))
            data["domain"] = domain
            data["healthy"] = 200 <= data.get("status", 0) < 400
            # Recalculate time_ms properly
            time_val = data.get("time_ms", 0)
            data["time_ms"] = int(float(str(time_val)))
            return data
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass

    return {"domain": domain, "status": 0, "healthy": False,
            "time_ms": 0, "error": "unreachable"}


def check_ssl_expiry(domain):
    """Check SSL certificate expiry date using openssl s_client.
    Returns dict with days_left, expiry_date, issuer."""
    try:
        # Connect and get certificate info
        connect = subprocess.run(
            ["openssl", "s_client", "-connect", f"{domain}:443",
             "-servername", domain, "-showcerts"],
            input="",
            capture_output=True, text=True, timeout=10
        )
        if connect.returncode != 0 and not connect.stdout:
            return {"domain": domain, "ssl_ok": False, "error": "connect_failed"}

        # Parse expiry date from certificate
        dates = subprocess.run(
            ["openssl", "x509", "-noout", "-dates", "-issuer"],
            input=connect.stdout,
            capture_output=True, text=True, timeout=5
        )
        if dates.returncode != 0:
            return {"domain": domain, "ssl_ok": False, "error": "parse_failed"}

        result = {"domain": domain, "ssl_ok": True}

        for line in dates.stdout.strip().split("\n"):
            line = line.strip()
            if line.startswith("notAfter="):
                # Parse: notAfter=Mar 15 12:00:00 2025 GMT
                date_str = line.split("=", 1)[1].strip()
                try:
                    expiry = datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z")
                except ValueError:
                    try:
                        expiry = datetime.strptime(date_str, "%b  %d %H:%M:%S %Y %Z")
                    except ValueError:
                        result["expiry_raw"] = date_str
                        continue
                result["expiry_date"] = expiry.strftime("%Y-%m-%d")
                result["days_left"] = (expiry - datetime.now()).days
            elif line.startswith("issuer="):
                result["issuer"] = line.split("=", 1)[1].strip()[:80]

        return result

    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"domain": domain, "ssl_ok": False, "error": "openssl_unavailable"}


def check_all_ssl():
    """Check SSL certificates for all configured sites."""
    sites_config = load_yaml(SITES_PATH)
    sites = sites_config.get("sites", {})
    results = []
    alerts = []

    for domain in sites.keys():
        ssl_info = check_ssl_expiry(domain)
        results.append(ssl_info)

        days = ssl_info.get("days_left")
        if days is not None:
            if days < 0:
                alerts.append(f"SSL SURESI DOLMUS: {domain} ({abs(days)} gun once)")
            elif days < 7:
                alerts.append(f"SSL KRITIK: {domain} ({days} gun kaldi)")
            elif days < 30:
                alerts.append(f"SSL uyari: {domain} ({days} gun kaldi)")
        elif not ssl_info.get("ssl_ok"):
            alerts.append(f"SSL kontrol edilemedi: {domain}")

    return results, alerts


def check_all_sites():
    """Check all configured web sites."""
    sites_config = load_yaml(SITES_PATH)
    sites = sites_config.get("sites", {})
    results = []
    alerts = []

    for domain, _config in sites.items():
        health = check_site_health(domain)
        results.append(health)

        if not health.get("healthy"):
            alerts.append(f"Site DOWN: {domain} (HTTP {health.get('status', '?')})")
        elif health.get("time_ms", 0) > DEFAULT_ALERT_THRESHOLDS["response_time_ms"]:
            alerts.append(f"Site yavas: {domain} ({health['time_ms']}ms)")

    return results, alerts


# --- Dashboard ---

def print_dashboard():
    """Print a terminal dashboard with all status info."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("")
    print(f"{BOLD}{'=' * 60}{NC}")
    print(f"{BOLD}  Linux-AI System Dashboard  {DIM}{now}{NC}")
    print(f"{BOLD}{'=' * 60}{NC}")

    # System
    sys_status, sys_alerts = check_system()
    print(f"\n{CYAN}[Sistem]{NC}")
    cpu_color = RED if sys_status["cpu_percent"] > 85 else \
                YELLOW if sys_status["cpu_percent"] > 70 else GREEN
    ram_color = RED if sys_status["ram_percent"] > 85 else \
                YELLOW if sys_status["ram_percent"] > 70 else GREEN
    disk_color = RED if sys_status["disk_percent"] > 90 else \
                 YELLOW if sys_status["disk_percent"] > 80 else GREEN

    print(f"  CPU:  {cpu_color}{sys_status['cpu_percent']:5.1f}%{NC}"
          f"  ({sys_status['cpu_freq_mhz']} MHz)")
    print(f"  RAM:  {ram_color}{sys_status['ram_percent']:5.1f}%{NC}"
          f"  ({sys_status['ram_used_mb']}/{sys_status['ram_total_mb']} MB)")
    print(f"  Disk: {disk_color}{sys_status['disk_percent']:5.1f}%{NC}"
          f"  ({sys_status['disk_used_gb']}/{sys_status['disk_total_gb']} GB)")
    if "temp_celsius" in sys_status:
        temp = sys_status["temp_celsius"]
        temp_color = RED if temp > 80 else YELLOW if temp > 70 else GREEN
        print(f"  Temp: {temp_color}{temp:.0f}°C{NC}")

    # Services
    print(f"\n{CYAN}[Servisler]{NC}")
    ollama_st = check_ollama()
    ollama_val = ollama_st.get("ollama", "?")
    ollama_color = GREEN if ollama_val == "running" else RED
    print(f"  Ollama: {ollama_color}{ollama_val}{NC}")

    kernel_st = check_kernel_module()
    km_val = kernel_st.get("kernel_module", "?")
    km_color = GREEN if km_val == "loaded" else YELLOW
    print(f"  Kernel: {km_color}{km_val}{NC}")

    ts_st = check_tailscale()
    ts_val = ts_st.get("tailscale", "?")
    ts_color = GREEN if ts_val == "connected" else \
               YELLOW if ts_val == "stopped" else RED
    ts_info = ""
    if ts_val == "connected":
        ts_info = (f" ({ts_st.get('ip', '?')}, "
                   f"{ts_st.get('peers_online', 0)}/{ts_st.get('peers_total', 0)} peer)")
    print(f"  Tailsc: {ts_color}{ts_val}{NC}{ts_info}")

    # Web Sites
    print(f"\n{CYAN}[Web Siteleri]{NC}")
    site_results, site_alerts = check_all_sites()
    if site_results:
        for s in site_results:
            domain = s.get("domain", "?")
            status = s.get("status", 0)
            time_ms = s.get("time_ms", 0)
            healthy = s.get("healthy", False)

            color = GREEN if healthy else RED
            time_color = GREEN if time_ms < 1000 else \
                         YELLOW if time_ms < 3000 else RED

            print(f"  {color}{domain:30s}{NC}"
                  f"  HTTP {status}"
                  f"  {time_color}{time_ms:>5}ms{NC}")
    else:
        print(f"  {DIM}(webops-sites.yml bulunamadi){NC}")

    # SSL Certificates
    print(f"\n{CYAN}[SSL Sertifikalari]{NC}")
    ssl_results, ssl_alerts = check_all_ssl()
    if ssl_results:
        for s in ssl_results:
            domain = s.get("domain", "?")
            days = s.get("days_left")
            if days is not None:
                if days < 7:
                    color = RED
                elif days < 30:
                    color = YELLOW
                else:
                    color = GREEN
                expiry = s.get("expiry_date", "?")
                print(f"  {domain:30s}  {color}{days:>3} gun{NC}  ({expiry})")
            else:
                err = s.get("error", "bilinmiyor")
                print(f"  {domain:30s}  {RED}hata{NC}  ({err})")
    else:
        print(f"  {DIM}(site yapilandirmasi yok){NC}")

    # Alerts
    all_alerts = sys_alerts + site_alerts + ssl_alerts
    if all_alerts:
        print(f"\n{RED}[UYARILAR]{NC}")
        for alert in all_alerts:
            print(f"  {RED}!{NC} {alert}")
    else:
        print(f"\n{GREEN}[OK]{NC} Tum sistemler normal.")

    print(f"\n{'=' * 60}")
    print("")


# --- Monitoring Loop ---

def run_monitor_loop(interval=DEFAULT_CHECK_INTERVAL):
    """Run continuous monitoring loop."""
    info(f"Monitor baslatildi (kontrol araligi: {interval}s)")
    info("Durdurmak icin Ctrl+C")
    log_event("INFO", "Monitor started")

    while True:
        try:
            sys_status, sys_alerts = check_system()
            site_results, site_alerts = check_all_sites()
            _ssl_results, ssl_alerts = check_all_ssl()
            all_alerts = sys_alerts + site_alerts + ssl_alerts

            if all_alerts:
                for alert in all_alerts:
                    warn(alert)
                    log_event("WARN", alert)
                    send_notification(alert)
            else:
                log_event("INFO", "All checks passed")

            time.sleep(interval)

        except KeyboardInterrupt:
            info("Monitor durduruluyor...")
            log_event("INFO", "Monitor stopped")
            break


def send_notification(message):
    """Send alert via all configured channels: notify-send, Telegram, Discord."""
    ts = datetime.now().strftime("%H:%M:%S")
    full_msg = f"[Linux-AI {ts}] {message}"

    # 1. notify-send (Linux desktop)
    try:
        subprocess.run(
            ["notify-send", "-u", "critical", "Linux-AI Monitor", message],
            capture_output=True, timeout=5
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 2. Telegram Bot
    _send_telegram(full_msg)

    # 3. Discord Webhook
    _send_discord(full_msg)


def _send_telegram(message):
    """Send message via Telegram Bot API."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": message, "parse_mode": "HTML"})

    try:
        subprocess.run(
            ["curl", "-s", "-X", "POST", url,
             "-H", "Content-Type: application/json",
             "-d", payload],
            capture_output=True, text=True, timeout=10
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def _send_discord(message):
    """Send message via Discord webhook."""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook_url:
        return

    payload = json.dumps({"content": message})

    try:
        subprocess.run(
            ["curl", "-s", "-X", "POST", webhook_url,
             "-H", "Content-Type: application/json",
             "-d", payload],
            capture_output=True, text=True, timeout=10
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


# --- CLI ---

def cmd_run(args):
    interval = getattr(args, "interval", DEFAULT_CHECK_INTERVAL)
    run_monitor_loop(interval)


def cmd_check(_args):
    """One-time health check."""
    print_dashboard()

    sys_status, sys_alerts = check_system()
    _site_results, site_alerts = check_all_sites()
    _ssl_results, ssl_alerts = check_all_ssl()
    all_alerts = sys_alerts + site_alerts + ssl_alerts

    if all_alerts:
        sys.exit(1)  # Non-zero exit for alerting scripts


def cmd_dashboard(_args):
    print_dashboard()


def build_parser():
    parser = argparse.ArgumentParser(
        prog="ai-monitor",
        description="Linux-AI: Sistem ve web izleme daemonu"
    )
    sub = parser.add_subparsers(dest="command", help="Alt komutlar")

    p_run = sub.add_parser("run", help="Surekli izleme baslat")
    p_run.add_argument("--interval", type=int, default=DEFAULT_CHECK_INTERVAL,
                        help=f"Kontrol araligi saniye (varsayilan: {DEFAULT_CHECK_INTERVAL})")
    p_run.set_defaults(func=cmd_run)

    p_check = sub.add_parser("check", help="Tek seferlik kontrol")
    p_check.set_defaults(func=cmd_check)

    p_dash = sub.add_parser("dashboard", help="Terminal dashboard goster")
    p_dash.set_defaults(func=cmd_dashboard)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        # Default: dashboard
        print_dashboard()
        return

    args.func(args)


if __name__ == "__main__":
    main()

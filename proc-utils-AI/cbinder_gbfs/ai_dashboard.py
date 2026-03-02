#!/usr/bin/env python3
"""
Linux-AI Terminal Dashboard (Bloomberg-style TUI)
=================================================
Masaüstü gerektirmeyen, terminal üzerinde çalışan canlı kontrol paneli.

Kullanım:
    ai-dashboard              # Tam dashboard
    ai-dashboard --minimal    # Minimal mod (düşük kaynak)
    ai-dashboard --refresh 5  # 5 saniye yenileme

Gereksinim: pip install rich
"""

import argparse
import os
import sys
import time
import signal
import subprocess
import socket
import ssl
import datetime
import json
from pathlib import Path

try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.live import Live
    from rich.columns import Columns
    from rich import box
    from rich.align import Align
    from rich.bar import Bar
    from rich.style import Style
except ImportError:
    print("HATA: 'rich' kütüphanesi gerekli.")
    print("Kur:  pip install rich")
    sys.exit(1)

try:
    import psutil
except ImportError:
    psutil = None

# ─── Sabitler ────────────────────────────────────────────────────────────────

VERSION = "0.3.0"
CONFIG_DIR = os.environ.get("LINUX_AI_CONFIG", "/var/AI-stump")
LOG_DIR = "/var/log"

COLORS = {
    "ok": "green",
    "warn": "yellow",
    "crit": "red",
    "info": "cyan",
    "dim": "bright_black",
    "header": "bold white on blue",
    "title": "bold cyan",
    "accent": "bold green",
    "value": "white",
    "bar_low": "green",
    "bar_mid": "yellow",
    "bar_high": "red",
}

# ─── TTL Cache (reduces subprocess forks 83%) ────────────────────────────────
_svc_cache = {}
_svc_cache_time = 0.0
_SVC_CACHE_TTL = 30.0  # seconds

_net_conn_cache = 0
_net_conn_cache_time = 0.0
_NET_CONN_CACHE_TTL = 30.0

# ─── Veri Toplama ────────────────────────────────────────────────────────────

def get_cpu_info():
    """CPU bilgileri."""
    info = {"percent": 0, "freq": 0, "cores": 0, "temp": None, "per_cpu": []}
    if not psutil:
        return info
    info["percent"] = psutil.cpu_percent(interval=0.5)
    info["per_cpu"] = psutil.cpu_percent(interval=0, percpu=True)
    info["cores"] = psutil.cpu_count()
    freq = psutil.cpu_freq()
    if freq:
        info["freq"] = int(freq.current)
    # Sıcaklık
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                if entries:
                    info["temp"] = int(entries[0].current)
                    break
    except Exception:
        pass
    return info


def get_memory_info():
    """RAM bilgileri."""
    if not psutil:
        return {"total": 0, "used": 0, "percent": 0, "swap_percent": 0}
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "total": mem.total // (1024 * 1024),
        "used": mem.used // (1024 * 1024),
        "available": mem.available // (1024 * 1024),
        "percent": mem.percent,
        "swap_total": swap.total // (1024 * 1024),
        "swap_used": swap.used // (1024 * 1024),
        "swap_percent": swap.percent,
    }


def get_disk_info():
    """Disk bilgileri."""
    if not psutil:
        return []
    disks = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "mount": part.mountpoint,
                "total": usage.total // (1024**3),
                "used": usage.used // (1024**3),
                "free": usage.free // (1024**3),
                "percent": usage.percent,
            })
        except PermissionError:
            pass
    return disks


def get_network_info():
    """Ağ bilgileri (net_connections cached with 30s TTL)."""
    global _net_conn_cache, _net_conn_cache_time
    if not psutil:
        return {"sent": 0, "recv": 0, "connections": 0}
    net = psutil.net_io_counters()
    # Cache expensive net_connections() call (kernel traversal)
    now = time.time()
    if now - _net_conn_cache_time > _NET_CONN_CACHE_TTL:
        _net_conn_cache = len(psutil.net_connections(kind="inet"))
        _net_conn_cache_time = now
    return {
        "sent": net.bytes_sent // (1024 * 1024),
        "recv": net.bytes_recv // (1024 * 1024),
        "connections": _net_conn_cache,
    }


def get_top_processes(n=8):
    """En çok kaynak kullanan süreçler."""
    if not psutil:
        return []
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = p.info
            if info["cpu_percent"] is not None:
                procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x.get("cpu_percent", 0), reverse=True)
    return procs[:n]


def get_service_status(name):
    """systemd servis durumu (30s TTL cache, 83% fork reduction)."""
    global _svc_cache_time
    now = time.time()
    if now - _svc_cache_time > _SVC_CACHE_TTL:
        _svc_cache.clear()
        _svc_cache_time = now
    if name in _svc_cache:
        return _svc_cache[name]
    try:
        r = subprocess.run(
            ["systemctl", "is-active", name],
            capture_output=True, text=True, timeout=3
        )
        state = r.stdout.strip()
        if state == "active":
            result = ("active", "ok")
        elif state == "inactive":
            result = ("inactive", "dim")
        else:
            result = (state, "warn")
    except Exception:
        result = ("?", "dim")
    _svc_cache[name] = result
    return result


def get_ollama_models():
    """Ollama model listesi."""
    try:
        r = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode != 0:
            return []
        models = []
        for line in r.stdout.strip().split("\n")[1:]:  # header atla
            parts = line.split()
            if len(parts) >= 2:
                models.append({"name": parts[0], "size": parts[2] if len(parts) > 2 else "?"})
        return models
    except Exception:
        return []


def get_tailscale_status():
    """Tailscale durumu."""
    try:
        r = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode != 0:
            return None
        data = json.loads(r.stdout)
        peers = data.get("Peer", {})
        return {
            "ip": data.get("TailscaleIPs", ["?"])[0] if data.get("TailscaleIPs") else "?",
            "hostname": data.get("Self", {}).get("HostName", "?"),
            "peers": len(peers),
            "connected": data.get("BackendState") == "Running",
        }
    except Exception:
        return None


def check_ssl_expiry(domain, port=443):
    """SSL sertifika kalan gün."""
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
            s.settimeout(5)
            s.connect((domain, port))
            cert = s.getpeercert()
        expire = datetime.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
        days = (expire - datetime.datetime.utcnow()).days
        return days
    except Exception:
        return None


def get_ssl_status(domains):
    """Tüm domainlerin SSL durumu."""
    results = []
    for d in domains:
        days = check_ssl_expiry(d)
        if days is None:
            results.append((d, "?", "dim"))
        elif days < 7:
            results.append((d, f"{days}g", "crit"))
        elif days < 30:
            results.append((d, f"{days}g", "warn"))
        else:
            results.append((d, f"{days}g", "ok"))
    return results


def get_uptime():
    """Sistem uptime."""
    if not psutil:
        return "?"
    boot = datetime.datetime.fromtimestamp(psutil.boot_time())
    delta = datetime.datetime.now() - boot
    days = delta.days
    hours = delta.seconds // 3600
    mins = (delta.seconds % 3600) // 60
    if days > 0:
        return f"{days}g {hours}s {mins}dk"
    elif hours > 0:
        return f"{hours}s {mins}dk"
    return f"{mins}dk"


def get_load_avg():
    """Sistem load average."""
    try:
        load = os.getloadavg()
        return f"{load[0]:.1f}  {load[1]:.1f}  {load[2]:.1f}"
    except (OSError, AttributeError):
        # Windows
        if psutil:
            return f"{psutil.cpu_percent():.0f}%"
        return "N/A"


def read_recent_logs(n=8):
    """Son log satırları."""
    log_files = [
        "/var/log/linux-ai/agent.log",
        "/var/log/linux-ai/monitor.log",
        "/var/log/linux-ai/backup.log",
        "/var/log/syslog",
    ]
    lines = []
    for lf in log_files:
        try:
            with open(lf, "r") as f:
                for line in f.readlines()[-3:]:
                    line = line.strip()
                    if line:
                        src = Path(lf).stem[:6]
                        lines.append((src, line[:120]))
        except Exception:
            pass
    lines.sort(key=lambda x: x[1], reverse=True)
    return lines[:n]


def load_config_domains():
    """Config'den domain listesi yükle."""
    config_path = os.path.join(CONFIG_DIR, "monitor.yml")
    domains = []
    try:
        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        sites = cfg.get("sites", cfg.get("ssl_domains", []))
        if isinstance(sites, list):
            for s in sites:
                if isinstance(s, dict):
                    domains.append(s.get("domain", s.get("url", "")))
                elif isinstance(s, str):
                    domains.append(s)
    except Exception:
        pass
    # Varsayılan domainler temizle
    return [d.replace("https://", "").replace("http://", "").split("/")[0]
            for d in domains if d]


# ─── Panel Oluşturucular ─────────────────────────────────────────────────────

def make_bar(percent, width=20):
    """Yüzde çubuğu oluştur."""
    filled = int(width * percent / 100)
    empty = width - filled
    if percent >= 90:
        color = COLORS["bar_high"]
    elif percent >= 70:
        color = COLORS["bar_mid"]
    else:
        color = COLORS["bar_low"]
    bar = f"[{color}]{'█' * filled}[/{color}][{COLORS['dim']}]{'░' * empty}[/{COLORS['dim']}]"
    return bar


def panel_header(tick):
    """Üst başlık satırı."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    uptime = get_uptime()
    load = get_load_avg()
    dots = "●" if tick % 2 == 0 else "○"

    text = Text()
    text.append(" ◆ LINUX-AI ", style="bold white on dark_blue")
    text.append(f" v{VERSION} ", style="bold cyan")
    text.append("│", style="bright_black")
    text.append(f" {now} ", style="white")
    text.append("│", style="bright_black")
    text.append(f" Uptime: {uptime} ", style="green")
    text.append("│", style="bright_black")
    text.append(f" Load: {load} ", style="yellow")
    text.append(f" {dots}", style="green")
    return text


def panel_cpu(cpu_info):
    """CPU paneli."""
    table = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    table.add_column("label", style=COLORS["dim"], width=10)
    table.add_column("bar", width=24)
    table.add_column("val", style=COLORS["value"], width=8, justify="right")

    # Toplam CPU
    table.add_row(
        "CPU Total",
        make_bar(cpu_info["percent"]),
        f"{cpu_info['percent']:5.1f}%"
    )

    # Her çekirdek
    for i, pct in enumerate(cpu_info.get("per_cpu", [])):
        table.add_row(
            f"Core {i}",
            make_bar(pct),
            f"{pct:5.1f}%"
        )

    # Frekans
    if cpu_info.get("freq"):
        table.add_row("Frekans", "", f"{cpu_info['freq']} MHz")

    # Sıcaklık
    if cpu_info.get("temp") is not None:
        temp = cpu_info["temp"]
        temp_color = "red" if temp > 80 else "yellow" if temp > 60 else "green"
        table.add_row("Sıcaklık", "", f"[{temp_color}]{temp}°C[/{temp_color}]")

    return Panel(table, title="[bold cyan]◆ CPU[/bold cyan]", border_style="cyan",
                 box=box.ROUNDED)


def panel_memory(mem_info):
    """RAM paneli."""
    table = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    table.add_column("label", style=COLORS["dim"], width=10)
    table.add_column("bar", width=24)
    table.add_column("val", style=COLORS["value"], width=12, justify="right")

    table.add_row(
        "RAM",
        make_bar(mem_info["percent"]),
        f"{mem_info['used']}/{mem_info['total']} MB"
    )

    if mem_info.get("swap_total", 0) > 0:
        table.add_row(
            "Swap",
            make_bar(mem_info["swap_percent"]),
            f"{mem_info['swap_used']}/{mem_info['swap_total']} MB"
        )

    table.add_row(
        "Kullanılabilir", "", f"[green]{mem_info.get('available', 0)} MB[/green]"
    )

    return Panel(table, title="[bold magenta]◆ Bellek[/bold magenta]",
                 border_style="magenta", box=box.ROUNDED)


def panel_disk(disks):
    """Disk paneli."""
    table = Table(box=None, show_header=True, padding=(0, 1), expand=True)
    table.add_column("Bağlam", style=COLORS["dim"], width=12)
    table.add_column("Kullanım", width=24)
    table.add_column("Boş", style=COLORS["value"], width=10, justify="right")

    for d in disks[:4]:  # max 4 disk
        table.add_row(
            d["mount"][:12],
            make_bar(d["percent"]),
            f"{d['free']} GB"
        )

    return Panel(table, title="[bold yellow]◆ Disk[/bold yellow]",
                 border_style="yellow", box=box.ROUNDED)


def panel_network(net_info):
    """Ağ paneli."""
    table = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    table.add_column("label", style=COLORS["dim"], width=12)
    table.add_column("val", style=COLORS["value"])

    table.add_row("↑ Gönderilen", f"{net_info['sent']} MB")
    table.add_row("↓ Alınan", f"{net_info['recv']} MB")
    table.add_row("Bağlantılar", f"{net_info['connections']}")

    return Panel(table, title="[bold blue]◆ Ağ[/bold blue]",
                 border_style="blue", box=box.ROUNDED)


def panel_services():
    """Servis durumları paneli."""
    services = [
        ("ollama", "Ollama AI"),
        ("tailscaled", "Tailscale"),
        ("ai-monitor", "AI Monitor"),
        ("ai-cpufregd", "CPU Freq"),
        ("cron", "Cron"),
        ("sshd", "SSH"),
        ("lightdm", "Display"),
        ("nginx", "Nginx"),
    ]

    table = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    table.add_column("icon", width=2)
    table.add_column("name", style=COLORS["value"], width=12)
    table.add_column("status", width=10)

    for svc_name, display_name in services:
        state, color = get_service_status(svc_name)
        icon = "●" if state == "active" else "○"
        table.add_row(
            f"[{COLORS[color]}]{icon}[/{COLORS[color]}]",
            display_name,
            f"[{COLORS[color]}]{state}[/{COLORS[color]}]"
        )

    return Panel(table, title="[bold green]◆ Servisler[/bold green]",
                 border_style="green", box=box.ROUNDED)


def panel_ollama(models):
    """Ollama modelleri paneli."""
    table = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    table.add_column("model", style="cyan", width=24)
    table.add_column("size", style=COLORS["value"], width=8, justify="right")

    if models:
        for m in models[:6]:
            table.add_row(m["name"], m["size"])
    else:
        table.add_row("[dim]Ollama çalışmıyor[/dim]", "")

    return Panel(table, title="[bold cyan]◆ AI Modeller[/bold cyan]",
                 border_style="cyan", box=box.ROUNDED)


def panel_tailscale(ts_info):
    """Tailscale paneli."""
    table = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    table.add_column("label", style=COLORS["dim"], width=10)
    table.add_column("val", style=COLORS["value"])

    if ts_info and ts_info.get("connected"):
        table.add_row("Durum", "[green]● Bağlı[/green]")
        table.add_row("IP", ts_info.get("ip", "?"))
        table.add_row("Hostname", ts_info.get("hostname", "?"))
        table.add_row("Peers", str(ts_info.get("peers", 0)))
    else:
        table.add_row("Durum", "[red]○ Bağlı değil[/red]")

    return Panel(table, title="[bold blue]◆ Tailscale VPN[/bold blue]",
                 border_style="blue", box=box.ROUNDED)


def panel_ssl(ssl_results):
    """SSL sertifika paneli."""
    table = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    table.add_column("domain", style=COLORS["value"], width=24)
    table.add_column("days", width=10, justify="right")

    if ssl_results:
        for domain, days, color in ssl_results:
            table.add_row(domain, f"[{COLORS[color]}]{days}[/{COLORS[color]}]")
    else:
        table.add_row("[dim]Domain yapılandırılmamış[/dim]", "")

    return Panel(table, title="[bold yellow]◆ SSL Sertifikaları[/bold yellow]",
                 border_style="yellow", box=box.ROUNDED)


def panel_processes(procs):
    """Süreç listesi paneli."""
    table = Table(box=None, show_header=True, padding=(0, 1), expand=True)
    table.add_column("PID", style=COLORS["dim"], width=7, justify="right")
    table.add_column("İsim", style=COLORS["value"], width=18)
    table.add_column("CPU%", width=6, justify="right")
    table.add_column("MEM%", width=6, justify="right")

    for p in procs:
        cpu = p.get("cpu_percent", 0)
        mem = p.get("memory_percent", 0)
        cpu_color = "red" if cpu > 50 else "yellow" if cpu > 20 else "green"
        mem_color = "red" if mem > 30 else "yellow" if mem > 15 else "green"
        table.add_row(
            str(p.get("pid", "")),
            (p.get("name", "?"))[:18],
            f"[{cpu_color}]{cpu:.1f}[/{cpu_color}]",
            f"[{mem_color}]{mem:.1f}[/{mem_color}]"
        )

    return Panel(table, title="[bold red]◆ Süreçler (Top 8)[/bold red]",
                 border_style="red", box=box.ROUNDED)


def panel_logs(log_lines):
    """Son loglar paneli."""
    text = Text()
    if log_lines:
        for src, line in log_lines:
            text.append(f"[{src}] ", style="cyan")
            # Renklendirme
            if "error" in line.lower() or "fail" in line.lower():
                text.append(line[:100] + "\n", style="red")
            elif "warn" in line.lower():
                text.append(line[:100] + "\n", style="yellow")
            else:
                text.append(line[:100] + "\n", style="bright_black")
    else:
        text.append("Log bulunamadı", style="bright_black")

    return Panel(text, title="[bold white]◆ Son Loglar[/bold white]",
                 border_style="white", box=box.ROUNDED)


def panel_alerts(cpu_info, mem_info, disks, ssl_results):
    """Uyarılar paneli."""
    alerts = []

    # CPU uyarısı
    if cpu_info["percent"] > 90:
        alerts.append(("[CRIT]", f"CPU %{cpu_info['percent']:.0f} kullanımda!", "red"))
    elif cpu_info["percent"] > 70:
        alerts.append(("[WARN]", f"CPU %{cpu_info['percent']:.0f} kullanımda", "yellow"))

    # RAM uyarısı
    if mem_info["percent"] > 90:
        alerts.append(("[CRIT]", f"RAM %{mem_info['percent']:.0f} dolu!", "red"))
    elif mem_info["percent"] > 80:
        alerts.append(("[WARN]", f"RAM %{mem_info['percent']:.0f} kullanımda", "yellow"))

    # Disk uyarısı
    for d in disks:
        if d["percent"] > 90:
            alerts.append(("[CRIT]", f"Disk {d['mount']} %{d['percent']:.0f} dolu!", "red"))
        elif d["percent"] > 80:
            alerts.append(("[WARN]", f"Disk {d['mount']} %{d['percent']:.0f}", "yellow"))

    # Sıcaklık
    if cpu_info.get("temp") and cpu_info["temp"] > 85:
        alerts.append(("[CRIT]", f"CPU sıcaklığı {cpu_info['temp']}°C!", "red"))

    # SSL
    for domain, days, color in (ssl_results or []):
        if color == "crit":
            alerts.append(("[CRIT]", f"SSL {domain}: {days} kaldı!", "red"))
        elif color == "warn":
            alerts.append(("[WARN]", f"SSL {domain}: {days} kaldı", "yellow"))

    # Uyarı yoksa
    if not alerts:
        alerts.append(("[ OK ]", "Tüm sistemler normal", "green"))

    text = Text()
    for tag, msg, color in alerts[:6]:
        text.append(f" {tag} ", style=f"bold {color}")
        text.append(f" {msg}\n", style=color)

    return Panel(text, title="[bold white on red] ◆ UYARILAR [/bold white on red]",
                 border_style="red", box=box.HEAVY)


def panel_quick_commands():
    """Hızlı komutlar referans paneli."""
    text = Text()
    commands = [
        ("ai-agent", "AI Asistan"),
        ("ai-monitor check", "Hızlı kontrol"),
        ("ai-backup run", "Yedek al"),
        ("ai-logs tail", "Canlı loglar"),
        ("ai-web-agent", "Web yönetim"),
        ("ollama run qwen2.5-coder:3b", "AI Kodlama"),
    ]
    for cmd, desc in commands:
        text.append(f" {cmd}", style="bold green")
        text.append(f"  {desc}\n", style="bright_black")

    return Panel(text, title="[bold green]◆ Komutlar[/bold green]",
                 border_style="green", box=box.ROUNDED)


def panel_ticker(tick):
    """Alt bilgi ticker satırı."""
    messages = [
        "Linux-AI OS v0.3.0 | AI-Powered System Management",
        "Çıkış: Ctrl+C | Yenile: Otomatik",
        f"Ollama: OLLAMA_NUM_GPU=0 | CPU-Only Mode | {psutil.cpu_count() if psutil else '?'}T",
        "github.com/turer73/Linux-AI",
    ]
    idx = (tick // 3) % len(messages)
    return Text(f" ▶ {messages[idx]}", style="bold white on dark_blue")


# ─── Ana Layout ──────────────────────────────────────────────────────────────

def build_dashboard(tick, minimal=False):
    """Dashboard layout oluştur."""
    # Veri topla
    cpu_info = get_cpu_info()
    mem_info = get_memory_info()
    disks = get_disk_info()
    net_info = get_network_info()
    procs = get_top_processes()

    # Yavaş sorgular sadece her 6. tick'te (30 saniyede bir)
    ssl_results = []
    ts_info = None
    models = []

    if tick % 6 == 0 or tick == 0:
        build_dashboard._cache_ssl = get_ssl_status(load_config_domains())
        build_dashboard._cache_ts = get_tailscale_status()
        build_dashboard._cache_models = get_ollama_models()
        build_dashboard._cache_logs = read_recent_logs()

    ssl_results = getattr(build_dashboard, '_cache_ssl', [])
    ts_info = getattr(build_dashboard, '_cache_ts', None)
    models = getattr(build_dashboard, '_cache_models', [])
    log_lines = getattr(build_dashboard, '_cache_logs', [])

    # Layout oluştur
    layout = Layout()

    # Üst başlık
    layout.split_column(
        Layout(name="header", size=1),
        Layout(name="alerts", size=5),
        Layout(name="main"),
        Layout(name="bottom", size=10),
        Layout(name="ticker", size=1),
    )

    # Header
    layout["header"].update(panel_header(tick))

    # Uyarılar
    layout["alerts"].update(panel_alerts(cpu_info, mem_info, disks, ssl_results))

    if minimal:
        # Minimal mod: sadece CPU + RAM + Servisler
        layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1),
        )
        layout["main"]["left"].split_column(
            Layout(panel_cpu(cpu_info)),
            Layout(panel_memory(mem_info)),
        )
        layout["main"]["right"].split_column(
            Layout(panel_services()),
            Layout(panel_disk(disks)),
        )
    else:
        # Tam mod: 3 sütun
        layout["main"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="center", ratio=2),
            Layout(name="right", ratio=2),
        )

        # Sol sütun: CPU + RAM + Disk
        layout["main"]["left"].split_column(
            Layout(panel_cpu(cpu_info), ratio=2),
            Layout(panel_memory(mem_info), ratio=1),
            Layout(panel_disk(disks), ratio=1),
        )

        # Orta sütun: Servisler + Süreçler + Ağ
        layout["main"]["center"].split_column(
            Layout(panel_services(), ratio=2),
            Layout(panel_processes(procs), ratio=2),
            Layout(panel_network(net_info), ratio=1),
        )

        # Sağ sütun: AI + VPN + SSL
        layout["main"]["right"].split_column(
            Layout(panel_ollama(models), ratio=1),
            Layout(panel_tailscale(ts_info), ratio=1),
            Layout(panel_ssl(ssl_results), ratio=1),
            Layout(panel_quick_commands(), ratio=1),
        )

    # Alt: Loglar
    layout["bottom"].update(panel_logs(log_lines))

    # Ticker
    layout["ticker"].update(panel_ticker(tick))

    return layout


# ─── Ana ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Linux-AI Terminal Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  ai-dashboard              # Tam dashboard
  ai-dashboard --minimal    # Minimal mod
  ai-dashboard --refresh 3  # 3 saniye yenileme
        """
    )
    parser.add_argument("--minimal", "-m", action="store_true",
                        help="Minimal mod (düşük kaynak kullanımı)")
    parser.add_argument("--refresh", "-r", type=int, default=5,
                        help="Yenileme aralığı (saniye, varsayılan: 5)")
    args = parser.parse_args()

    console = Console()

    # psutil kontrolü
    if not psutil:
        console.print("[red]HATA:[/red] 'psutil' gerekli: pip install psutil")
        sys.exit(1)

    # Ctrl+C ile temiz çıkış
    def signal_handler(sig, frame):
        console.clear()
        console.print("\n[cyan]Linux-AI Dashboard kapatıldı.[/cyan]")
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    # Canlı dashboard
    tick = 0
    try:
        with Live(console=console, refresh_per_second=1, screen=True) as live:
            while True:
                layout = build_dashboard(tick, minimal=args.minimal)
                live.update(layout)
                time.sleep(args.refresh)
                tick += 1
                # GC every 60 ticks (~5 min at default refresh) to prevent RSS growth
                if tick % 60 == 0:
                    import gc
                    gc.collect()
    except KeyboardInterrupt:
        pass
    finally:
        console.clear()
        console.print("[cyan]Linux-AI Dashboard kapatıldı.[/cyan]")


if __name__ == "__main__":
    main()

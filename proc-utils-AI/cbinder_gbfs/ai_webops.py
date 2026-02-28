"""
ai_webops.py - Web operations and site management for Linux-AI

Manages web projects with integrated DevOps tooling:
  - Vercel deployment and preview
  - Cloudflare DNS and cache management
  - Supabase database operations
  - GitHub repository management
  - Uptime and health monitoring
  - Security scanning

Site config: /var/AI-stump/webops-sites.yml
  or: ~/.config/linux-ai/webops-sites.yml

Usage:
  ai-webops status                     # Tum sitelerin durumu
  ai-webops deploy renderhane.com      # Vercel'e deploy
  ai-webops monitor                    # Uptime kontrolu
  ai-webops dns renderhane.com list    # DNS kayitlari
  ai-webops db kokenakademi.com status # Supabase durumu
  ai-webops health renderhane.com      # Performans/guvenlik taramasi
  ai-webops init my-site.com           # Yeni site konfig ekle
"""

import os
import sys
import json
import time
import argparse
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

import psutil
import yaml

# --- Constants ---

TAG = "[ai-webops]"

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
NC = "\033[0m"

# Config locations (first found wins)
CONFIG_PATHS = [
    "/var/AI-stump/webops-sites.yml",
    os.path.expanduser("~/.config/linux-ai/webops-sites.yml"),
]

DEFAULT_CONFIG = {
    "sites": {},
    "defaults": {
        "framework": "nextjs",
        "hosting": "vercel",
        "cdn": "cloudflare",
        "db": "supabase",
        "monitor_interval": 300,
    },
}


# --- Utility ---

def info(msg):
    print(f"{GREEN}{TAG}{NC} {msg}")


def warn(msg):
    print(f"{YELLOW}{TAG}{NC} {msg}")


def error(msg):
    print(f"{RED}{TAG}{NC} {msg}")


def header(msg):
    print(f"{CYAN}{TAG}{NC} {msg}")


def command_exists(cmd):
    return shutil.which(cmd) is not None


def run_cmd(args, timeout=60, capture=True):
    """Run command safely. Returns CompletedProcess."""
    try:
        return subprocess.run(
            args, capture_output=capture, text=True,
            timeout=timeout, check=False
        )
    except FileNotFoundError:
        error(f"Komut bulunamadi: {args[0]}")
        return None
    except subprocess.TimeoutExpired:
        error(f"Zaman asimi: {' '.join(args)}")
        return None


def run_json_cmd(args, timeout=60):
    """Run command and parse JSON output."""
    result = run_cmd(args, timeout=timeout)
    if result and result.returncode == 0:
        try:
            return json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError):
            pass
    return None


# --- Config Management ---

def find_config_path():
    """Find existing config or return first writable path."""
    for path in CONFIG_PATHS:
        if os.path.exists(path):
            return path
    # Return first path, create dir if needed
    path = CONFIG_PATHS[0]
    if not os.path.exists(path):
        # Try user config as fallback
        path = CONFIG_PATHS[1]
    return path


def load_config():
    """Load site configuration from YAML."""
    path = find_config_path()
    if not os.path.exists(path):
        return DEFAULT_CONFIG.copy()
    try:
        with open(path, "r") as f:
            cfg = yaml.safe_load(f) or {}
        # Merge with defaults
        merged = DEFAULT_CONFIG.copy()
        merged.update(cfg)
        return merged
    except (yaml.YAMLError, IOError) as e:
        error(f"Konfigurasyon okuma hatasi: {e}")
        return DEFAULT_CONFIG.copy()


def save_config(config):
    """Save site configuration to YAML."""
    path = find_config_path()
    config_dir = os.path.dirname(path)
    try:
        os.makedirs(config_dir, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        info(f"Konfigurasyon kaydedildi: {path}")
    except (IOError, PermissionError) as e:
        error(f"Konfigurasyon yazilamadi: {e}")


def get_site_config(config, domain):
    """Get config for a specific site."""
    sites = config.get("sites", {})
    if domain not in sites:
        error(f"Site bulunamadi: {domain}")
        error(f"Kayitli siteler: {', '.join(sites.keys()) or '(yok)'}")
        return None
    return sites[domain]


# --- Tool Checks ---

def check_tools():
    """Check which CLI tools are available."""
    tools = {
        "vercel": command_exists("vercel"),
        "wrangler": command_exists("wrangler"),
        "supabase": command_exists("supabase"),
        "gh": command_exists("gh"),
        "curl": command_exists("curl"),
        "npm": command_exists("npm"),
    }
    return tools


def ensure_tool(name):
    """Check if a tool exists, warn if not."""
    if not command_exists(name):
        error(f"{name} bulunamadi.")
        install_hints = {
            "vercel": "npm i -g vercel",
            "wrangler": "npm i -g wrangler",
            "supabase": "npm i -g supabase",
            "gh": "https://cli.github.com/",
        }
        hint = install_hints.get(name, f"{name} kurun")
        warn(f"Kurun: {hint}")
        return False
    return True


# --- Vercel Operations ---

def vercel_deploy(site_cfg, production=False):
    """Deploy to Vercel."""
    if not ensure_tool("vercel"):
        return False

    repo_path = site_cfg.get("repo_path", ".")
    args = ["vercel", "--cwd", repo_path]
    if production:
        args.append("--prod")

    info(f"Vercel deploy baslatiliyor... ({'production' if production else 'preview'})")
    result = run_cmd(args, timeout=300, capture=False)
    if result and result.returncode == 0:
        info("Deploy basarili!")
        return True
    error("Deploy basarisiz.")
    return False


def vercel_status(site_cfg):
    """Get Vercel deployment status."""
    if not ensure_tool("vercel"):
        return

    domain = site_cfg.get("domain", "")
    result = run_cmd(["vercel", "ls", "--limit", "5"], timeout=30)
    if result and result.returncode == 0:
        print(result.stdout)
    else:
        warn("Vercel durumu alinamadi.")


# --- Cloudflare Operations ---

def cloudflare_dns_list(site_cfg):
    """List Cloudflare DNS records."""
    if not ensure_tool("wrangler"):
        return

    zone_id = site_cfg.get("cloudflare_zone_id", "")
    if not zone_id:
        # Try to get zone by domain
        domain = site_cfg.get("domain", "")
        info(f"Cloudflare DNS kayitlari: {domain}")
        warn("Zone ID ayarlanmamis. webops-sites.yml'de cloudflare_zone_id ekleyin.")
        return

    # Use curl with CF API token from env
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not token:
        error("CLOUDFLARE_API_TOKEN ortam degiskeni ayarlanmamis.")
        warn("export CLOUDFLARE_API_TOKEN=your_token")
        return

    result = run_cmd([
        "curl", "-s",
        "-H", f"Authorization: Bearer {token}",
        "-H", "Content-Type: application/json",
        f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    ], timeout=30)

    if result and result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            records = data.get("result", [])
            if records:
                print(f"\n  {'Tip':<8} {'Ad':<35} {'Deger':<40}")
                print(f"  {'-'*8} {'-'*35} {'-'*40}")
                for r in records:
                    print(f"  {r['type']:<8} {r['name']:<35} {r['content']:<40}")
            else:
                info("DNS kaydi bulunamadi.")
        except (json.JSONDecodeError, KeyError):
            warn("DNS verileri ayristirilamadi.")


def cloudflare_purge_cache(site_cfg):
    """Purge Cloudflare cache."""
    zone_id = site_cfg.get("cloudflare_zone_id", "")
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")

    if not zone_id or not token:
        error("Zone ID veya API token eksik.")
        return False

    result = run_cmd([
        "curl", "-s", "-X", "POST",
        "-H", f"Authorization: Bearer {token}",
        "-H", "Content-Type: application/json",
        "--data", '{"purge_everything":true}',
        f"https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache"
    ], timeout=30)

    if result and result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            if data.get("success"):
                info("Cache temizlendi!")
                return True
        except json.JSONDecodeError:
            pass
    error("Cache temizleme basarisiz.")
    return False


# --- Supabase Operations ---

def supabase_status(site_cfg):
    """Check Supabase project status."""
    if not ensure_tool("supabase"):
        return

    project_id = site_cfg.get("supabase_project_id", "")
    if project_id:
        info(f"Supabase proje: {project_id}")

    repo_path = site_cfg.get("repo_path", ".")
    result = run_cmd(["supabase", "status"], timeout=30)
    if result and result.returncode == 0:
        print(result.stdout)
    else:
        warn("Supabase durumu alinamadi. 'supabase init' calistirilmis mi?")


def supabase_db_push(site_cfg):
    """Push database migrations."""
    if not ensure_tool("supabase"):
        return False

    info("Supabase migration push baslatiliyor...")
    result = run_cmd(["supabase", "db", "push"], timeout=120, capture=False)
    if result and result.returncode == 0:
        info("Migration basarili!")
        return True
    error("Migration basarisiz.")
    return False


# --- GitHub Operations ---

def github_status(site_cfg):
    """Show GitHub repo status."""
    if not ensure_tool("gh"):
        return

    repo = site_cfg.get("github_repo", "")
    if not repo:
        warn("GitHub repo ayarlanmamis.")
        return

    info(f"GitHub: {repo}")

    # Recent PRs
    result = run_cmd(["gh", "pr", "list", "-R", repo, "--limit", "5"], timeout=30)
    if result and result.returncode == 0 and result.stdout.strip():
        print(f"\n  Son PR'ler:")
        print(f"  {result.stdout}")

    # Recent issues
    result = run_cmd(["gh", "issue", "list", "-R", repo, "--limit", "5"], timeout=30)
    if result and result.returncode == 0 and result.stdout.strip():
        print(f"  Son Issue'lar:")
        print(f"  {result.stdout}")


# --- Health / Monitoring ---

def check_site_health(domain):
    """Basic health check for a site."""
    info(f"Saglik kontrolu: {domain}")

    url = f"https://{domain}"
    start = time.time()
    result = run_cmd([
        "curl", "-s", "-o", "/dev/null",
        "-w", "%{http_code} %{time_total} %{size_download}",
        "-L", url
    ], timeout=30)

    if result and result.returncode == 0:
        parts = result.stdout.strip().split()
        if len(parts) >= 3:
            status = parts[0]
            response_time = float(parts[1])
            size = int(float(parts[2]))

            status_color = GREEN if status.startswith("2") else (YELLOW if status.startswith("3") else RED)
            time_color = GREEN if response_time < 1.0 else (YELLOW if response_time < 3.0 else RED)

            print(f"  HTTP:     {status_color}{status}{NC}")
            print(f"  Sure:     {time_color}{response_time:.2f}s{NC}")
            print(f"  Boyut:    {size / 1024:.1f} KB")
            return status.startswith("2") or status.startswith("3")
    else:
        print(f"  Durum:    {RED}Erisilemez{NC}")
        return False


def monitor_all_sites(config):
    """Run health checks on all configured sites."""
    sites = config.get("sites", {})
    if not sites:
        warn("Kayitli site yok. Once ekleyin: ai-webops init site.com")
        return

    header("=== Site Saglik Raporu ===")
    print(f"  Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("")

    results = {}
    for domain in sites:
        ok = check_site_health(domain)
        results[domain] = ok
        print("")

    # Summary
    total = len(results)
    healthy = sum(1 for v in results.values() if v)
    print(f"  Ozet: {healthy}/{total} site saglikli")

    if healthy < total:
        unhealthy = [d for d, v in results.items() if not v]
        warn(f"Sorunlu siteler: {', '.join(unhealthy)}")


# --- Security Scan ---

def security_scan(domain):
    """Basic security headers check."""
    info(f"Guvenlik taramasi: {domain}")

    url = f"https://{domain}"
    result = run_cmd([
        "curl", "-s", "-I", "-L", url
    ], timeout=30)

    if not result or result.returncode != 0:
        error("Site erisilemez.")
        return

    headers_text = result.stdout.lower()
    checks = {
        "strict-transport-security": "HSTS",
        "x-content-type-options": "Content-Type koruması",
        "x-frame-options": "Clickjacking koruması",
        "content-security-policy": "CSP",
        "x-xss-protection": "XSS koruması",
        "referrer-policy": "Referrer politikası",
    }

    print("")
    for header_name, label in checks.items():
        found = header_name in headers_text
        status = f"{GREEN}OK{NC}" if found else f"{RED}EKSIK{NC}"
        print(f"  {label:<25} {status}")

    # SSL check
    ssl_result = run_cmd([
        "curl", "-s", "-o", "/dev/null", "-w", "%{ssl_verify_result}",
        url
    ], timeout=15)
    if ssl_result and ssl_result.stdout.strip() == "0":
        print(f"  {'SSL Sertifikasi':<25} {GREEN}Gecerli{NC}")
    else:
        print(f"  {'SSL Sertifikasi':<25} {RED}Sorunlu{NC}")
    print("")


# --- Subcommand Handlers ---

def cmd_init(args):
    """Add a new site to configuration."""
    domain = args.domain
    config = load_config()

    if domain in config.get("sites", {}):
        warn(f"{domain} zaten kayitli.")
        return

    config.setdefault("sites", {})[domain] = {
        "domain": domain,
        "framework": args.framework or "nextjs",
        "hosting": "vercel",
        "cdn": "cloudflare",
        "db": "supabase",
        "github_repo": args.repo or "",
        "repo_path": args.path or "",
        "cloudflare_zone_id": "",
        "supabase_project_id": "",
        "description": "",
    }

    save_config(config)
    info(f"{domain} eklendi. webops-sites.yml'i duzenleyerek detaylari doldurun.")


def cmd_status(args):
    """Show status of all sites and tools."""
    config = load_config()
    sites = config.get("sites", {})

    header("=== AI WebOps Durum Raporu ===")
    print("")

    # Tools
    tools = check_tools()
    print("  Araclar:")
    for name, available in tools.items():
        status = f"{GREEN}OK{NC}" if available else f"{YELLOW}Yok{NC}"
        print(f"    {name:<12} {status}")
    print("")

    # Sites
    if not sites:
        warn("Kayitli site yok. Ekleyin: ai-webops init site.com")
        return

    print("  Siteler:")
    for domain, cfg in sites.items():
        fw = cfg.get("framework", "?")
        hosting = cfg.get("hosting", "?")
        repo = cfg.get("github_repo", "-")
        desc = cfg.get("description", "")
        print(f"    {CYAN}{domain}{NC}")
        print(f"      Framework: {fw} | Hosting: {hosting}")
        if repo:
            print(f"      Repo: {repo}")
        if desc:
            print(f"      Aciklama: {desc}")
    print("")


def cmd_deploy(args):
    """Deploy a site."""
    config = load_config()
    site_cfg = get_site_config(config, args.domain)
    if not site_cfg:
        return

    hosting = site_cfg.get("hosting", "vercel")
    if hosting == "vercel":
        vercel_deploy(site_cfg, production=args.prod)
    else:
        error(f"Desteklenmeyen hosting: {hosting}")


def cmd_monitor(args):
    """Monitor all sites."""
    config = load_config()

    if args.loop:
        interval = config.get("defaults", {}).get("monitor_interval", 300)
        info(f"Surekli izleme modu ({interval}s aralik). Ctrl+C ile durdurun.")
        while True:
            monitor_all_sites(config)
            time.sleep(interval)
    else:
        monitor_all_sites(config)


def cmd_dns(args):
    """Cloudflare DNS operations."""
    config = load_config()
    site_cfg = get_site_config(config, args.domain)
    if not site_cfg:
        return

    action = args.action or "list"
    if action == "list":
        cloudflare_dns_list(site_cfg)
    elif action == "purge":
        cloudflare_purge_cache(site_cfg)
    else:
        error(f"Bilinmeyen DNS islemi: {action}")


def cmd_db(args):
    """Supabase database operations."""
    config = load_config()
    site_cfg = get_site_config(config, args.domain)
    if not site_cfg:
        return

    action = args.action or "status"
    if action == "status":
        supabase_status(site_cfg)
    elif action == "push":
        supabase_db_push(site_cfg)
    else:
        error(f"Bilinmeyen DB islemi: {action}")


def cmd_health(args):
    """Health and security check for a site."""
    check_site_health(args.domain)
    security_scan(args.domain)


def cmd_github(args):
    """GitHub operations for a site."""
    config = load_config()
    site_cfg = get_site_config(config, args.domain)
    if not site_cfg:
        return

    github_status(site_cfg)


# --- CLI ---

def build_parser():
    parser = argparse.ArgumentParser(
        prog="ai-webops",
        description="Linux-AI: Web proje yonetim ve operasyon araci"
    )
    sub = parser.add_subparsers(dest="command", help="Alt komutlar")

    # init
    p_init = sub.add_parser("init", help="Yeni site ekle")
    p_init.add_argument("domain", help="Site alan adi (ornek: renderhane.com)")
    p_init.add_argument("--framework", default="nextjs", help="Framework (nextjs, react, static)")
    p_init.add_argument("--repo", default="", help="GitHub repo (ornek: user/repo)")
    p_init.add_argument("--path", default="", help="Yerel repo yolu")
    p_init.set_defaults(func=cmd_init)

    # status
    p_status = sub.add_parser("status", help="Tum sitelerin durumu")
    p_status.set_defaults(func=cmd_status)

    # deploy
    p_deploy = sub.add_parser("deploy", help="Siteyi deploy et")
    p_deploy.add_argument("domain", help="Site alan adi")
    p_deploy.add_argument("--prod", action="store_true", help="Production deploy")
    p_deploy.set_defaults(func=cmd_deploy)

    # monitor
    p_monitor = sub.add_parser("monitor", help="Uptime ve saglik kontrolu")
    p_monitor.add_argument("--loop", action="store_true", help="Surekli izleme")
    p_monitor.set_defaults(func=cmd_monitor)

    # dns
    p_dns = sub.add_parser("dns", help="Cloudflare DNS yonetimi")
    p_dns.add_argument("domain", help="Site alan adi")
    p_dns.add_argument("action", nargs="?", default="list",
                        choices=["list", "purge"], help="Islem (list, purge)")
    p_dns.set_defaults(func=cmd_dns)

    # db
    p_db = sub.add_parser("db", help="Supabase veritabani islemleri")
    p_db.add_argument("domain", help="Site alan adi")
    p_db.add_argument("action", nargs="?", default="status",
                       choices=["status", "push"], help="Islem (status, push)")
    p_db.set_defaults(func=cmd_db)

    # health
    p_health = sub.add_parser("health", help="Performans ve guvenlik taramasi")
    p_health.add_argument("domain", help="Site alan adi")
    p_health.set_defaults(func=cmd_health)

    # github
    p_gh = sub.add_parser("github", help="GitHub repo islemleri")
    p_gh.add_argument("domain", help="Site alan adi")
    p_gh.set_defaults(func=cmd_github)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()

"""
ai_agent.py - Tool-calling AI agent for Linux-AI

Local AI agent that can:
  - Read/control system via kernel ioctl bridge
  - Manage web projects via API calls
  - Execute system commands (with user approval)
  - Monitor and optimize system resources

Uses Ollama for inference with tool/function calling.
All dangerous operations require explicit user confirmation.

Usage:
  ai-agent                    # Interaktif mod
  ai-agent "CPU durumunu gor" # Tek seferlik soru
  ai-agent --status           # Agent durumu
"""

import os
import sys
import json
import argparse
import subprocess
import shutil
import re
import time
from datetime import datetime

import psutil
import yaml

# Pre-compiled regex patterns for tool call parsing (avoid per-call recompilation)
_RE_TOOL_OBJECT = re.compile(r'\{[^{}]*"tool"\s*:\s*"[^"]+[^{}]*\}')
_RE_TOOL_ARRAY = re.compile(r'\[[\s\S]*?\{[^{}]*"tool"[^{}]*\}[\s\S]*?\]')

# --- Constants ---

TAG = "[ai-agent]"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
DIM = "\033[2m"
NC = "\033[0m"

AGENT_CONFIG_PATH = "/var/AI-stump/ai-agent.yml"

OLLAMA_MODEL_AGENT = "linux-ai-agent"
OLLAMA_MODEL_CODER = "linux-ai-coder"
OLLAMA_MODEL = OLLAMA_MODEL_AGENT  # Prefer agent model, fallback to coder
OLLAMA_API = "http://localhost:11434/api/chat"
MAX_MEMORY_MB = 300


# --- Config Loader ---

_config = None


def load_config():
    """Load agent configuration from YAML. Falls back to defaults."""
    global _config, OLLAMA_MODEL_AGENT, OLLAMA_MODEL_CODER, OLLAMA_API, MAX_MEMORY_MB

    if _config is not None:
        return _config

    _config = {}
    try:
        if os.path.exists(AGENT_CONFIG_PATH):
            with open(AGENT_CONFIG_PATH, "r") as f:
                _config = yaml.safe_load(f) or {}

            agent_cfg = _config.get("agent", {})
            if agent_cfg.get("model_primary"):
                OLLAMA_MODEL_AGENT = agent_cfg["model_primary"]
            if agent_cfg.get("model_fallback"):
                OLLAMA_MODEL_CODER = agent_cfg["model_fallback"]
            if agent_cfg.get("ollama_api"):
                OLLAMA_API = agent_cfg["ollama_api"] + "/api/chat"
            if agent_cfg.get("max_memory_mb"):
                MAX_MEMORY_MB = agent_cfg["max_memory_mb"]

            info(f"Konfigurasyon yuklendi: {AGENT_CONFIG_PATH}")
    except (yaml.YAMLError, IOError) as e:
        warn(f"Konfigurasyon okunamadi: {e} (varsayilanlar kullaniliyor)")

    return _config


# --- Output helpers ---

def info(msg):
    print(f"{GREEN}{TAG}{NC} {msg}")


def warn(msg):
    print(f"{YELLOW}{TAG}{NC} {msg}")


def error(msg):
    print(f"{RED}{TAG}{NC} {msg}")


def agent_say(msg):
    print(f"{CYAN}AI:{NC} {msg}")


def user_prompt():
    try:
        return input(f"\n{GREEN}Sen:{NC} ").strip()
    except (EOFError, KeyboardInterrupt):
        return None


# --- Tool Registry ---

TOOLS = []


def register_tool(name, description, func, requires_confirm=False, params=None):
    """Register a tool that the AI agent can call."""
    TOOLS.append({
        "name": name,
        "description": description,
        "function": func,
        "requires_confirm": requires_confirm,
        "params": params or {},
    })


def get_tools_prompt():
    """Generate tool description prompt for the model."""
    lines = ["You have access to these tools:\n"]
    for t in TOOLS:
        params_str = ""
        if t["params"]:
            params_str = f" Params: {json.dumps(t['params'])}"
        confirm = " [REQUIRES USER CONFIRMATION]" if t["requires_confirm"] else ""
        lines.append(f"- {t['name']}: {t['description']}{params_str}{confirm}")

    lines.append("\nTo use a tool, respond with JSON in this format:")
    lines.append('{"tool": "tool_name", "params": {"key": "value"}}')
    lines.append("\nYou can call multiple tools by returning a JSON array.")
    lines.append("If no tool is needed, respond normally in Turkish.")
    lines.append("Always explain what you're doing before calling tools.")
    return "\n".join(lines)


def find_tool(name):
    """Find a registered tool by name."""
    for t in TOOLS:
        if t["name"] == name:
            return t
    return None


# --- Built-in Tools ---

def tool_system_info():
    """Get current system information."""
    cpu_percent = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    cpu_freq = psutil.cpu_freq()

    result = {
        "cpu_percent": cpu_percent,
        "cpu_cores": psutil.cpu_count(logical=False),
        "cpu_threads": psutil.cpu_count(logical=True),
        "cpu_freq_mhz": int(cpu_freq.current) if cpu_freq else 0,
        "ram_total_mb": mem.total // (1024 * 1024),
        "ram_used_mb": mem.used // (1024 * 1024),
        "ram_percent": mem.percent,
        "disk_total_gb": disk.total // (1024 * 1024 * 1024),
        "disk_free_gb": disk.free // (1024 * 1024 * 1024),
        "disk_percent": disk.percent,
    }
    return json.dumps(result, indent=2)


def tool_process_list():
    """Get top processes by CPU usage."""
    procs = []
    for p in psutil.process_iter(attrs=["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info_dict = p.info
            if info_dict["cpu_percent"] and info_dict["cpu_percent"] > 0:
                procs.append(info_dict)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    procs.sort(key=lambda x: x["cpu_percent"], reverse=True)
    top = procs[:15]
    return json.dumps(top, indent=2)


def tool_kernel_status():
    """Get kernel module status via bridge."""
    try:
        from cbinder_gbfs.ai_kernel_bridge import KernelBridge
        kb = KernelBridge()
        if not kb.available:
            return json.dumps({"error": "Kernel modulu yuklenmemis"})
        snapshot = kb.get_system_snapshot()
        kb.close()
        return json.dumps(snapshot, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_kernel_set_governor(mode="ondemand"):
    """Set CPU governor (requires confirmation)."""
    try:
        from cbinder_gbfs.ai_kernel_bridge import KernelBridge
        kb = KernelBridge()
        kb.set_governor(mode)
        kb.close()
        return json.dumps({"success": True, "governor": mode})
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_read_file(path=""):
    """Read a file's contents (limited to project directory)."""
    if not path:
        return json.dumps({"error": "Dosya yolu gerekli"})

    # Safety: only allow reading from known safe locations
    safe_prefixes = ["/var/AI-stump/", "/proc/ai_", "/sys/ai/"]
    abs_path = os.path.abspath(path)

    allowed = any(abs_path.startswith(p) for p in safe_prefixes)
    if not allowed:
        return json.dumps({"error": f"Guvenlik: {path} okunamaz. Sadece AI config ve proc/sys yollari."})

    try:
        with open(abs_path, "r") as f:
            content = f.read(4096)  # Max 4KB
        return json.dumps({"path": abs_path, "content": content})
    except (FileNotFoundError, PermissionError) as e:
        return json.dumps({"error": str(e)})


def tool_site_health(domain=""):
    """Check website health."""
    if not domain:
        return json.dumps({"error": "Alan adi gerekli"})

    url = f"https://{domain}"
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w",
             '{"status":%{http_code},"time":%{time_total},"size":%{size_download}}',
             "-L", url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return result.stdout
        return json.dumps({"error": "Site erisilemez"})
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return json.dumps({"error": str(e)})


def tool_run_command(cmd=""):
    """Run a safe system command (requires confirmation)."""
    if not cmd:
        return json.dumps({"error": "Komut gerekli"})

    # Whitelist of allowed commands
    allowed_prefixes = [
        "systemctl status", "systemctl is-active",
        "df ", "free ", "uptime", "uname ",
        "ollama list", "ollama ps",
        "vercel ls", "vercel inspect",
        "supabase status",
        "gh pr list", "gh issue list",
        "ping -c 3 ",
    ]

    # Blacklist dangerous patterns
    dangerous = ["rm ", "dd ", "mkfs", "sudo rm", "> /dev/", "chmod 777",
                 "curl | sh", "wget | sh", "eval ", ";", "&&", "||", "`"]

    if any(d in cmd for d in dangerous):
        return json.dumps({"error": "Guvenlik: Tehlikeli komut reddedildi"})

    allowed = any(cmd.startswith(p) for p in allowed_prefixes)
    if not allowed:
        return json.dumps({"error": f"Guvenlik: '{cmd}' izin listesinde degil"})

    try:
        result = subprocess.run(
            cmd.split(), capture_output=True, text=True, timeout=30
        )
        output = result.stdout[:2048]  # Limit output
        return json.dumps({"returncode": result.returncode, "output": output})
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return json.dumps({"error": str(e)})


# --- Web API Tools (from ai_browser_agent) ---

def tool_vercel_projects():
    """List Vercel projects."""
    try:
        from cbinder_gbfs.ai_browser_agent import VercelAgent
        v = VercelAgent()
        data = _api_call_json("GET", f"{v.API}/v9/projects", v.token)
        if data and "projects" in data:
            projects = [{"name": p.get("name"), "framework": p.get("framework")}
                        for p in data["projects"]]
            return json.dumps(projects, indent=2, ensure_ascii=False)
        return json.dumps({"error": "Proje listesi alinamadi"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_vercel_deployments():
    """List recent Vercel deployments."""
    try:
        from cbinder_gbfs.ai_browser_agent import VercelAgent
        v = VercelAgent()
        data = _api_call_json("GET", f"{v.API}/v6/deployments?limit=5", v.token)
        if data and "deployments" in data:
            deploys = [{"state": d.get("state"), "url": d.get("url"),
                        "created": d.get("created")}
                       for d in data["deployments"]]
            return json.dumps(deploys, indent=2, ensure_ascii=False)
        return json.dumps({"error": "Deploy listesi alinamadi"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_cloudflare_zones():
    """List Cloudflare zones."""
    try:
        from cbinder_gbfs.ai_browser_agent import CloudflareAgent
        c = CloudflareAgent()
        data = _api_call_json("GET", f"{c.API}/zones", c.token)
        if data and data.get("success") and "result" in data:
            zones = [{"name": z.get("name"), "status": z.get("status"),
                      "id": z.get("id")} for z in data["result"]]
            return json.dumps(zones, indent=2, ensure_ascii=False)
        return json.dumps({"error": "Zone listesi alinamadi"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_cloudflare_purge(zone_id=""):
    """Purge Cloudflare cache for a zone (requires confirmation)."""
    if not zone_id:
        return json.dumps({"error": "zone_id gerekli"})
    try:
        from cbinder_gbfs.ai_browser_agent import CloudflareAgent
        c = CloudflareAgent()
        data = _api_call_json("POST",
                              f"{c.API}/zones/{zone_id}/purge_cache",
                              c.token, {"purge_everything": True})
        if data and data.get("success"):
            return json.dumps({"success": True, "message": "Cache temizlendi"})
        return json.dumps({"error": "Cache temizleme basarisiz"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_supabase_projects():
    """List Supabase projects."""
    try:
        from cbinder_gbfs.ai_browser_agent import SupabaseAgent
        s = SupabaseAgent()
        data = _api_call_json("GET", f"{s.API}/projects", s.token)
        if data and isinstance(data, list):
            projects = [{"name": p.get("name"), "region": p.get("region"),
                         "status": p.get("status"), "id": p.get("id")}
                        for p in data]
            return json.dumps(projects, indent=2, ensure_ascii=False)
        return json.dumps({"error": "Proje listesi alinamadi"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_github_repos(user=""):
    """List GitHub repos."""
    args = ["gh", "repo", "list"]
    if user:
        args.append(user)
    args.extend(["--limit", "10", "--json", "name,description,updatedAt"])
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return result.stdout[:2048]
        return json.dumps({"error": "Repo listesi alinamadi. 'gh auth login' calistirin."})
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return json.dumps({"error": str(e)})


def tool_github_prs(repo=""):
    """List open PRs for a repo."""
    if not repo:
        return json.dumps({"error": "repo gerekli (ornek: user/repo)"})
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "-R", repo, "--limit", "10",
             "--json", "title,state,author,createdAt"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return result.stdout[:2048] or json.dumps([])
        return json.dumps({"error": f"PR listesi alinamadi: {repo}"})
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return json.dumps({"error": str(e)})


def tool_coolify_apps():
    """List Coolify applications."""
    try:
        from cbinder_gbfs.ai_browser_agent import CoolifyAgent
        c = CoolifyAgent()
        data = c._call("GET", "/applications")
        if data and isinstance(data, list):
            apps = [{"name": a.get("name"), "fqdn": a.get("fqdn"),
                     "status": a.get("status"), "uuid": a.get("uuid")}
                    for a in data]
            return json.dumps(apps, indent=2, ensure_ascii=False)
        return json.dumps({"error": "Uygulama listesi alinamadi"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_coolify_servers():
    """List Coolify servers."""
    try:
        from cbinder_gbfs.ai_browser_agent import CoolifyAgent
        c = CoolifyAgent()
        data = c._call("GET", "/servers")
        if data and isinstance(data, list):
            servers = [{"name": s.get("name"), "ip": s.get("ip"),
                        "reachable": s.get("settings", {}).get("is_reachable")}
                       for s in data]
            return json.dumps(servers, indent=2, ensure_ascii=False)
        return json.dumps({"error": "Sunucu listesi alinamadi"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_coolify_deploy(app_uuid=""):
    """Deploy a Coolify application (requires confirmation)."""
    if not app_uuid:
        return json.dumps({"error": "app_uuid gerekli"})
    try:
        from cbinder_gbfs.ai_browser_agent import CoolifyAgent
        c = CoolifyAgent()
        data = c.deploy_application(app_uuid)
        if data:
            return json.dumps({"success": True, "message": f"Deploy baslatildi: {app_uuid}"})
        return json.dumps({"error": "Deploy baslatilamadi"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_coolify_restart(app_uuid=""):
    """Restart a Coolify application (requires confirmation)."""
    if not app_uuid:
        return json.dumps({"error": "app_uuid gerekli"})
    try:
        from cbinder_gbfs.ai_browser_agent import CoolifyAgent
        c = CoolifyAgent()
        data = c.restart_application(app_uuid)
        if data:
            return json.dumps({"success": True, "message": f"Yeniden baslatildi: {app_uuid}"})
        return json.dumps({"error": "Yeniden baslatma basarisiz"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_tailscale_status():
    """Get Tailscale VPN status and connected peers."""
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            self_node = data.get("Self", {})
            peers = data.get("Peer", {})
            ips = self_node.get("TailscaleIPs", [])
            online_peers = sum(1 for p in peers.values() if p.get("Online"))
            peer_list = [
                {"hostname": p.get("HostName", "?"),
                 "ip": p.get("TailscaleIPs", ["?"])[0] if p.get("TailscaleIPs") else "?",
                 "online": p.get("Online", False),
                 "os": p.get("OS", "?")}
                for p in peers.values()
            ]
            return json.dumps({
                "connected": self_node.get("Online", False),
                "hostname": self_node.get("HostName", "?"),
                "ip": ips[0] if ips else "?",
                "tailnet": data.get("MagicDNSSuffix", "?"),
                "peers_online": online_peers,
                "peers_total": len(peers),
                "peers": peer_list[:10],
            }, ensure_ascii=False)
        return "Tailscale calismıyor"
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return "Tailscale bulunamadi"


def tool_tailscale_ping(hostname=""):
    """Ping a peer on the Tailscale network."""
    if not hostname:
        return "hostname gerekli"
    try:
        result = subprocess.run(
            ["tailscale", "ping", "--c", "3", hostname],
            capture_output=True, text=True, timeout=15
        )
        return result.stdout or result.stderr or "Ping sonucu alinamadi"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "Tailscale ping calistirilamadi"


def _api_call_json(method, url, token, data=None):
    """Helper: authenticated API call, returns parsed JSON."""
    if not token:
        return None
    args = [
        "curl", "-s", "-X", method,
        "-H", f"Authorization: Bearer {token}",
        "-H", "Content-Type: application/json",
    ]
    if data:
        args.extend(["-d", json.dumps(data)])
    args.append(url)
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return None


# --- Register all tools ---

def register_all_tools():
    """Register built-in + web tools."""
    # System tools
    register_tool(
        "system_info", "Sistem bilgisi (CPU, RAM, disk kullanimi)",
        tool_system_info
    )
    register_tool(
        "process_list", "En cok CPU kullanan surecler",
        tool_process_list
    )
    register_tool(
        "kernel_status", "Linux-AI kernel modul durumu",
        tool_kernel_status
    )
    register_tool(
        "kernel_set_governor",
        "CPU governor modunu degistir (performance/powersave/ondemand/ai_adaptive)",
        tool_kernel_set_governor,
        requires_confirm=True,
        params={"mode": "str"}
    )
    register_tool(
        "read_file", "Konfigurasyon dosyasi oku (/var/AI-stump/ veya /proc/ai_*)",
        tool_read_file,
        params={"path": "str"}
    )
    register_tool(
        "site_health", "Web sitesi saglik kontrolu",
        tool_site_health,
        params={"domain": "str"}
    )
    register_tool(
        "run_command", "Guvenli sistem komutu calistir",
        tool_run_command,
        requires_confirm=True,
        params={"cmd": "str"}
    )

    # Web API tools
    register_tool(
        "vercel_projects", "Vercel projelerini listele",
        tool_vercel_projects
    )
    register_tool(
        "vercel_deployments", "Son Vercel deploy'larini listele",
        tool_vercel_deployments
    )
    register_tool(
        "cloudflare_zones", "Cloudflare alan adlarini (zone) listele",
        tool_cloudflare_zones
    )
    register_tool(
        "cloudflare_purge", "Cloudflare cache temizle",
        tool_cloudflare_purge,
        requires_confirm=True,
        params={"zone_id": "str"}
    )
    register_tool(
        "supabase_projects", "Supabase projelerini listele",
        tool_supabase_projects
    )
    register_tool(
        "github_repos", "GitHub repolarini listele",
        tool_github_repos,
        params={"user": "str (opsiyonel)"}
    )
    register_tool(
        "github_prs", "Acik PR'leri listele",
        tool_github_prs,
        params={"repo": "str (ornek: user/repo)"}
    )

    # Coolify tools
    register_tool(
        "coolify_apps", "Coolify uygulamalarini listele",
        tool_coolify_apps
    )
    register_tool(
        "coolify_servers", "Coolify sunucularini listele",
        tool_coolify_servers
    )
    register_tool(
        "coolify_deploy", "Coolify uygulamasi deploy et",
        tool_coolify_deploy,
        requires_confirm=True,
        params={"app_uuid": "str"}
    )
    register_tool(
        "coolify_restart", "Coolify uygulamasini yeniden baslat",
        tool_coolify_restart,
        requires_confirm=True,
        params={"app_uuid": "str"}
    )

    # Tailscale tools
    register_tool(
        "tailscale_status", "Tailscale VPN durumu ve bagli cihazlar",
        tool_tailscale_status
    )
    register_tool(
        "tailscale_ping", "Tailscale aginda peer'a ping at",
        tool_tailscale_ping,
        params={"hostname": "str"}
    )


# --- Ollama Communication ---

def ollama_available():
    """Check if Ollama is running."""
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/tags"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def detect_best_model():
    """Auto-detect best available model. Prefers agent (7B) over coder (3B)."""
    global OLLAMA_MODEL
    if not shutil.which("ollama"):
        return OLLAMA_MODEL
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return OLLAMA_MODEL
        output = result.stdout
        if OLLAMA_MODEL_AGENT in output:
            OLLAMA_MODEL = OLLAMA_MODEL_AGENT
            info(f"Agent modeli kullaniliyor: {OLLAMA_MODEL_AGENT} (7B, tool-calling)")
        elif OLLAMA_MODEL_CODER in output:
            OLLAMA_MODEL = OLLAMA_MODEL_CODER
            warn(f"Coder modeli kullaniliyor: {OLLAMA_MODEL_CODER} (3B)")
            warn("Daha iyi tool-calling icin: ai-dev-setup model-pull --agent")
        else:
            warn("Ozel model bulunamadi. Varsayilan Ollama modeli denenecek.")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return OLLAMA_MODEL


def ollama_chat(messages, model=OLLAMA_MODEL):
    """Send chat request to Ollama API. Returns response text."""
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "top_p": 0.9,
            "num_predict": 2048,
        }
    })

    try:
        result = subprocess.run(
            ["curl", "-s", "-X", "POST", OLLAMA_API,
             "-H", "Content-Type: application/json",
             "-d", payload],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("message", {}).get("content", "")
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


# --- Tool Call Parsing ---

def parse_tool_calls(text):
    """Extract tool call JSON from model response.

    Returns list of (tool_name, params) tuples and remaining text.
    """
    calls = []
    remaining = text

    # Try to find JSON objects or arrays in the response
    matches = _RE_TOOL_OBJECT.findall(text)

    for match in matches:
        try:
            obj = json.loads(match)
            if "tool" in obj:
                calls.append((obj["tool"], obj.get("params", {})))
                remaining = remaining.replace(match, "").strip()
        except json.JSONDecodeError:
            continue

    # Also try JSON array
    array_matches = _RE_TOOL_ARRAY.findall(text)
    for match in array_matches:
        try:
            arr = json.loads(match)
            for obj in arr:
                if isinstance(obj, dict) and "tool" in obj:
                    calls.append((obj["tool"], obj.get("params", {})))
            remaining = remaining.replace(match, "").strip()
        except json.JSONDecodeError:
            continue

    return calls, remaining


def confirm_action(tool_name, params):
    """Ask user to confirm a dangerous action."""
    print(f"\n{YELLOW}[ONAY GEREKLI]{NC} {tool_name}")
    if params:
        print(f"  Parametreler: {json.dumps(params, ensure_ascii=False)}")

    try:
        answer = input(f"  Onayliyor musunuz? (e/h): ").strip().lower()
        return answer in ("e", "evet", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


# --- Agent Loop ---

def execute_tool_calls(calls):
    """Execute parsed tool calls with confirmation for dangerous ops."""
    results = []
    for tool_name, params in calls:
        tool = find_tool(tool_name)
        if not tool:
            results.append(f"[Hata: '{tool_name}' araci bulunamadi]")
            continue

        # Confirm if needed
        if tool["requires_confirm"]:
            if not confirm_action(tool_name, params):
                results.append(f"[{tool_name}: Kullanici tarafindan reddedildi]")
                continue

        # Execute
        try:
            print(f"{DIM}  -> {tool_name} calistiriliyor...{NC}")
            result = tool["function"](**params)
            results.append(f"[{tool_name} sonucu]:\n{result}")
        except Exception as e:
            results.append(f"[{tool_name} hatasi]: {e}")

    return "\n".join(results)


def run_agent_loop():
    """Main interactive agent loop."""
    load_config()

    print("")
    print("=========================================")
    print("  Linux-AI Agent - Yerel AI Asistani")
    print("  Cikis: 'q' veya Ctrl+C")
    print("=========================================")
    print("")

    if not ollama_available():
        error("Ollama calismiyor. Baslatin: ollama serve")
        sys.exit(1)

    detect_best_model()
    print(f"  Model: {OLLAMA_MODEL}")
    print(f"  Araclar: {len(TOOLS)} kayitli")
    print("")
    register_all_tools()

    # System message with tool definitions
    system_msg = (
        "Sen Linux-AI projesinin yerel AI asistanisin. "
        "Kullanicinin sistemini izle, optimize et ve web projelerini yonet. "
        "Turkce konusuyorsun. Kisa ve net cevap ver.\n\n"
        + get_tools_prompt()
    )

    messages = [{"role": "system", "content": system_msg}]

    while True:
        user_input = user_prompt()
        if user_input is None or user_input.lower() in ("q", "quit", "exit", "cik"):
            info("Agent kapatiliyor.")
            break

        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        # Get model response
        print(f"{DIM}  Dusunuyor...{NC}")
        response = ollama_chat(messages)

        if response is None:
            error("Model yanit vermedi. Ollama calisiyor mu?")
            messages.pop()  # Remove failed message
            continue

        # Parse tool calls
        tool_calls, text_response = parse_tool_calls(response)

        # Print text response (if any)
        if text_response:
            agent_say(text_response)

        # Execute tool calls
        if tool_calls:
            tool_results = execute_tool_calls(tool_calls)

            if tool_results:
                # Feed results back to model for interpretation
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content":
                    f"Arac sonuclari:\n{tool_results}\n\nBu sonuclari yorumla ve Turkce acikla."
                })

                print(f"{DIM}  Sonuclari yorumluyor...{NC}")
                interpretation = ollama_chat(messages)
                if interpretation:
                    agent_say(interpretation)
                    messages.append({"role": "assistant", "content": interpretation})
                else:
                    # Just show raw results
                    print(tool_results)
                    messages.append({"role": "assistant", "content": tool_results})
        else:
            messages.append({"role": "assistant", "content": response})

        # Keep context manageable (last 20 messages)
        if len(messages) > 22:  # system + 20 messages
            messages = [messages[0]] + messages[-20:]


def run_single_query(query):
    """Run a single query and exit."""
    load_config()

    if not ollama_available():
        error("Ollama calismiyor.")
        sys.exit(1)

    detect_best_model()
    register_all_tools()

    system_msg = (
        "Sen Linux-AI asistanisin. Turkce kisa cevap ver.\n\n"
        + get_tools_prompt()
    )

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": query}
    ]

    response = ollama_chat(messages)
    if response is None:
        error("Model yanit vermedi.")
        sys.exit(1)

    tool_calls, text_response = parse_tool_calls(response)

    if text_response:
        print(text_response)

    if tool_calls:
        results = execute_tool_calls(tool_calls)
        if results:
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content":
                f"Arac sonuclari:\n{results}\n\nKisaca yorumla."
            })
            interpretation = ollama_chat(messages)
            if interpretation:
                print(interpretation)
            else:
                print(results)


def show_agent_status():
    """Show agent capabilities and status."""
    register_all_tools()

    print("\n=== Linux-AI Agent Durumu ===\n")

    # Ollama
    if ollama_available():
        print(f"  Ollama:  {GREEN}Calisiyor{NC}")
    else:
        print(f"  Ollama:  {RED}Calismiyor{NC}")

    # Model
    if shutil.which("ollama"):
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and OLLAMA_MODEL in result.stdout:
            print(f"  Model:   {GREEN}{OLLAMA_MODEL}{NC}")
        else:
            print(f"  Model:   {YELLOW}{OLLAMA_MODEL} (bulunamadi){NC}")

    # Kernel
    if os.path.exists("/dev/ai_ctl"):
        print(f"  Kernel:  {GREEN}/dev/ai_ctl mevcut{NC}")
    else:
        print(f"  Kernel:  {YELLOW}Modul yuklenmemis{NC}")

    # Tools
    print(f"\n  Kayitli Araclar ({len(TOOLS)}):")
    for t in TOOLS:
        confirm = f" {YELLOW}[onay gerekli]{NC}" if t["requires_confirm"] else ""
        print(f"    - {t['name']}: {t['description']}{confirm}")

    print("")


# --- CLI ---

def main():
    global OLLAMA_MODEL
    parser = argparse.ArgumentParser(
        prog="ai-agent",
        description="Linux-AI: Yerel AI asistan (tool-calling destekli)"
    )
    parser.add_argument("query", nargs="?", default=None,
                        help="Tek seferlik soru")
    parser.add_argument("--status", action="store_true",
                        help="Agent durumunu goster")
    parser.add_argument("--model", default=OLLAMA_MODEL,
                        help=f"Ollama model (varsayilan: {OLLAMA_MODEL})")
    args = parser.parse_args()

    if args.model != OLLAMA_MODEL_AGENT:
        OLLAMA_MODEL = args.model  # User explicitly specified a model

    if args.status:
        show_agent_status()
    elif args.query:
        run_single_query(args.query)
    else:
        run_agent_loop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{TAG} Kapatildi.")

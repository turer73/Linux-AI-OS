"""
ai_browser_agent.py - Web API automation agent for Linux-AI

Automates web operations through APIs (no browser needed):
  - Vercel: deploy, domains, environment variables
  - Cloudflare: DNS, cache, security rules, analytics
  - Supabase: DB queries, migrations, auth management
  - GitHub: repos, PRs, issues, actions
  - Fal.ai: AI model inference
  - HuggingFace: model management

All API calls use environment tokens. No credentials stored in code.

Usage:
  ai-web-agent vercel deploy renderhane.com
  ai-web-agent cloudflare analytics renderhane.com
  ai-web-agent supabase query kokenakademi.com "SELECT count(*) FROM users"
  ai-web-agent github prs 3d-labx.com
  ai-web-agent fal generate "3D model of a castle"
"""

import os
import sys
import json
import argparse
import subprocess

# --- Constants ---

TAG = "[ai-web-agent]"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BOLD = "\033[1m"
NC = "\033[0m"


def info(msg):
    print(f"{GREEN}{TAG}{NC} {msg}")


def warn(msg):
    print(f"{YELLOW}{TAG}{NC} {msg}")


def error(msg):
    print(f"{RED}{TAG}{NC} {msg}")


def api_call(method, url, token, data=None):
    """Make an authenticated API call via curl. Returns parsed JSON."""
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


def get_token(env_var):
    """Get API token from environment."""
    token = os.environ.get(env_var, "")
    if not token:
        error(f"{env_var} ortam degiskeni ayarlanmamis.")
        warn(f"  export {env_var}=your_token")
    return token


# --- Vercel Operations ---

class VercelAgent:
    API = "https://api.vercel.com"

    def __init__(self):
        self.token = get_token("VERCEL_TOKEN")

    def list_projects(self):
        """List Vercel projects."""
        if not self.token:
            return
        data = api_call("GET", f"{self.API}/v9/projects", self.token)
        if data and "projects" in data:
            info("Vercel Projeleri:")
            for p in data["projects"]:
                name = p.get("name", "?")
                framework = p.get("framework", "?")
                updated = p.get("updatedAt", "?")
                print(f"  {name} ({framework}) - guncelleme: {updated}")
        else:
            warn("Proje listesi alinamadi.")

    def list_deployments(self, project=None, limit=5):
        """List recent deployments."""
        if not self.token:
            return
        url = f"{self.API}/v6/deployments?limit={limit}"
        if project:
            url += f"&projectId={project}"
        data = api_call("GET", url, self.token)
        if data and "deployments" in data:
            info("Son Deploy'lar:")
            for d in data["deployments"]:
                state = d.get("state", "?")
                url_str = d.get("url", "?")
                created = d.get("created", "?")
                color = GREEN if state == "READY" else YELLOW
                print(f"  {color}{state}{NC} {url_str} ({created})")

    def get_env_vars(self, project_id):
        """List environment variables for a project."""
        if not self.token:
            return
        data = api_call("GET", f"{self.API}/v9/projects/{project_id}/env", self.token)
        if data and "envs" in data:
            info(f"Ortam Degiskenleri ({project_id}):")
            for env in data["envs"]:
                key = env.get("key", "?")
                target = ",".join(env.get("target", []))
                print(f"  {key} -> [{target}]")


# --- Cloudflare Operations ---

class CloudflareAgent:
    API = "https://api.cloudflare.com/client/v4"

    def __init__(self):
        self.token = get_token("CLOUDFLARE_API_TOKEN")

    def list_zones(self):
        """List all Cloudflare zones (domains)."""
        if not self.token:
            return
        data = api_call("GET", f"{self.API}/zones", self.token)
        if data and data.get("success") and "result" in data:
            info("Cloudflare Zone'lar:")
            for z in data["result"]:
                name = z.get("name", "?")
                status = z.get("status", "?")
                zone_id = z.get("id", "?")
                color = GREEN if status == "active" else YELLOW
                print(f"  {color}{name}{NC} ({status}) ID: {zone_id}")

    def get_analytics(self, zone_id, days=7):
        """Get zone analytics summary."""
        if not self.token:
            return
        url = (f"{self.API}/zones/{zone_id}/analytics/dashboard"
               f"?since=-{days * 1440}&continuous=true")
        data = api_call("GET", url, self.token)
        if data and data.get("success"):
            totals = data.get("result", {}).get("totals", {})
            requests_data = totals.get("requests", {})
            bandwidth = totals.get("bandwidth", {})
            threats = totals.get("threats", {})
            info(f"Analitik (son {days} gun):")
            print(f"  Istek:     {requests_data.get('all', 0):,}")
            print(f"  Onbellek:  {requests_data.get('cached', 0):,}")
            print(f"  Bant gen:  {bandwidth.get('all', 0) / (1024*1024):.1f} MB")
            print(f"  Tehdit:    {threats.get('all', 0)}")

    def purge_cache(self, zone_id):
        """Purge all cache for a zone."""
        if not self.token:
            return
        data = api_call("POST", f"{self.API}/zones/{zone_id}/purge_cache",
                        self.token, {"purge_everything": True})
        if data and data.get("success"):
            info("Cache temizlendi!")
        else:
            error("Cache temizleme basarisiz.")

    # --- WAF (Web Application Firewall) ---

    def list_waf_rules(self, zone_id):
        """List custom WAF rules (firewall rules) for a zone."""
        if not self.token:
            return
        data = api_call("GET", f"{self.API}/zones/{zone_id}/firewall/rules", self.token)
        if data and data.get("success") and "result" in data:
            rules = data["result"]
            if not rules:
                info("WAF kurali yok.")
                return rules
            info(f"WAF Kurallari ({len(rules)}):")
            for r in rules:
                rid = r.get("id", "?")[:12]
                desc = r.get("description", "(isimsiz)")
                action = r.get("action", "?")
                paused = r.get("paused", False)
                status_str = f"{RED}duraklatildi{NC}" if paused else f"{GREEN}aktif{NC}"
                action_color = RED if action == "block" else \
                               YELLOW if action == "challenge" else GREEN
                print(f"  [{rid}] {desc:40s} "
                      f"{action_color}{action:12s}{NC} {status_str}")
            return rules
        return []

    def create_waf_rule(self, zone_id, description, expression, action="block"):
        """Create a new WAF firewall rule.

        Args:
            zone_id: Cloudflare zone ID
            description: Human-readable rule description
            expression: Cloudflare filter expression
                Examples:
                  - '(ip.src eq 1.2.3.4)'
                  - '(http.request.uri.path contains "/wp-admin")'
                  - '(ip.geoip.country eq "XX")'
                  - '(cf.threat_score gt 50)'
            action: block, challenge, js_challenge, managed_challenge, allow, log
        """
        if not self.token:
            return None
        valid_actions = ["block", "challenge", "js_challenge",
                         "managed_challenge", "allow", "log"]
        if action not in valid_actions:
            error(f"Gecersiz aksiyon: {action}. Gecerli: {', '.join(valid_actions)}")
            return None

        # First create the filter
        filter_data = api_call(
            "POST", f"{self.API}/zones/{zone_id}/filters",
            self.token, [{"expression": expression}]
        )
        if not filter_data or not filter_data.get("success"):
            error(f"Filter olusturulamadi: {filter_data}")
            return None

        filter_id = filter_data["result"][0]["id"]

        # Then create the firewall rule
        rule_data = api_call(
            "POST", f"{self.API}/zones/{zone_id}/firewall/rules",
            self.token, [{
                "filter": {"id": filter_id},
                "action": action,
                "description": description,
            }]
        )
        if rule_data and rule_data.get("success"):
            rule = rule_data["result"][0]
            info(f"WAF kurali olusturuldu: {rule.get('id', '?')}")
            info(f"  Aciklama: {description}")
            info(f"  Aksiyon:  {action}")
            info(f"  Filtre:   {expression}")
            return rule
        else:
            error(f"WAF kurali olusturulamadi: {rule_data}")
            return None

    def delete_waf_rule(self, zone_id, rule_id):
        """Delete a WAF firewall rule."""
        if not self.token:
            return False
        data = api_call(
            "DELETE", f"{self.API}/zones/{zone_id}/firewall/rules/{rule_id}",
            self.token
        )
        if data and data.get("success"):
            info(f"WAF kurali silindi: {rule_id}")
            return True
        else:
            error(f"WAF kurali silinemedi: {rule_id}")
            return False

    def toggle_waf_rule(self, zone_id, rule_id, paused=True):
        """Pause or unpause a WAF rule."""
        if not self.token:
            return False
        data = api_call(
            "PATCH", f"{self.API}/zones/{zone_id}/firewall/rules/{rule_id}",
            self.token, {"paused": paused}
        )
        if data and data.get("success"):
            state = "duraklatildi" if paused else "etkinlestirildi"
            info(f"WAF kurali {state}: {rule_id}")
            return True
        return False

    def block_ip(self, zone_id, ip_address, description=""):
        """Quick helper: block a specific IP address."""
        desc = description or f"IP engelle: {ip_address}"
        expression = f'(ip.src eq {ip_address})'
        return self.create_waf_rule(zone_id, desc, expression, "block")

    def block_country(self, zone_id, country_code, description=""):
        """Quick helper: block traffic from a country."""
        cc = country_code.upper()
        desc = description or f"Ulke engelle: {cc}"
        expression = f'(ip.geoip.country eq "{cc}")'
        return self.create_waf_rule(zone_id, desc, expression, "block")

    def challenge_high_threat(self, zone_id, threshold=50):
        """Quick helper: challenge visitors with high threat score."""
        desc = f"Yuksek tehdit skoru (>{threshold})"
        expression = f'(cf.threat_score gt {threshold})'
        return self.create_waf_rule(zone_id, desc, expression, "managed_challenge")

    def protect_admin_paths(self, zone_id, paths=None):
        """Quick helper: protect admin/login paths with challenge."""
        if paths is None:
            paths = ["/wp-admin", "/wp-login.php", "/admin", "/administrator"]
        conditions = " or ".join(
            f'http.request.uri.path contains "{p}"' for p in paths
        )
        expression = f"({conditions})"
        desc = "Admin yollarini koru"
        return self.create_waf_rule(zone_id, desc, expression, "managed_challenge")


# --- Supabase Operations ---

class SupabaseAgent:
    API = "https://api.supabase.com/v1"

    def __init__(self):
        self.token = get_token("SUPABASE_ACCESS_TOKEN")

    def list_projects(self):
        """List Supabase projects."""
        if not self.token:
            return
        data = api_call("GET", f"{self.API}/projects", self.token)
        if data and isinstance(data, list):
            info("Supabase Projeleri:")
            for p in data:
                name = p.get("name", "?")
                region = p.get("region", "?")
                status = p.get("status", "?")
                ref = p.get("id", "?")
                color = GREEN if status == "ACTIVE_HEALTHY" else YELLOW
                print(f"  {color}{name}{NC} ({region}) ref: {ref}")

    def get_project_health(self, project_ref):
        """Check project health."""
        if not self.token:
            return
        data = api_call("GET", f"{self.API}/projects/{project_ref}/health", self.token)
        if data:
            info(f"Proje Sagligi ({project_ref}):")
            for service, status in data.items():
                color = GREEN if status == "healthy" else RED
                print(f"  {service}: {color}{status}{NC}")


# --- GitHub Operations ---

class GitHubAgent:
    """GitHub operations via gh CLI."""

    def list_repos(self, user=""):
        """List repositories."""
        args = ["gh", "repo", "list"]
        if user:
            args.append(user)
        args.extend(["--limit", "10"])

        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                info("GitHub Repolar:")
                print(result.stdout)
            else:
                error("Repo listesi alinamadi. 'gh auth login' calistirin.")
        except FileNotFoundError:
            error("gh bulunamadi. Kurun: https://cli.github.com/")

    def list_prs(self, repo):
        """List open PRs for a repo."""
        try:
            result = subprocess.run(
                ["gh", "pr", "list", "-R", repo, "--limit", "10"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                info(f"Acik PR'ler ({repo}):")
                print(result.stdout or "  (yok)")
        except FileNotFoundError:
            error("gh bulunamadi.")

    def list_issues(self, repo):
        """List open issues for a repo."""
        try:
            result = subprocess.run(
                ["gh", "issue", "list", "-R", repo, "--limit", "10"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                info(f"Acik Issue'lar ({repo}):")
                print(result.stdout or "  (yok)")
        except FileNotFoundError:
            error("gh bulunamadi.")


# --- Fal.ai Operations ---

class FalAgent:
    API = "https://fal.run"

    def __init__(self):
        self.token = get_token("FAL_KEY")

    def run_model(self, model_id, input_data):
        """Run a Fal.ai model."""
        if not self.token:
            return None
        url = f"{self.API}/{model_id}"
        info(f"Fal.ai model calistiriliyor: {model_id}")
        data = api_call("POST", url, self.token, input_data)
        if data:
            info("Sonuc alindi.")
            return data
        error("Model calistirma basarisiz.")
        return None


# --- Coolify Operations (Self-hosting) ---

class CoolifyAgent:
    """Coolify self-hosting platform management via API."""

    def __init__(self, api_base=None):
        self.token = get_token("COOLIFY_API_TOKEN")
        # API base: http://<ip>:8000/api/v1
        self.api_base = api_base or os.environ.get(
            "COOLIFY_API_BASE", "http://localhost:8000/api/v1"
        )

    def _call(self, method, endpoint, data=None):
        """Make Coolify API call."""
        if not self.token:
            return None
        url = f"{self.api_base}{endpoint}"
        return api_call(method, url, self.token, data)

    def get_version(self):
        """Get Coolify version."""
        data = self._call("GET", "/../version")
        if data:
            info(f"Coolify versiyon: {data}")
            return data
        warn("Coolify API'ye erisilemedi.")
        return None

    def list_servers(self):
        """List all servers managed by Coolify."""
        data = self._call("GET", "/servers")
        if data and isinstance(data, list):
            info("Coolify Sunuculari:")
            for s in data:
                name = s.get("name", "?")
                ip = s.get("ip", "?")
                status = s.get("settings", {}).get("is_reachable", False)
                color = GREEN if status else RED
                print(f"  {color}{name}{NC} ({ip}) "
                      f"{'erisilebilir' if status else 'erisilemez'}")
            return data
        warn("Sunucu listesi alinamadi.")
        return None

    def list_applications(self):
        """List all deployed applications."""
        data = self._call("GET", "/applications")
        if data and isinstance(data, list):
            info("Coolify Uygulamalari:")
            for app in data:
                name = app.get("name", "?")
                fqdn = app.get("fqdn", "?")
                status = app.get("status", "?")
                color = GREEN if status == "running" else YELLOW
                print(f"  {color}{name}{NC} -> {fqdn} [{status}]")
            return data
        warn("Uygulama listesi alinamadi.")
        return None

    def list_databases(self):
        """List all databases."""
        data = self._call("GET", "/databases")
        if data and isinstance(data, list):
            info("Coolify Veritabanlari:")
            for db in data:
                name = db.get("name", "?")
                db_type = db.get("type", "?")
                status = db.get("status", "?")
                color = GREEN if status == "running" else YELLOW
                print(f"  {color}{name}{NC} ({db_type}) [{status}]")
            return data
        warn("Veritabani listesi alinamadi.")
        return None

    def list_services(self):
        """List all one-click services."""
        data = self._call("GET", "/services")
        if data and isinstance(data, list):
            info("Coolify Servisler:")
            for svc in data:
                name = svc.get("name", "?")
                svc_type = svc.get("type", "?")
                status = svc.get("status", "?")
                color = GREEN if status == "running" else YELLOW
                print(f"  {color}{name}{NC} ({svc_type}) [{status}]")
            return data
        warn("Servis listesi alinamadi.")
        return None

    def deploy_application(self, app_uuid):
        """Trigger deployment for an application (requires confirmation)."""
        if not app_uuid:
            error("Uygulama UUID gerekli.")
            return None
        data = self._call("POST", f"/applications/{app_uuid}/deploy")
        if data:
            info(f"Deploy baslatildi: {app_uuid}")
            return data
        error("Deploy baslatilamadi.")
        return None

    def get_deployments(self, app_uuid):
        """Get deployment history for an application."""
        data = self._call("GET", f"/applications/{app_uuid}/deployments")
        if data and isinstance(data, list):
            info(f"Deploy Gecmisi ({app_uuid[:8]}...):")
            for d in data[:5]:
                status = d.get("status", "?")
                created = d.get("created_at", "?")
                color = GREEN if status == "finished" else YELLOW
                print(f"  {color}{status}{NC} - {created}")
            return data
        warn("Deploy gecmisi alinamadi.")
        return None

    def restart_application(self, app_uuid):
        """Restart an application (requires confirmation)."""
        data = self._call("POST", f"/applications/{app_uuid}/restart")
        if data:
            info(f"Yeniden baslatildi: {app_uuid}")
            return data
        error("Yeniden baslatma basarisiz.")
        return None

    def stop_application(self, app_uuid):
        """Stop an application (requires confirmation)."""
        data = self._call("POST", f"/applications/{app_uuid}/stop")
        if data:
            info(f"Durduruldu: {app_uuid}")
            return data
        error("Durdurma basarisiz.")
        return None


# --- Tailscale VPN Operations ---

class TailscaleAgent:
    """Tailscale mesh VPN management via CLI."""

    def __init__(self):
        self._check_installed()

    def _check_installed(self):
        """Check if tailscale CLI is available."""
        try:
            result = subprocess.run(
                ["tailscale", "version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                self.version = result.stdout.strip().split("\n")[0]
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        self.version = None
        return False

    def status(self):
        """Get Tailscale network status and connected peers."""
        try:
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                self_node = data.get("Self", {})
                peers = data.get("Peer", {})

                info("Tailscale Durumu:")
                # Self info
                hostname = self_node.get("HostName", "?")
                tailnet = data.get("MagicDNSSuffix", "?")
                addrs = self_node.get("TailscaleIPs", [])
                ip_str = ", ".join(addrs[:2]) if addrs else "?"
                online = self_node.get("Online", False)
                color = GREEN if online else RED

                print(f"  {BOLD}Bu Cihaz:{NC}")
                print(f"    Hostname:  {color}{hostname}{NC}")
                print(f"    IP:        {ip_str}")
                print(f"    Tailnet:   {tailnet}")
                print(f"    Durum:     {color}{'cevrimici' if online else 'cevrimdisi'}{NC}")

                # Peers
                if peers:
                    print(f"\n  {BOLD}Bagla Cihazlar ({len(peers)}):{NC}")
                    for _peer_id, peer in peers.items():
                        p_host = peer.get("HostName", "?")
                        p_ips = peer.get("TailscaleIPs", [])
                        p_ip = p_ips[0] if p_ips else "?"
                        p_online = peer.get("Online", False)
                        p_os = peer.get("OS", "?")
                        p_exit = peer.get("ExitNode", False)
                        p_color = GREEN if p_online else RED

                        tags = []
                        if p_exit:
                            tags.append("exit-node")
                        if peer.get("ExitNodeOption", False):
                            tags.append("exit-capable")
                        tag_str = f" [{', '.join(tags)}]" if tags else ""

                        print(f"    {p_color}{p_host:20s}{NC} {p_ip:18s} "
                              f"{p_os:10s} "
                              f"{'online' if p_online else 'offline'}"
                              f"{tag_str}")

                return data
            else:
                if "not running" in (result.stderr or "").lower():
                    warn("Tailscale calismıyor. 'sudo tailscale up' ile baslatin.")
                else:
                    error(f"Tailscale status hatasi: {result.stderr[:200]}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            error("Tailscale bulunamadi. Kurun: https://tailscale.com/download/linux")
        except json.JSONDecodeError:
            error("Tailscale ciktisi okunamadi.")
        return None

    def get_ip(self, hostname=None):
        """Get Tailscale IP for self or a peer."""
        args = ["tailscale", "ip", "-4"]
        if hostname:
            args.append(hostname)
        try:
            result = subprocess.run(
                args, capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                ip = result.stdout.strip()
                if hostname:
                    info(f"{hostname} -> {ip}")
                else:
                    info(f"Bu cihaz -> {ip}")
                return ip
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def ping_peer(self, hostname):
        """Ping a peer on the Tailscale network."""
        try:
            result = subprocess.run(
                ["tailscale", "ping", "--c", "3", hostname],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                info(f"Ping -> {hostname}:")
                print(result.stdout)
                return True
            else:
                error(f"Ping basarisiz: {hostname}")
                if result.stderr:
                    print(result.stderr[:200])
        except (FileNotFoundError, subprocess.TimeoutExpired):
            error("Tailscale ping calistirilamadi.")
        return False

    def netcheck(self):
        """Run network diagnostic check."""
        try:
            result = subprocess.run(
                ["tailscale", "netcheck"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                info("Ag Diagnostigi:")
                print(result.stdout)
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        error("Netcheck calistirilamadi.")
        return False

    def serve_port(self, port, proto="https"):
        """Expose a local port via Tailscale serve."""
        try:
            result = subprocess.run(
                ["tailscale", "serve", f"--{proto}={port}",
                 f"http://127.0.0.1:{port}"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                info(f"Port {port} Tailscale uzerinden paylasiliyor ({proto})")
                return True
            else:
                error(f"Serve hatasi: {result.stderr[:200]}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            error("Tailscale serve calistirilamadi.")
        return False

    def serve_off(self):
        """Stop all Tailscale serve instances."""
        try:
            result = subprocess.run(
                ["tailscale", "serve", "--remove", "/"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                info("Tailscale serve durduruldu.")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return False

    def up(self, exit_node=False, ssh=False, advertise_routes=None):
        """Connect to Tailscale with options."""
        args = ["tailscale", "up"]
        if exit_node:
            args.append("--advertise-exit-node")
        if ssh:
            args.append("--ssh")
        if advertise_routes:
            args.extend(["--advertise-routes", advertise_routes])

        try:
            result = subprocess.run(
                args, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                info("Tailscale baglandi.")
                return True
            else:
                error(f"Tailscale up hatasi: {result.stderr[:200]}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            error("Tailscale calistirilamadi.")
        return False

    def down(self):
        """Disconnect from Tailscale."""
        try:
            result = subprocess.run(
                ["tailscale", "down"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                info("Tailscale baglantisi kesildi.")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return False


# --- Tool definitions for AI agent integration ---

WEB_TOOLS = [
    {
        "name": "vercel_projects",
        "description": "Vercel projelerini listele",
        "requires_confirm": False,
    },
    {
        "name": "vercel_deployments",
        "description": "Son deploy'lari listele",
        "requires_confirm": False,
    },
    {
        "name": "cloudflare_zones",
        "description": "Cloudflare alan adlarini listele",
        "requires_confirm": False,
    },
    {
        "name": "cloudflare_analytics",
        "description": "Site analitiklerini goster",
        "requires_confirm": False,
        "params": {"zone_id": "str", "days": "int"},
    },
    {
        "name": "cloudflare_purge",
        "description": "Cloudflare cache'ini temizle",
        "requires_confirm": True,
        "params": {"zone_id": "str"},
    },
    {
        "name": "cloudflare_waf_list",
        "description": "WAF guvenlik duvarı kurallarini listele",
        "requires_confirm": False,
        "params": {"zone_id": "str"},
    },
    {
        "name": "cloudflare_waf_create",
        "description": "Yeni WAF kurali olustur",
        "requires_confirm": True,
        "params": {"zone_id": "str", "description": "str",
                   "expression": "str", "action": "str"},
    },
    {
        "name": "cloudflare_waf_delete",
        "description": "WAF kuralini sil",
        "requires_confirm": True,
        "params": {"zone_id": "str", "rule_id": "str"},
    },
    {
        "name": "cloudflare_block_ip",
        "description": "IP adresini engelle",
        "requires_confirm": True,
        "params": {"zone_id": "str", "ip": "str"},
    },
    {
        "name": "supabase_projects",
        "description": "Supabase projelerini listele",
        "requires_confirm": False,
    },
    {
        "name": "github_repos",
        "description": "GitHub repolarini listele",
        "requires_confirm": False,
    },
    {
        "name": "github_prs",
        "description": "Acik PR'leri listele",
        "requires_confirm": False,
        "params": {"repo": "str"},
    },
    {
        "name": "site_health",
        "description": "Site saglik kontrolu",
        "requires_confirm": False,
        "params": {"domain": "str"},
    },
    {
        "name": "coolify_servers",
        "description": "Coolify sunucularini listele",
        "requires_confirm": False,
    },
    {
        "name": "coolify_apps",
        "description": "Coolify uygulamalarini listele",
        "requires_confirm": False,
    },
    {
        "name": "coolify_databases",
        "description": "Coolify veritabanlarini listele",
        "requires_confirm": False,
    },
    {
        "name": "coolify_deploy",
        "description": "Coolify uygulamasi deploy et",
        "requires_confirm": True,
        "params": {"app_uuid": "str"},
    },
    {
        "name": "coolify_restart",
        "description": "Coolify uygulamasini yeniden baslat",
        "requires_confirm": True,
        "params": {"app_uuid": "str"},
    },
    {
        "name": "tailscale_status",
        "description": "Tailscale VPN durumu ve bagli cihazlar",
        "requires_confirm": False,
    },
    {
        "name": "tailscale_ping",
        "description": "Tailscale agiyla peer'a ping at",
        "requires_confirm": False,
        "params": {"hostname": "str"},
    },
    {
        "name": "tailscale_serve",
        "description": "Yerel portu Tailscale uzerinden paylas",
        "requires_confirm": True,
        "params": {"port": "int"},
    },
]


# --- CLI ---

def cmd_vercel(args):
    v = VercelAgent()
    action = args.action or "projects"
    if action == "projects":
        v.list_projects()
    elif action == "deploys":
        v.list_deployments()
    elif action == "env" and args.project:
        v.get_env_vars(args.project)


def cmd_cloudflare(args):
    c = CloudflareAgent()
    action = args.action or "zones"
    if action == "zones":
        c.list_zones()
    elif action == "analytics" and args.zone_id:
        c.get_analytics(args.zone_id, days=args.days or 7)
    elif action == "purge" and args.zone_id:
        c.purge_cache(args.zone_id)
    elif action == "waf-list" and args.zone_id:
        c.list_waf_rules(args.zone_id)
    elif action == "waf-create" and args.zone_id and args.expression:
        c.create_waf_rule(
            args.zone_id,
            args.description or "Linux-AI WAF rule",
            args.expression,
            args.waf_action or "block"
        )
    elif action == "waf-delete" and args.zone_id and args.rule_id:
        c.delete_waf_rule(args.zone_id, args.rule_id)
    elif action == "block-ip" and args.zone_id and args.ip:
        c.block_ip(args.zone_id, args.ip, args.description or "")
    elif action == "block-country" and args.zone_id and args.country:
        c.block_country(args.zone_id, args.country, args.description or "")
    elif action == "protect-admin" and args.zone_id:
        c.protect_admin_paths(args.zone_id)
    elif action == "challenge-threats" and args.zone_id:
        c.challenge_high_threat(args.zone_id, args.threshold or 50)


def cmd_supabase(args):
    s = SupabaseAgent()
    action = args.action or "projects"
    if action == "projects":
        s.list_projects()
    elif action == "health" and args.project:
        s.get_project_health(args.project)


def cmd_github(args):
    g = GitHubAgent()
    action = args.action or "repos"
    if action == "repos":
        g.list_repos(args.user or "")
    elif action == "prs" and args.repo:
        g.list_prs(args.repo)
    elif action == "issues" and args.repo:
        g.list_issues(args.repo)


def cmd_coolify(args):
    c = CoolifyAgent()
    action = args.action or "apps"
    if action == "servers":
        c.list_servers()
    elif action == "apps":
        c.list_applications()
    elif action == "databases":
        c.list_databases()
    elif action == "services":
        c.list_services()
    elif action == "deploy" and args.app_uuid:
        c.deploy_application(args.app_uuid)
    elif action == "deployments" and args.app_uuid:
        c.get_deployments(args.app_uuid)
    elif action == "restart" and args.app_uuid:
        c.restart_application(args.app_uuid)
    elif action == "stop" and args.app_uuid:
        c.stop_application(args.app_uuid)
    elif action == "version":
        c.get_version()


def cmd_fal(args):
    f = FalAgent()
    if args.model and args.prompt:
        result = f.run_model(args.model, {"prompt": args.prompt})
        if result:
            print(json.dumps(result, indent=2, ensure_ascii=False)[:2048])


def cmd_tailscale(args):
    t = TailscaleAgent()
    if not t.version:
        error("Tailscale bulunamadi. Kurun: https://tailscale.com/download/linux")
        return
    action = args.action or "status"
    if action == "status":
        t.status()
    elif action == "ip":
        t.get_ip(args.hostname or None)
    elif action == "ping" and args.hostname:
        t.ping_peer(args.hostname)
    elif action == "netcheck":
        t.netcheck()
    elif action == "serve" and args.port:
        t.serve_port(args.port)
    elif action == "serve-off":
        t.serve_off()
    elif action == "up":
        t.up(
            exit_node=args.exit_node,
            ssh=args.ssh,
            advertise_routes=args.routes
        )
    elif action == "down":
        t.down()


def build_parser():
    parser = argparse.ArgumentParser(
        prog="ai-web-agent",
        description="Linux-AI: Web API otomasyon araci"
    )
    sub = parser.add_subparsers(dest="command", help="Servis")

    # vercel
    p_v = sub.add_parser("vercel", help="Vercel islemleri")
    p_v.add_argument("action", nargs="?", default="projects",
                      choices=["projects", "deploys", "env"])
    p_v.add_argument("--project", help="Proje ID")
    p_v.set_defaults(func=cmd_vercel)

    # cloudflare
    p_cf = sub.add_parser("cloudflare", help="Cloudflare islemleri")
    p_cf.add_argument("action", nargs="?", default="zones",
                       choices=["zones", "analytics", "purge",
                                "waf-list", "waf-create", "waf-delete",
                                "block-ip", "block-country",
                                "protect-admin", "challenge-threats"])
    p_cf.add_argument("--zone-id", dest="zone_id", help="Zone ID")
    p_cf.add_argument("--days", type=int, default=7, help="Analitik gun sayisi")
    p_cf.add_argument("--expression", help="WAF filtre ifadesi")
    p_cf.add_argument("--description", help="Kural aciklamasi")
    p_cf.add_argument("--waf-action", dest="waf_action", default="block",
                       choices=["block", "challenge", "js_challenge",
                                "managed_challenge", "allow", "log"],
                       help="WAF kural aksiyonu")
    p_cf.add_argument("--rule-id", dest="rule_id", help="Kural ID (silme icin)")
    p_cf.add_argument("--ip", help="Engellenecek IP adresi")
    p_cf.add_argument("--country", help="Engellenecek ulke kodu (TR, US, ...)")
    p_cf.add_argument("--threshold", type=int, default=50,
                       help="Tehdit skoru esigi (varsayilan: 50)")
    p_cf.set_defaults(func=cmd_cloudflare)

    # supabase
    p_sb = sub.add_parser("supabase", help="Supabase islemleri")
    p_sb.add_argument("action", nargs="?", default="projects",
                       choices=["projects", "health"])
    p_sb.add_argument("--project", help="Proje ref")
    p_sb.set_defaults(func=cmd_supabase)

    # github
    p_gh = sub.add_parser("github", help="GitHub islemleri")
    p_gh.add_argument("action", nargs="?", default="repos",
                       choices=["repos", "prs", "issues"])
    p_gh.add_argument("--repo", help="Repo (user/repo)")
    p_gh.add_argument("--user", help="GitHub kullanici adi")
    p_gh.set_defaults(func=cmd_github)

    # coolify
    p_cool = sub.add_parser("coolify", help="Coolify self-hosting islemleri")
    p_cool.add_argument("action", nargs="?", default="apps",
                         choices=["servers", "apps", "databases", "services",
                                  "deploy", "deployments", "restart", "stop", "version"])
    p_cool.add_argument("--app-uuid", dest="app_uuid", help="Uygulama UUID")
    p_cool.set_defaults(func=cmd_coolify)

    # fal.ai
    p_fal = sub.add_parser("fal", help="Fal.ai model calistir")
    p_fal.add_argument("--model", help="Model ID (ornek: fal-ai/flux/dev)")
    p_fal.add_argument("--prompt", help="Input prompt")
    p_fal.set_defaults(func=cmd_fal)

    # tailscale
    p_ts = sub.add_parser("tailscale", help="Tailscale VPN islemleri")
    p_ts.add_argument("action", nargs="?", default="status",
                       choices=["status", "ip", "ping", "netcheck",
                                "serve", "serve-off", "up", "down"])
    p_ts.add_argument("--hostname", help="Peer hostname")
    p_ts.add_argument("--port", type=int, help="Paylasim icin yerel port")
    p_ts.add_argument("--exit-node", dest="exit_node", action="store_true",
                       help="Exit node olarak duyur")
    p_ts.add_argument("--ssh", action="store_true",
                       help="Tailscale SSH etkinlestir")
    p_ts.add_argument("--routes", help="Subnet route'lar (ornek: 192.168.1.0/24)")
    p_ts.set_defaults(func=cmd_tailscale)

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

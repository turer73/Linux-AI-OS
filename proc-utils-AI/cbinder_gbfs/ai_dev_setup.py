"""
ai_dev_setup.py - AI development environment setup and management

Installs and configures AI coding tools as part of Linux-AI:
  - Ollama (local LLM runtime, CPU-only mode)
  - Qwen2.5-Coder 3B model + linux-ai-coder custom profile
  - Continue.dev VS Code extension
  - Claude Code CLI

Optimized for: i7-M640 (2C/4T), 8 GB RAM, GT 330M (CPU-only)

Usage:
  ai-dev-setup install       # Tam kurulum
  ai-dev-setup status        # Durum kontrolu
  ai-dev-setup model-pull    # Model indir/guncelle
  ai-dev-setup configure     # CPU-only yapilandirma uygula
"""

import os
import sys
import shutil
import subprocess
import argparse
import tempfile
import platform
import time

import psutil

# --- Constants ---

TAG = "[ai-dev-setup]"

MIN_RAM_MB = 6000
MIN_DISK_GB = 5
OLLAMA_NUM_GPU = 0
OLLAMA_NUM_THREAD = 4
OLLAMA_MAX_LOADED_MODELS = 1

BASE_MODEL = "qwen2.5-coder:3b"
AGENT_MODEL = "qwen2.5:7b"  # Tool-calling destekli, agent icin
CUSTOM_MODEL_NAME = "linux-ai-coder"
AGENT_MODEL_NAME = "linux-ai-agent"
CONTINUE_EXTENSION_ID = "Continue.continue"
SYSTEMD_ENV_PATH = "/etc/systemd/system/ollama-env.conf"

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"

AGENT_MODELFILE_TEMPLATE = """FROM {base_model}

PARAMETER temperature 0.2
PARAMETER top_p 0.85
PARAMETER num_ctx 8192
PARAMETER num_predict 4096

SYSTEM \"\"\"You are the Linux-AI system agent. You control and monitor a Linux system
through tool calls. You respond in Turkish.

== Available Actions ==
You can call tools by responding with JSON:
{{"tool": "tool_name", "params": {{"key": "value"}}}}

Available tools:
- system_info: Get CPU, RAM, disk usage
- process_list: Top processes by CPU
- kernel_status: Kernel module state, governor, CPU metrics
- kernel_set_governor: Change CPU governor (requires user confirmation)
- read_file: Read config files from /var/AI-stump/ or /proc/ai_*
- site_health: Check website HTTP status and response time
- run_command: Run whitelisted system commands (requires confirmation)

== Rules ==
1. Always explain what you will do BEFORE calling a tool
2. Operations that modify the system REQUIRE user confirmation
3. Keep responses short and actionable
4. When analyzing metrics, provide specific recommendations
5. For web operations, check site health before other actions

== Context ==
Hardware: Intel i7-M640 (2C/4T), 8GB RAM, CPU-only inference
Web projects: renderhane.com, kokenakademi.com, 3d-labx.com
Stack: Next.js, Supabase, Vercel, Cloudflare
\"\"\"
"""

MODELFILE_TEMPLATE = """FROM {base_model}

PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER num_ctx 4096
PARAMETER num_predict 2048

SYSTEM \"\"\"You are a full-stack developer and Linux systems programmer.

== Linux-AI Project ==
- Linux kernel modules (C) for AI-driven system management
- Python AI daemons for CPU/GPU monitoring and optimization
- Compressed data pipelines (delta encoding, bit-packing, gzip)
- Web operations: Vercel deploy, Cloudflare DNS, Supabase DB

== Web Projects ==
- renderhane.com: 3D render platform (Next.js + Supabase + Vercel)
- kokenakademi.com: Education platform (Next.js + Supabase + Vercel)
- 3d-labx.com: 3D lab with games (Next.js + Supabase + Vercel)
- Tech stack: TypeScript, React, Next.js, Tailwind CSS, Supabase, Cloudflare
- Games: Kelime Fethi (word game), Tikla Fethet (clicker) - web + Google Play

== Hardware ==
Intel i7-M640 (2C/4T), 8GB RAM, NVIDIA GT 330M (CPU-only).
Optimize for minimal memory and CPU usage.

== Code Conventions ==
- C: Linux kernel style, 4-space indent, snake_case
- Python: PEP 8, type hints, no unnecessary dependencies
- TypeScript/React: functional components, hooks, Tailwind CSS
- Comments in English, user-facing messages in Turkish
- Security: no system(), no eval(), no shell injection, no dangerouslySetInnerHTML
\"\"\"
"""


# --- Utility ---

def info(msg):
    print(f"{GREEN}{TAG}{NC} {msg}")


def warn(msg):
    print(f"{YELLOW}{TAG}{NC} {msg}")


def error(msg):
    print(f"{RED}{TAG}{NC} {msg}")


def command_exists(cmd):
    """Check if a command is available on PATH."""
    return shutil.which(cmd) is not None


def run_cmd(args, timeout=300, capture=True, check=False):
    """Run an external command safely (no shell=True)."""
    return subprocess.run(
        args, capture_output=capture, text=True,
        timeout=timeout, check=check
    )


# --- System Checks ---

def get_total_ram_mb():
    return psutil.virtual_memory().total // (1024 * 1024)


def get_free_disk_gb(path="/"):
    return psutil.disk_usage(path).free // (1024 * 1024 * 1024)


def get_cpu_info():
    return {
        "physical_cores": psutil.cpu_count(logical=False) or 1,
        "logical_threads": psutil.cpu_count(logical=True) or 1,
    }


def detect_gpu():
    """Detect GPU via lspci (Linux only)."""
    if platform.system() != "Linux":
        return ""
    try:
        result = run_cmd(["lspci"], timeout=10)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                low = line.lower()
                if "vga" in low or "3d" in low or "display" in low:
                    return line.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


def check_system():
    """Verify system meets minimum requirements. Returns True if OK."""
    info("Sistem kontrol ediliyor...")
    ok = True

    ram_mb = get_total_ram_mb()
    if ram_mb < MIN_RAM_MB:
        error(f"Yetersiz RAM: {ram_mb} MB (minimum {MIN_RAM_MB // 1000} GB gerekli)")
        ok = False
    else:
        info(f"RAM: {ram_mb} MB (yeterli)")

    disk_gb = get_free_disk_gb("/")
    if disk_gb < MIN_DISK_GB:
        error(f"Yetersiz disk: {disk_gb} GB (minimum {MIN_DISK_GB} GB gerekli)")
        ok = False
    else:
        info(f"Disk: {disk_gb} GB bos")

    cpu = get_cpu_info()
    info(f"CPU: {cpu['physical_cores']} cekirdek / {cpu['logical_threads']} thread")

    gpu_desc = detect_gpu()
    if gpu_desc:
        low = gpu_desc.lower()
        if "gt 330m" in low or "fermi" in low:
            warn("GT 330M tespit edildi - CUDA destegi yok, CPU-only mod kullanilacak")
        else:
            info(f"GPU: {gpu_desc}")

    return ok


# --- Ollama ---

def is_ollama_installed():
    return command_exists("ollama")


def get_ollama_version():
    if not is_ollama_installed():
        return ""
    try:
        result = run_cmd(["ollama", "--version"], timeout=10)
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "unknown"


def install_ollama():
    """Install Ollama via official installer. Returns True on success."""
    if is_ollama_installed():
        info(f"Ollama zaten kurulu: {get_ollama_version()}")
        return True

    if platform.system() != "Linux":
        error("Ollama otomatik kurulum sadece Linux'ta desteklenir.")
        warn("Manuel kurun: https://ollama.com/download")
        return False

    info("Ollama kuruluyor...")
    try:
        installer = os.path.join(tempfile.gettempdir(), "ollama_install.sh")
        dl = run_cmd(
            ["curl", "-fsSL", "-o", installer, "https://ollama.com/install.sh"],
            timeout=120
        )
        if dl.returncode != 0:
            error("Ollama installer indirilemedi.")
            return False

        run_cmd(["sh", installer], timeout=300, capture=False)

        try:
            os.remove(installer)
        except OSError:
            pass

        if not is_ollama_installed():
            error("Ollama kurulumu basarisiz!")
            return False

        info("Ollama kuruldu.")
        return True

    except subprocess.TimeoutExpired:
        error("Ollama kurulumu zaman asimina ugradi.")
        return False
    except FileNotFoundError:
        error("curl bulunamadi. Kurun: sudo apt install curl")
        return False


def is_ollama_running():
    for proc in psutil.process_iter(attrs=["name"]):
        try:
            if proc.info["name"] == "ollama":
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def start_ollama_service():
    """Start Ollama service. Returns True if running."""
    if is_ollama_running():
        info("Ollama servisi zaten calisiyor.")
        return True

    info("Ollama servisi baslatiliyor...")

    # Try systemctl first
    if command_exists("systemctl"):
        try:
            run_cmd(["systemctl", "start", "ollama"], timeout=15)
            time.sleep(3)
            if is_ollama_running():
                info("Ollama servisi baslatildi (systemd).")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # Fallback: direct start
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(3)
        if is_ollama_running():
            info("Ollama servisi baslatildi.")
            return True
    except FileNotFoundError:
        pass

    warn("Ollama baslatilamadi. Manuel deneyin: ollama serve")
    return False


# --- Model Management ---

def list_ollama_models():
    """Get list of installed Ollama model names."""
    if not is_ollama_installed():
        return []
    try:
        result = run_cmd(["ollama", "list"], timeout=15)
        if result.returncode != 0:
            return []
        models = []
        for line in result.stdout.splitlines()[1:]:
            parts = line.split()
            if parts:
                models.append(parts[0])
        return models
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []


def has_model(model_name):
    return any(model_name in m for m in list_ollama_models())


def pull_model(model_name=BASE_MODEL):
    """Pull/download an Ollama model. Returns True on success."""
    info(f"{model_name} indiriliyor (~1.8 GB)...")
    info("Bu islem internet hiziniza bagli olarak 5-30 dakika surebilir.")

    try:
        result = run_cmd(
            ["ollama", "pull", model_name],
            timeout=1800,
            capture=False
        )
        if result.returncode == 0:
            info("Model indirildi.")
            return True
        error(f"Model indirme basarisiz: {model_name}")
        return False
    except subprocess.TimeoutExpired:
        error("Model indirme zaman asimina ugradi (30 dk).")
        return False


def create_custom_modelfile():
    """Create linux-ai-coder custom profile. Returns True on success."""
    info("Linux-AI ozel profil olusturuluyor...")

    content = MODELFILE_TEMPLATE.format(base_model=BASE_MODEL)
    modelfile_path = os.path.join(tempfile.gettempdir(), "linux-ai-coder.Modelfile")

    try:
        with open(modelfile_path, "w") as f:
            f.write(content)

        result = run_cmd(
            ["ollama", "create", CUSTOM_MODEL_NAME, "-f", modelfile_path],
            timeout=120, capture=False
        )

        try:
            os.remove(modelfile_path)
        except OSError:
            pass

        if result.returncode == 0:
            info(f"Profil olusturuldu: {CUSTOM_MODEL_NAME}")
            return True
        error("Ozel profil olusturulamadi.")
        return False

    except Exception as e:
        error(f"Modelfile hatasi: {e}")
        return False


def create_agent_modelfile():
    """Create linux-ai-agent profile for tool-calling. Returns True on success."""
    info("Linux-AI agent profili olusturuluyor...")

    content = AGENT_MODELFILE_TEMPLATE.format(base_model=AGENT_MODEL)
    modelfile_path = os.path.join(tempfile.gettempdir(), "linux-ai-agent.Modelfile")

    try:
        with open(modelfile_path, "w") as f:
            f.write(content)

        result = run_cmd(
            ["ollama", "create", AGENT_MODEL_NAME, "-f", modelfile_path],
            timeout=120, capture=False
        )

        try:
            os.remove(modelfile_path)
        except OSError:
            pass

        if result.returncode == 0:
            info(f"Agent profili olusturuldu: {AGENT_MODEL_NAME}")
            return True
        error("Agent profili olusturulamadi.")
        return False

    except Exception as e:
        error(f"Agent Modelfile hatasi: {e}")
        return False


# --- Configuration ---

def configure_ollama_env():
    """Apply CPU-only Ollama environment. Returns True."""
    env_vars = {
        "OLLAMA_NUM_GPU": str(OLLAMA_NUM_GPU),
        "OLLAMA_NUM_THREAD": str(OLLAMA_NUM_THREAD),
        "OLLAMA_MAX_LOADED_MODELS": str(OLLAMA_MAX_LOADED_MODELS),
    }

    # Current process
    for key, val in env_vars.items():
        os.environ[key] = val
    info("Ortam degiskenleri ayarlandi (mevcut oturum).")

    # Systemd override
    if os.path.isdir("/etc/systemd/system"):
        systemd_content = "[Service]\n"
        for key, val in env_vars.items():
            systemd_content += f'Environment="{key}={val}"\n'
        try:
            proc = subprocess.run(
                ["sudo", "tee", SYSTEMD_ENV_PATH],
                input=systemd_content, capture_output=True,
                text=True, timeout=15
            )
            if proc.returncode == 0:
                info("Ollama systemd ortam degiskenleri ayarlandi.")
            else:
                warn("Systemd konfigurasyon yazilamadi (sudo gerekebilir).")
        except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
            warn("Systemd konfigurasyonu atlaniyor.")

    # ~/.bashrc
    bashrc_path = os.path.expanduser("~/.bashrc")
    bashrc_block = (
        "\n# Ollama - Linux-AI dev (CPU-only, i7-M640 optimized)\n"
        "export OLLAMA_NUM_GPU=0\n"
        "export OLLAMA_NUM_THREAD=4\n"
        "export OLLAMA_MAX_LOADED_MODELS=1\n"
    )
    try:
        already = False
        if os.path.exists(bashrc_path):
            with open(bashrc_path, "r") as f:
                if "OLLAMA_NUM_GPU" in f.read():
                    already = True
        if not already:
            with open(bashrc_path, "a") as f:
                f.write(bashrc_block)
            info("Ollama ortam degiskenleri ~/.bashrc'ye eklendi.")
        else:
            info("~/.bashrc'de Ollama ayarlari zaten mevcut.")
    except (IOError, PermissionError) as e:
        warn(f"~/.bashrc yazilamadi: {e}")

    return True


# --- VS Code / Continue.dev ---

def is_vscode_installed():
    return command_exists("code")


def is_continue_installed():
    if not is_vscode_installed():
        return False
    try:
        result = run_cmd(["code", "--list-extensions"], timeout=30)
        if result.returncode == 0:
            return any("continue" in ext.lower() for ext in result.stdout.splitlines())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return False


def setup_continue_dev():
    """Install Continue.dev extension. Returns True on success."""
    if not is_vscode_installed():
        warn("VS Code bulunamadi. Continue.dev'i manuel kurun:")
        warn("  VS Code -> Extensions -> 'Continue' ara -> Install")
        return False

    if is_continue_installed():
        info("Continue.dev zaten kurulu.")
        return True

    info("VS Code Continue eklentisi kuruluyor...")
    try:
        result = run_cmd(
            ["code", "--install-extension", CONTINUE_EXTENSION_ID],
            timeout=120
        )
        if result.returncode == 0:
            info("Continue eklentisi kuruldu.")
            return True
        warn("Continue eklentisi kurulamadi. Manuel kurun.")
        return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        warn("Continue kurulumu basarisiz.")
        return False


# --- Claude Code ---

def is_claude_code_installed():
    return command_exists("claude")


def setup_claude_code():
    """Install Claude Code via npm. Returns True on success."""
    if is_claude_code_installed():
        info("Claude Code zaten kurulu.")
        return True

    if not command_exists("npm"):
        warn("npm bulunamadi. Claude Code icin:")
        warn("  1. Node.js kurun: https://nodejs.org/")
        warn("  2. npm install -g @anthropic-ai/claude-code")
        return False

    info("Claude Code kuruluyor...")
    try:
        result = run_cmd(
            ["npm", "install", "-g", "@anthropic-ai/claude-code"],
            timeout=180, capture=False
        )
        if result.returncode == 0 or is_claude_code_installed():
            info("Claude Code kuruldu.")
            return True
        warn("Claude Code npm ile kurulamadi. Manuel kurun:")
        warn("  npm install -g @anthropic-ai/claude-code")
        return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        warn("Claude Code kurulumu basarisiz.")
        return False


# --- Status Report ---

def print_status():
    """Print comprehensive status of all AI dev components."""
    cpu = get_cpu_info()
    ram_mb = get_total_ram_mb()

    print("")
    print("=== AI Gelistirme Ortami Durumu ===")
    print(f"  Sistem: {cpu['physical_cores']}C/{cpu['logical_threads']}T, {ram_mb} MB RAM")
    print("")

    # Ollama
    if is_ollama_installed():
        running = "Calisiyor" if is_ollama_running() else "Durdurulmus"
        print(f"  Ollama:          {GREEN}Kurulu{NC} ({get_ollama_version()}) [{running}]")

        if has_model(CUSTOM_MODEL_NAME):
            print(f"  linux-ai-coder:  {GREEN}Mevcut{NC}")
        elif has_model(BASE_MODEL):
            print(f"  qwen2.5-coder:   {GREEN}Mevcut{NC} (ozel profil yok)")
        else:
            print(f"  Coder model:     {YELLOW}Indirilmedi{NC}")

        if has_model(AGENT_MODEL_NAME):
            print(f"  linux-ai-agent:  {GREEN}Mevcut{NC} (7B tool-calling)")
        elif has_model(AGENT_MODEL):
            print(f"  qwen2.5:7b:      {GREEN}Mevcut{NC} (agent profil yok)")
        else:
            print(f"  Agent model:     {YELLOW}Indirilmedi{NC} (ai-dev-setup model-pull --agent)")

        models = list_ollama_models()
        if models:
            print(f"  Tum modeller:    {', '.join(models)}")
    else:
        print(f"  Ollama:          {RED}Kurulu Degil{NC}")

    print(f"  OLLAMA_NUM_GPU:  {os.environ.get('OLLAMA_NUM_GPU', 'ayarlanmamis')}")
    print(f"  OLLAMA_NUM_THREAD: {os.environ.get('OLLAMA_NUM_THREAD', 'ayarlanmamis')}")
    print("")

    # Claude Code
    if is_claude_code_installed():
        print(f"  Claude Code:     {GREEN}Kurulu{NC}")
    else:
        print(f"  Claude Code:     {YELLOW}Kurulu Degil{NC}")

    # VS Code + Continue
    if is_vscode_installed():
        print(f"  VS Code:         {GREEN}Kurulu{NC}")
        if is_continue_installed():
            print(f"  Continue.dev:    {GREEN}Kurulu{NC}")
        else:
            print(f"  Continue.dev:    {YELLOW}Kurulu Degil{NC}")
    else:
        print(f"  VS Code:         {YELLOW}Kurulu Degil{NC}")

    print("")
    info("Kullanim:")
    print("  ollama run linux-ai-coder    # Yerel AI ile sohbet")
    print("  claude                        # Claude Code baslat")
    print("  Continue.dev                  # VS Code icinde AI (Ctrl+L)")
    print("")


# --- Subcommand Handlers ---

def cmd_install(_args):
    """Full installation of all AI dev tools."""
    print("")
    print("=========================================")
    print("  Linux-AI: AI Dev Ortami Kurulumu")
    print("  Hedef: i7-M640, 8GB RAM (CPU-only)")
    print("=========================================")
    print("")

    if not check_system():
        error("Sistem gereksinimleri karsilanmiyor.")
        sys.exit(1)

    if not install_ollama():
        error("Ollama kurulamadi.")
        sys.exit(1)

    start_ollama_service()
    configure_ollama_env()

    if not pull_model(BASE_MODEL):
        error("Temel model indirilemedi.")
        sys.exit(1)

    create_custom_modelfile()

    # Agent model (7B - tool-calling destekli)
    info("Agent modeli indiriliyor (7B, tool-calling destekli)...")
    ram_mb = get_total_ram_mb()
    if ram_mb >= 7500:
        if pull_model(AGENT_MODEL):
            create_agent_modelfile()
        else:
            warn("Agent modeli indirilemedi. Coder modeli agent olarak kullanilacak.")
    else:
        warn(f"RAM ({ram_mb} MB) 7B model icin dusuk. 3B coder modeli agent olarak kullanilacak.")
        warn("Daha sonra 'ai-dev-setup model-pull --agent' ile deneyebilirsiniz.")

    setup_continue_dev()
    setup_claude_code()
    print_status()
    info("Kurulum tamamlandi!")


def cmd_status(_args):
    """Show installation status."""
    print_status()


def cmd_model_pull(args):
    """Pull or update the AI model."""
    if not is_ollama_installed():
        error("Ollama kurulu degil. Once kurun: ai-dev-setup install")
        sys.exit(1)

    if not is_ollama_running():
        start_ollama_service()

    if getattr(args, "agent", False):
        # Pull agent model (7B tool-calling)
        if not pull_model(AGENT_MODEL):
            sys.exit(1)
        create_agent_modelfile()
        info("Agent modeli guncellendi.")
    else:
        model = getattr(args, "model", None) or BASE_MODEL
        if not pull_model(model):
            sys.exit(1)
        if model == BASE_MODEL:
            create_custom_modelfile()
        info("Model guncellendi.")


def cmd_configure(_args):
    """Apply CPU-only Ollama configuration."""
    if not is_ollama_installed():
        error("Ollama kurulu degil. Once kurun: ai-dev-setup install")
        sys.exit(1)

    configure_ollama_env()
    info("Yapilandirma tamamlandi. Ollama'yi yeniden baslatin:")
    print("  systemctl restart ollama")


# --- CLI ---

def build_parser():
    parser = argparse.ArgumentParser(
        prog="ai-dev-setup",
        description="Linux-AI: AI gelistirme ortami kurulum ve yonetim araci"
    )
    sub = parser.add_subparsers(dest="command", help="Alt komutlar")

    p_install = sub.add_parser("install", help="Tum AI araclarini kur")
    p_install.set_defaults(func=cmd_install)

    p_status = sub.add_parser("status", help="Kurulum durumunu goster")
    p_status.set_defaults(func=cmd_status)

    p_pull = sub.add_parser("model-pull", help="Model indir veya guncelle")
    p_pull.add_argument(
        "--model", default=BASE_MODEL,
        help=f"Indirilecek model (varsayilan: {BASE_MODEL})"
    )
    p_pull.add_argument(
        "--agent", action="store_true",
        help=f"Agent modelini indir ({AGENT_MODEL}, 7B tool-calling)"
    )
    p_pull.set_defaults(func=cmd_model_pull)

    p_conf = sub.add_parser("configure", help="CPU-only yapilandirma uygula")
    p_conf.set_defaults(func=cmd_configure)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if platform.system() != "Linux":
        warn("Bu arac Linux icin tasarlanmistir. Bazi ozellikler calismayabilir.")

    args.func(args)


if __name__ == "__main__":
    main()

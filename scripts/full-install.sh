#!/bin/bash
# =============================================================================
# Linux-AI Full Installation Script
# =============================================================================
#
# Installs the complete Linux-AI system on Ubuntu/Debian.
# Run as root or with sudo.
#
# Usage:
#   sudo bash full-install.sh              # Full installation
#   sudo bash full-install.sh --no-models  # Skip AI model download
#   sudo bash full-install.sh --dev-only   # Dev tools only (no services)
#
# Tested on: Ubuntu 22.04/24.04, Debian 12, WSL2
# Target: i7-M640 (2C/4T), 8 GB RAM, GT 330M (no CUDA)
# =============================================================================

set -euo pipefail

# --- Colors ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

TAG="[linux-ai-install]"

# --- Flags ---
SKIP_MODELS=false
DEV_ONLY=false
INSTALL_DIR="/opt/linux-ai"
CONFIG_DIR="/var/AI-stump"

for arg in "$@"; do
    case $arg in
        --no-models)  SKIP_MODELS=true ;;
        --dev-only)   DEV_ONLY=true ;;
        --help|-h)
            echo "Usage: sudo bash full-install.sh [--no-models] [--dev-only]"
            exit 0 ;;
    esac
done

# --- Helpers ---
info()  { echo -e "${GREEN}${TAG}${NC} $1"; }
warn()  { echo -e "${YELLOW}${TAG}${NC} $1"; }
error() { echo -e "${RED}${TAG}${NC} $1"; }
step()  { echo -e "\n${BOLD}${CYAN}>>> $1${NC}\n"; }

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        error "Bu script root olarak calistirilmali: sudo bash full-install.sh"
        exit 1
    fi
}

# --- System Check ---
check_system() {
    step "1/9 - Sistem Kontrolu"

    # OS
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        info "OS: $PRETTY_NAME"
    fi

    # WSL check
    if grep -qi microsoft /proc/version 2>/dev/null; then
        IS_WSL=true
        info "Ortam: WSL2"
    else
        IS_WSL=false
        info "Ortam: Native Linux"
    fi

    # CPU
    CPU_MODEL=$(grep -m1 "model name" /proc/cpuinfo | cut -d: -f2 | xargs)
    CPU_CORES=$(nproc)
    info "CPU: $CPU_MODEL ($CPU_CORES thread)"

    # RAM
    RAM_MB=$(free -m | awk '/Mem:/ {print $2}')
    info "RAM: ${RAM_MB} MB"
    if [ "$RAM_MB" -lt 4096 ]; then
        error "Minimum 4 GB RAM gerekli. Mevcut: ${RAM_MB} MB"
        exit 1
    fi

    # Disk
    DISK_FREE_GB=$(df -BG / | awk 'NR==2 {print $4}' | tr -d 'G')
    info "Disk (bos): ${DISK_FREE_GB} GB"
    if [ "$DISK_FREE_GB" -lt 5 ]; then
        error "Minimum 5 GB bos disk gerekli. Mevcut: ${DISK_FREE_GB} GB"
        exit 1
    fi

    info "Sistem kontrolu: OK"
}

# --- Install System Packages ---
install_system_packages() {
    step "2/9 - Sistem Paketleri"

    apt-get update -qq

    PACKAGES=(
        # Build tools
        build-essential gcc g++ make cmake
        # Python
        python3 python3-pip python3-venv python3-dev
        # System tools
        curl wget git openssl
        # Libraries
        libssl-dev libffi-dev
        # Monitoring
        lm-sensors htop
        # Process management
        cron
    )

    info "Paketler kuruluyor: ${#PACKAGES[@]} adet..."
    apt-get install -y -qq "${PACKAGES[@]}" 2>/dev/null

    # Ensure pip is up to date
    python3 -m pip install --upgrade pip --quiet 2>/dev/null || true

    info "Sistem paketleri: OK"
}

# --- Clone & Install Linux-AI ---
install_linux_ai() {
    step "3/9 - Linux-AI Kurulumu"

    # Clone if not already present
    if [ -d "$INSTALL_DIR/.git" ]; then
        info "Repo zaten mevcut: $INSTALL_DIR"
        cd "$INSTALL_DIR"
        git pull --ff-only 2>/dev/null || true
    else
        info "Repo klonlaniyor..."
        git clone https://github.com/turer73/Linux-AI.git "$INSTALL_DIR" 2>/dev/null || {
            # If repo doesn't exist yet, copy from current location
            if [ -d "$(dirname "$0")/../proc-utils-AI" ]; then
                info "Yerel dosyalardan kopyalaniyor..."
                mkdir -p "$INSTALL_DIR"
                cp -r "$(dirname "$0")/.." "$INSTALL_DIR/"
            else
                error "Repo klonlanamadi ve yerel dosya bulunamadi."
                exit 1
            fi
        }
        cd "$INSTALL_DIR"
    fi

    # Install Python package
    info "Python paketi kuruluyor..."
    cd "$INSTALL_DIR"
    pip3 install -e "." --quiet 2>/dev/null
    pip3 install PyYAML psutil --quiet 2>/dev/null

    # Verify entry points
    info "Komutlar kontrol ediliyor..."
    for cmd in ai-monitor ai-backup ai-logs ai-agent ai-web-agent ai-dev-setup ai-webops; do
        if command -v "$cmd" &>/dev/null; then
            echo -e "  ${GREEN}✓${NC} $cmd"
        else
            echo -e "  ${RED}✗${NC} $cmd"
        fi
    done

    info "Linux-AI Python paketi: OK"
}

# --- Build C/C++ Components ---
build_native() {
    step "4/9 - C/C++ Derleme"

    cd "$INSTALL_DIR"

    # Build with Make
    if [ -f Makefile ]; then
        info "Make ile derleniyor..."
        make all 2>/dev/null || warn "Make build: bazi hedefler atlandi (normal)"
    fi

    # Build with CMake
    if [ -f CMakeLists.txt ]; then
        info "CMake ile derleniyor..."
        mkdir -p build && cd build
        cmake .. -DCMAKE_BUILD_TYPE=Release 2>/dev/null && make -j"$CPU_CORES" 2>/dev/null || warn "CMake build: bazi hedefler atlandi"
        cd "$INSTALL_DIR"
    fi

    # Kernel module (skip on WSL - no kernel headers)
    if [ "$IS_WSL" = true ]; then
        warn "WSL ortami: Kernel modulu atlanıyor (WSL kernel desteklemiyor)"
    else
        if [ -d proc-utils-AI/nproc-kernel/kmod ]; then
            info "Kernel modulu derleniyor..."
            cd proc-utils-AI/nproc-kernel/kmod
            make 2>/dev/null && info "Kernel modulu: OK" || warn "Kernel modulu: atlanıyor (kernel headers eksik olabilir)"
            cd "$INSTALL_DIR"
        fi
    fi

    info "Native build: OK"
}

# --- Setup Configuration ---
setup_config() {
    step "5/9 - Yapilandirma Dosyalari"

    mkdir -p "$CONFIG_DIR"
    mkdir -p "$CONFIG_DIR/backups"

    # Copy default configs
    if [ -d "$INSTALL_DIR/scripts/defaults" ]; then
        for yml in "$INSTALL_DIR"/scripts/defaults/*.yml; do
            fname=$(basename "$yml")
            if [ ! -f "$CONFIG_DIR/$fname" ]; then
                cp "$yml" "$CONFIG_DIR/$fname"
                info "  + $CONFIG_DIR/$fname"
            else
                info "  = $CONFIG_DIR/$fname (mevcut, atlanıyor)"
            fi
        done
    fi

    # Create .env if not exists
    if [ ! -f "$INSTALL_DIR/.env" ] && [ -f "$INSTALL_DIR/.env.example" ]; then
        cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
        info "  + .env olusturuldu (tokenlari doldur!)"
    fi

    # Set permissions
    chmod 750 "$CONFIG_DIR"
    chmod 640 "$CONFIG_DIR"/*.yml 2>/dev/null || true

    info "Yapilandirma: OK"
}

# --- Install Ollama ---
install_ollama() {
    step "6/9 - Ollama (Yerel AI)"

    if command -v ollama &>/dev/null; then
        OLLAMA_VER=$(ollama --version 2>/dev/null || echo "?")
        info "Ollama zaten kurulu: $OLLAMA_VER"
    else
        info "Ollama kuruluyor..."
        curl -fsSL https://ollama.ai/install.sh -o /tmp/ollama-install.sh
        sh /tmp/ollama-install.sh 2>/dev/null
        rm -f /tmp/ollama-install.sh
    fi

    # Start Ollama service
    if [ "$IS_WSL" = true ]; then
        # WSL: start as background process
        info "WSL: Ollama arka planda baslatiliyor..."
        nohup ollama serve > /tmp/ollama.log 2>&1 &
        sleep 3
    else
        # Native: use systemd
        systemctl enable ollama 2>/dev/null || true
        systemctl start ollama 2>/dev/null || true
    fi

    # Set CPU-only environment
    export OLLAMA_NUM_GPU=0
    export OLLAMA_NUM_THREAD="$CPU_CORES"
    export OLLAMA_MAX_LOADED_MODELS=1

    # Pull models (unless skipped)
    if [ "$SKIP_MODELS" = false ]; then
        info "AI modeller indiriliyor (bu biraz sure alabilir)..."

        # Coder model (3B, ~1.8GB)
        info "  qwen2.5-coder:3b indiriliyor..."
        ollama pull qwen2.5-coder:3b 2>/dev/null || warn "  Model indirilemedi (internet?)"

        # Agent model (7B, ~4.4GB) - only if enough RAM
        if [ "$RAM_MB" -ge 7500 ]; then
            info "  qwen2.5:7b indiriliyor (7B agent model)..."
            ollama pull qwen2.5:7b 2>/dev/null || warn "  7B model indirilemedi"
        else
            warn "  7B model icin yeterli RAM yok (${RAM_MB}MB < 7500MB). Sadece 3B kullanilacak."
        fi

        # Create custom profiles
        info "Ozel model profilleri olusturuluyor..."
        ai-dev-setup model-pull 2>/dev/null || warn "Model profili olusturulamadi"
    else
        warn "Model indirme atlandi (--no-models)"
    fi

    info "Ollama: OK"
}

# --- Install Tailscale ---
install_tailscale() {
    step "7/9 - Tailscale VPN"

    if command -v tailscale &>/dev/null; then
        TS_VER=$(tailscale version 2>/dev/null | head -1)
        info "Tailscale zaten kurulu: $TS_VER"
    else
        info "Tailscale kuruluyor..."
        curl -fsSL https://tailscale.com/install.sh | sh 2>/dev/null
    fi

    # Start service
    if [ "$IS_WSL" = true ]; then
        warn "WSL: Tailscale daemon'u elle baslatmaniz gerekebilir: sudo tailscaled &"
    else
        systemctl enable tailscaled 2>/dev/null || true
        systemctl start tailscaled 2>/dev/null || true
    fi

    info "Tailscale: OK (baglanmak icin: sudo tailscale up)"
}

# --- Setup Systemd Services ---
setup_services() {
    step "8/9 - Sistem Servisleri"

    if [ "$IS_WSL" = true ]; then
        warn "WSL: systemd sinirli destek. Servisleri elle baslatabilirsiniz."
        info "  ai-monitor run &      # Monitor daemon"
        info "  ai-backup cron --enable  # Gunluk yedekleme"
        return
    fi

    if [ "$DEV_ONLY" = true ]; then
        warn "Dev-only mod: servisler atlanıyor."
        return
    fi

    # ai-monitor service
    cat > /etc/systemd/system/ai-monitor.service << 'SVCEOF'
[Unit]
Description=Linux-AI System Monitor
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
ExecStart=/usr/local/bin/ai-monitor run --interval 300
Restart=on-failure
RestartSec=30
User=root
Environment=OLLAMA_NUM_GPU=0

[Install]
WantedBy=multi-user.target
SVCEOF

    # ai-cpufregd service
    cat > /etc/systemd/system/ai-cpufregd.service << 'SVCEOF'
[Unit]
Description=Linux-AI CPU Frequency Daemon
After=local-fs.target

[Service]
Type=simple
ExecStart=/usr/local/bin/ai-cpufregd
Restart=on-failure
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
SVCEOF

    # Reload and enable
    systemctl daemon-reload
    systemctl enable ai-monitor.service 2>/dev/null || true
    systemctl start ai-monitor.service 2>/dev/null || true
    info "  ai-monitor.service: etkinlestirildi"

    # Don't auto-start cpufregd - user should decide
    info "  ai-cpufregd.service: hazirlandi (elle baslatin: systemctl start ai-cpufregd)"

    # Setup daily backup cron
    ai-backup cron --enable 2>/dev/null || warn "Backup cron ayarlanamadi"

    info "Servisler: OK"
}

# --- Final Report ---
final_report() {
    step "9/9 - Kurulum Raporu"

    echo -e "${BOLD}==========================================${NC}"
    echo -e "${BOLD}  Linux-AI Kurulum Tamamlandi!${NC}"
    echo -e "${BOLD}==========================================${NC}"

    echo -e "\n${CYAN}[Kurulum Bilgileri]${NC}"
    echo -e "  Dizin:    $INSTALL_DIR"
    echo -e "  Config:   $CONFIG_DIR"
    echo -e "  Ortam:    $([ "$IS_WSL" = true ] && echo 'WSL2' || echo 'Native Linux')"

    echo -e "\n${CYAN}[Kullanilabilir Komutlar]${NC}"
    for cmd in ai-monitor ai-backup ai-logs ai-agent ai-web-agent ai-dev-setup ai-webops ai-cpufregd; do
        if command -v "$cmd" &>/dev/null; then
            echo -e "  ${GREEN}✓${NC} $cmd"
        else
            echo -e "  ${RED}✗${NC} $cmd"
        fi
    done

    echo -e "\n${CYAN}[Servisler]${NC}"
    if [ "$IS_WSL" = false ] && [ "$DEV_ONLY" = false ]; then
        for svc in ai-monitor ollama tailscaled; do
            if systemctl is-active "$svc" &>/dev/null; then
                echo -e "  ${GREEN}✓${NC} $svc (aktif)"
            else
                echo -e "  ${YELLOW}○${NC} $svc (pasif)"
            fi
        done
    else
        echo -e "  ${DIM}(WSL/dev mod - systemd sinirli)${NC}"
    fi

    echo -e "\n${CYAN}[Ollama Modeller]${NC}"
    ollama list 2>/dev/null || echo -e "  ${DIM}(ollama calismıyor)${NC}"

    echo -e "\n${CYAN}[Sonraki Adimlar]${NC}"
    echo -e "  1. .env dosyasini duzenle: ${BOLD}nano $INSTALL_DIR/.env${NC}"
    echo -e "  2. Tailscale baglan:       ${BOLD}sudo tailscale up${NC}"
    echo -e "  3. Dashboard goster:       ${BOLD}ai-monitor dashboard${NC}"
    echo -e "  4. Agent baslat:           ${BOLD}ai-agent${NC}"
    echo -e "  5. Web ops:                ${BOLD}ai-web-agent --help${NC}"

    if [ "$IS_WSL" = true ]; then
        echo -e "\n${YELLOW}[WSL Notlari]${NC}"
        echo -e "  - Kernel modulu WSL'de calismaz (native Linux gerektirir)"
        echo -e "  - Ollama: her WSL acilisinda 'ollama serve &' calistirin"
        echo -e "  - Tailscale: 'sudo tailscaled &' sonra 'sudo tailscale up'"
    fi

    echo -e "\n==========================================="
    echo ""
}

# --- Main ---
main() {
    echo ""
    echo -e "${BOLD}============================================${NC}"
    echo -e "${BOLD}  Linux-AI Full Installation Script v0.3.0${NC}"
    echo -e "${BOLD}============================================${NC}"
    echo ""

    check_root
    check_system
    install_system_packages
    install_linux_ai
    build_native
    setup_config

    if [ "$DEV_ONLY" = false ]; then
        install_ollama
        install_tailscale
        setup_services
    else
        warn "Dev-only mod: Ollama, Tailscale ve servisler atlanıyor."
    fi

    final_report
}

main "$@"

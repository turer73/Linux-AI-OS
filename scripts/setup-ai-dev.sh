#!/bin/bash
# =============================================================================
# setup-ai-dev.sh - AI Destekli Gelistirme Ortami Kurulumu
#
# Hedef donanim: i7-M640 (2C/4T), 8 GB RAM, GT 330M (kullanilmaz)
# Kurulumlar: Ollama + Qwen2.5-Coder 3B + Continue.dev + Claude Code
#
# Kullanim:
#   chmod +x scripts/setup-ai-dev.sh
#   ./scripts/setup-ai-dev.sh
# =============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[AI-DEV]${NC} $1"; }
warn()  { echo -e "${YELLOW}[AI-DEV]${NC} $1"; }
error() { echo -e "${RED}[AI-DEV]${NC} $1"; }

# ==== Sistem Kontrolu ====
check_system() {
    info "Sistem kontrol ediliyor..."

    # RAM kontrolu
    total_ram_mb=$(free -m | awk '/^Mem:/{print $2}')
    if [ "$total_ram_mb" -lt 6000 ]; then
        error "Yetersiz RAM: ${total_ram_mb} MB (minimum 6 GB gerekli)"
        exit 1
    fi
    info "RAM: ${total_ram_mb} MB (yeterli)"

    # Disk alani
    free_disk_gb=$(df -BG / | awk 'NR==2{print $4}' | tr -d 'G')
    if [ "$free_disk_gb" -lt 5 ]; then
        error "Yetersiz disk: ${free_disk_gb} GB (minimum 5 GB gerekli)"
        exit 1
    fi
    info "Disk: ${free_disk_gb} GB bos"

    # GPU uyarisi
    if lspci 2>/dev/null | grep -qi "GT 330M\|Fermi"; then
        warn "GT 330M tespit edildi - CUDA destegi yok, CPU-only mod kullanilacak"
    fi
}

# ==== Ollama Kurulumu ====
install_ollama() {
    if command -v ollama &>/dev/null; then
        info "Ollama zaten kurulu: $(ollama --version 2>/dev/null || echo 'version unknown')"
        return 0
    fi

    info "Ollama kuruluyor..."
    curl -fsSL https://ollama.com/install.sh | sh

    if ! command -v ollama &>/dev/null; then
        error "Ollama kurulumu basarisiz!"
        exit 1
    fi

    info "Ollama kuruldu."
}

# ==== Ollama Servisi Baslat ====
start_ollama() {
    if pgrep -x "ollama" >/dev/null 2>&1; then
        info "Ollama servisi zaten calisiyor."
        return 0
    fi

    info "Ollama servisi baslatiliyor..."
    ollama serve &>/dev/null &
    sleep 3

    if ! pgrep -x "ollama" >/dev/null 2>&1; then
        warn "Ollama baslatilamadi. Manuel deneyin: ollama serve"
    fi
}

# ==== Model Indirme ====
download_models() {
    info "Qwen2.5-Coder 3B indiriliyor (~1.8 GB)..."
    info "Bu islem internet hiziniza bagli olarak 5-30 dakika surebilir."

    ollama pull qwen2.5-coder:3b

    info "Model indirildi."

    # Olustur: Proje icin ozellestirilmis Modelfile
    cat > /tmp/linux-ai-coder.Modelfile << 'MODELFILE'
FROM qwen2.5-coder:3b

PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER num_ctx 4096
PARAMETER num_predict 2048

SYSTEM """You are an expert Linux systems programmer working on the Linux-AI project.
This project includes:
- Linux kernel modules (C) for AI-driven system management
- Python AI daemons for CPU/GPU monitoring and optimization
- Compressed data pipelines (delta encoding, bit-packing, gzip)

Hardware target: Intel i7-M640 (2C/4T), 8GB RAM, NVIDIA GT 330M.
Always optimize for minimal memory and CPU usage.

Code conventions:
- C: Linux kernel style, 4-space indent, snake_case
- Python: PEP 8, type hints where helpful, no unnecessary dependencies
- Comments in English, user-facing messages in Turkish
- Security: no system(), no eval(), no shell injection
"""
MODELFILE

    info "Linux-AI ozel profil olusturuluyor..."
    ollama create linux-ai-coder -f /tmp/linux-ai-coder.Modelfile
    rm -f /tmp/linux-ai-coder.Modelfile

    info "Profil olusturuldu: linux-ai-coder"
}

# ==== Ollama Yapilandirma ====
configure_ollama() {
    # CPU-only mod (GT 330M kullanilamaz)
    export OLLAMA_NUM_GPU=0

    # i7-M640 icin thread ayari (4 thread)
    export OLLAMA_NUM_THREAD=4

    # Bellek limiti (sistemde 8 GB var, Ollama'ya max 4 GB)
    export OLLAMA_MAX_LOADED_MODELS=1

    # Systemd service dosyasi olustur
    if [ -d /etc/systemd/system ]; then
        sudo tee /etc/systemd/system/ollama-env.conf > /dev/null << 'EOF'
[Service]
Environment="OLLAMA_NUM_GPU=0"
Environment="OLLAMA_NUM_THREAD=4"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
EOF
        info "Ollama systemd ortam degiskenleri ayarlandi."
    fi

    # Shell profil'e ekle
    local profile="$HOME/.bashrc"
    if ! grep -q "OLLAMA_NUM_GPU" "$profile" 2>/dev/null; then
        cat >> "$profile" << 'EOF'

# Ollama - Linux-AI dev (CPU-only, i7-M640 optimized)
export OLLAMA_NUM_GPU=0
export OLLAMA_NUM_THREAD=4
export OLLAMA_MAX_LOADED_MODELS=1
EOF
        info "Ollama ortam degiskenleri ~/.bashrc'ye eklendi."
    fi
}

# ==== Continue.dev (VS Code AI plugin) ====
setup_continue() {
    if command -v code &>/dev/null; then
        info "VS Code Continue eklentisi kuruluyor..."
        code --install-extension Continue.continue 2>/dev/null || true
        info "Continue eklentisi kuruldu (veya zaten mevcuttu)."
    else
        warn "VS Code bulunamadi. Continue.dev'i manuel kurun:"
        warn "  VS Code -> Extensions -> 'Continue' ara -> Install"
    fi
}

# ==== Claude Code ====
setup_claude_code() {
    if command -v claude &>/dev/null; then
        info "Claude Code zaten kurulu."
        return 0
    fi

    if command -v npm &>/dev/null; then
        info "Claude Code kuruluyor..."
        npm install -g @anthropic-ai/claude-code 2>/dev/null || {
            warn "Claude Code npm ile kurulamadi. Manuel kurun:"
            warn "  npm install -g @anthropic-ai/claude-code"
        }
    else
        warn "npm bulunamadi. Claude Code icin:"
        warn "  1. Node.js kurun: https://nodejs.org/"
        warn "  2. npm install -g @anthropic-ai/claude-code"
    fi
}

# ==== Test ====
test_setup() {
    info "Kurulum test ediliyor..."

    echo ""
    echo "=== Kurulum Durumu ==="

    # Ollama
    if command -v ollama &>/dev/null; then
        echo -e "  Ollama:        ${GREEN}OK${NC}"
        # Model kontrolu
        if ollama list 2>/dev/null | grep -q "linux-ai-coder"; then
            echo -e "  linux-ai-coder:${GREEN}OK${NC}"
        elif ollama list 2>/dev/null | grep -q "qwen2.5-coder"; then
            echo -e "  qwen2.5-coder: ${GREEN}OK${NC}"
        else
            echo -e "  Model:         ${YELLOW}Indirilmedi${NC}"
        fi
    else
        echo -e "  Ollama:        ${RED}Kurulu Degil${NC}"
    fi

    # Claude Code
    if command -v claude &>/dev/null; then
        echo -e "  Claude Code:   ${GREEN}OK${NC}"
    else
        echo -e "  Claude Code:   ${YELLOW}Kurulu Degil${NC}"
    fi

    # VS Code
    if command -v code &>/dev/null; then
        echo -e "  VS Code:       ${GREEN}OK${NC}"
    else
        echo -e "  VS Code:       ${YELLOW}Kurulu Degil${NC}"
    fi

    echo ""
    info "Kullanim:"
    echo "  ollama run linux-ai-coder    # Yerel AI ile sohbet"
    echo "  claude                        # Claude Code baslat"
    echo "  Continue.dev                  # VS Code icinde AI (Ctrl+L)"
    echo ""
    info "Ornek: Yerel AI'ya sor"
    echo '  ollama run linux-ai-coder "proc-CPUIO icin per-core monitoring yaz"'
}

# ==== Ana ====
main() {
    echo ""
    echo "========================================="
    echo "  Linux-AI: AI Dev Ortami Kurulumu"
    echo "  Hedef: i7-M640, 8GB RAM (CPU-only)"
    echo "========================================="
    echo ""

    check_system
    install_ollama
    start_ollama
    configure_ollama
    download_models
    setup_continue
    setup_claude_code
    test_setup

    info "Kurulum tamamlandi!"
}

main "$@"

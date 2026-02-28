#!/bin/bash
# =============================================================================
# Linux-AI OS - Post-Installation Script
# =============================================================================
# İlk boot'ta otomatik çalışır. Linux-AI'yi kurar ve masaüstünü ayarlar.
# Bu script kendini cron'dan siler (tek seferlik).
# =============================================================================

set -euo pipefail

LOG="/var/log/linux-ai-postinstall.log"
exec > >(tee -a "$LOG") 2>&1

echo "=========================================="
echo " Linux-AI OS - Post Install Başlıyor"
echo " $(date)"
echo "=========================================="

# --- Kendini cron'dan sil (bir kere çalışsın yeter) ---
sed -i '/post-install.sh/d' /etc/crontab

# --- İnternet bekle ---
echo "[1/8] İnternet bağlantısı bekleniyor..."
for i in $(seq 1 30); do
    if ping -c1 -W2 8.8.8.8 &>/dev/null; then
        echo "  İnternet: OK"
        break
    fi
    echo "  Bekleniyor... ($i/30)"
    sleep 5
done

# --- Sistem güncelle ---
echo "[2/8] Sistem güncelleniyor..."
apt-get update -qq
apt-get upgrade -y -qq

# --- Linux-AI Klonla ---
echo "[3/8] Linux-AI indiriliyor..."
INSTALL_DIR="/opt/linux-ai"

if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR"
    git pull --ff-only 2>/dev/null || true
else
    git clone https://github.com/turer73/Linux-AI.git "$INSTALL_DIR"
fi

# --- Full Install çalıştır ---
echo "[4/8] Linux-AI kuruluyor..."
cd "$INSTALL_DIR"
bash scripts/full-install.sh --no-models 2>&1 || {
    echo "UYARI: full-install.sh bazı adımlarda hata verdi, devam ediliyor..."
}

# --- Ollama modelleri (arka planda indir) ---
echo "[5/8] AI modelleri indiriliyor (arka plan)..."
if command -v ollama &>/dev/null; then
    # Ollama servisini başlat
    systemctl start ollama 2>/dev/null || (nohup ollama serve > /tmp/ollama.log 2>&1 &)
    sleep 5

    # CPU-only ayarla
    export OLLAMA_NUM_GPU=0
    CPU_CORES=$(nproc)
    export OLLAMA_NUM_THREAD="$CPU_CORES"

    # Modeli arka planda indir
    nohup bash -c '
        sleep 10
        ollama pull qwen2.5-coder:3b 2>/dev/null
        RAM_MB=$(free -m | awk "/Mem:/ {print \$2}")
        if [ "$RAM_MB" -ge 7500 ]; then
            ollama pull qwen2.5:7b 2>/dev/null
        fi
        echo "Model indirme tamamlandı" >> /var/log/linux-ai-postinstall.log
    ' &>/dev/null &
fi

# --- Masaüstü ayarla ---
echo "[6/8] Masaüstü yapılandırılıyor..."
if [ -f /opt/linux-ai-setup/desktop-setup.sh ]; then
    bash /opt/linux-ai-setup/desktop-setup.sh
fi

# --- LightDM otomatik giriş ---
echo "[7/8] Otomatik giriş ayarlanıyor..."
mkdir -p /etc/lightdm/lightdm.conf.d
cat > /etc/lightdm/lightdm.conf.d/50-linux-ai.conf << 'LDMEOF'
[Seat:*]
autologin-user=aiadmin
autologin-user-timeout=0
user-session=xfce
greeter-hide-users=false
LDMEOF

# --- Temizlik ve son ayarlar ---
echo "[8/8] Son ayarlar..."

# Gereksiz paketleri temizle
apt-get autoremove -y -qq 2>/dev/null || true
apt-get clean

# Swap ayarla (swappiness düşür - AI modelleri için)
echo "vm.swappiness=10" > /etc/sysctl.d/99-linux-ai.conf
sysctl -p /etc/sysctl.d/99-linux-ai.conf 2>/dev/null || true

# /etc/environment - global ortam değişkenleri
cat >> /etc/environment << 'ENVEOF'
OLLAMA_NUM_GPU=0
OLLAMA_MAX_LOADED_MODELS=1
LINUX_AI_HOME=/opt/linux-ai
LINUX_AI_CONFIG=/var/AI-stump
ENVEOF

# Motd (login mesajı)
cat > /etc/motd << 'MOTDEOF'

  ╔══════════════════════════════════════╗
  ║         Linux-AI OS v0.3.0          ║
  ║   AI-Powered System Management      ║
  ╠══════════════════════════════════════╣
  ║  ai-monitor dashboard  → Sistem     ║
  ║  ai-agent              → AI Asistan ║
  ║  ai-web-agent --help   → Web Ops    ║
  ║  ai-backup run         → Yedekle    ║
  ║  ai-logs view          → Loglar     ║
  ╚══════════════════════════════════════╝

MOTDEOF

# Post-install dosyalarını temizle
rm -rf /opt/linux-ai-setup

echo ""
echo "=========================================="
echo " Linux-AI OS kurulumu tamamlandı!"
echo " Sistem yeniden başlatılıyor..."
echo " $(date)"
echo "=========================================="

# Reboot (masaüstü ile açılsın)
sleep 3
reboot

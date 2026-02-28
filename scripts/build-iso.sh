#!/bin/bash
# =============================================================================
# Linux-AI OS - Custom ISO Builder
# =============================================================================
#
# Ubuntu 22.04 Minimal ISO üzerine Linux-AI'yı gömerek özel ISO oluşturur.
# Bu scripti MEVCUT bir Linux makinede çalıştırın (WSL2 de olur).
#
# Gereksinimler:
#   sudo apt install -y xorriso isolinux syslinux-utils wget p7zip-full
#
# Kullanım:
#   sudo bash build-iso.sh                    # Varsayılan ISO oluştur
#   sudo bash build-iso.sh --source /path/to/ubuntu.iso  # Kaynak ISO belirt
#
# Çıktı: /tmp/linux-ai-os/linux-ai-os-0.3.0.iso
# =============================================================================

set -euo pipefail

# --- Renkler ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${GREEN}[build-iso]${NC} $1"; }
warn()  { echo -e "${YELLOW}[build-iso]${NC} $1"; }
error() { echo -e "${RED}[build-iso]${NC} $1"; }
step()  { echo -e "\n${BOLD}${CYAN}>>> $1${NC}\n"; }

# --- Ayarlar ---
VERSION="0.3.0"
WORK_DIR="/tmp/linux-ai-os"
ISO_NAME="linux-ai-os-${VERSION}.iso"
ISO_LABEL="Linux-AI-OS"
SOURCE_ISO=""
UBUNTU_URL="https://releases.ubuntu.com/22.04/ubuntu-22.04.4-live-server-amd64.iso"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# --- Argümanlar ---
for arg in "$@"; do
    case $arg in
        --source=*) SOURCE_ISO="${arg#*=}" ;;
        --source)   shift; SOURCE_ISO="$1" ;;
        --help|-h)
            echo "Kullanım: sudo bash build-iso.sh [--source /path/to/ubuntu.iso]"
            exit 0 ;;
    esac
done

# --- Root kontrolü ---
if [ "$(id -u)" -ne 0 ]; then
    error "Root olarak çalıştırın: sudo bash build-iso.sh"
    exit 1
fi

# --- Bağımlılıklar ---
check_deps() {
    step "1/6 - Bağımlılık Kontrolü"

    DEPS=(xorriso isolinux p7zip-full wget syslinux-utils)
    MISSING=()

    for dep in "${DEPS[@]}"; do
        if ! dpkg -l "$dep" &>/dev/null; then
            MISSING+=("$dep")
        fi
    done

    if [ ${#MISSING[@]} -gt 0 ]; then
        info "Eksik paketler kuruluyor: ${MISSING[*]}"
        apt-get update -qq
        apt-get install -y -qq "${MISSING[@]}"
    fi

    info "Bağımlılıklar: OK"
}

# --- Ubuntu ISO indir ---
get_source_iso() {
    step "2/6 - Ubuntu ISO"

    mkdir -p "$WORK_DIR"

    if [ -n "$SOURCE_ISO" ] && [ -f "$SOURCE_ISO" ]; then
        info "Kaynak ISO: $SOURCE_ISO"
        return
    fi

    # Önceden indirilmiş mi?
    SOURCE_ISO="$WORK_DIR/ubuntu-source.iso"
    if [ -f "$SOURCE_ISO" ]; then
        info "Önceden indirilmiş ISO bulundu: $SOURCE_ISO"
        return
    fi

    info "Ubuntu 22.04 ISO indiriliyor (~1.4 GB)..."
    info "URL: $UBUNTU_URL"
    wget -q --show-progress -O "$SOURCE_ISO" "$UBUNTU_URL"
    info "İndirme tamamlandı."
}

# --- ISO'yu aç ---
extract_iso() {
    step "3/6 - ISO Açılıyor"

    EXTRACT_DIR="$WORK_DIR/iso-extract"

    if [ -d "$EXTRACT_DIR" ]; then
        info "Önceki çıkarma temizleniyor..."
        rm -rf "$EXTRACT_DIR"
    fi

    mkdir -p "$EXTRACT_DIR"

    info "ISO açılıyor..."
    7z x -o"$EXTRACT_DIR" "$SOURCE_ISO" -y > /dev/null 2>&1 || {
        # Fallback: mount + copy
        info "7z başarısız, mount ile deneniyor..."
        MOUNT_DIR="$WORK_DIR/iso-mount"
        mkdir -p "$MOUNT_DIR"
        mount -o loop "$SOURCE_ISO" "$MOUNT_DIR"
        cp -rT "$MOUNT_DIR" "$EXTRACT_DIR"
        umount "$MOUNT_DIR"
        rmdir "$MOUNT_DIR"
    }

    # Yazma izni ver
    chmod -R u+w "$EXTRACT_DIR"

    info "ISO açıldı: $EXTRACT_DIR"
}

# --- Linux-AI dosyalarını göm ---
embed_linux_ai() {
    step "4/6 - Linux-AI Dosyaları Gömülüyor"

    EXTRACT_DIR="$WORK_DIR/iso-extract"
    LINUX_AI_DIR="$EXTRACT_DIR/linux-ai"

    mkdir -p "$LINUX_AI_DIR"

    # Preseed dosyası
    info "Preseed kopyalanıyor..."
    cp "$SCRIPT_DIR/preseed.cfg" "$EXTRACT_DIR/preseed.cfg"

    # Post-install scriptleri
    info "Kurulum scriptleri kopyalanıyor..."
    cp "$SCRIPT_DIR/post-install.sh" "$LINUX_AI_DIR/post-install.sh"
    cp "$SCRIPT_DIR/desktop-setup.sh" "$LINUX_AI_DIR/desktop-setup.sh"
    cp "$SCRIPT_DIR/full-install.sh" "$LINUX_AI_DIR/full-install.sh"

    chmod +x "$LINUX_AI_DIR"/*.sh

    # GRUB'a preseed ekle
    info "Boot yapılandırması ayarlanıyor..."

    # GRUB config varsa düzenle
    GRUB_CFG="$EXTRACT_DIR/boot/grub/grub.cfg"
    if [ -f "$GRUB_CFG" ]; then
        # Yeni menü girdisi ekle (en başa)
        GRUB_ENTRY='
menuentry "Linux-AI OS Kur (Otomatik)" {
    set gfxpayload=keep
    linux /casper/vmlinuz autoinstall ds=nocloud-net\\;s=/cdrom/ quiet ---
    initrd /casper/initrd
}
'
        # Mevcut grub.cfg'nin başına ekle
        echo "$GRUB_ENTRY" | cat - "$GRUB_CFG" > /tmp/grub_tmp && mv /tmp/grub_tmp "$GRUB_CFG"
        info "GRUB menüsü güncellendi."
    fi

    # Autoinstall için cloud-init (Ubuntu 22.04 live server)
    NOCLOUD_DIR="$EXTRACT_DIR/nocloud"
    mkdir -p "$NOCLOUD_DIR"

    cat > "$NOCLOUD_DIR/user-data" << 'USERDATA'
#cloud-config
autoinstall:
  version: 1
  locale: tr_TR.UTF-8
  keyboard:
    layout: tr

  identity:
    hostname: linux-ai
    username: aiadmin
    # Şifre: linux-ai (değiştirin!)
    password: "$6$rounds=4096$xyz$hashed"

  ssh:
    install-server: true
    allow-pw: true

  storage:
    layout:
      name: lvm
      sizing-policy: all

  packages:
    - build-essential
    - gcc
    - g++
    - make
    - cmake
    - python3
    - python3-pip
    - python3-venv
    - python3-dev
    - curl
    - wget
    - git
    - openssl
    - libssl-dev
    - libffi-dev
    - lm-sensors
    - htop
    - cron
    - xfce4
    - xfce4-goodies
    - xfce4-terminal
    - lightdm
    - lightdm-gtk-greeter
    - firefox
    - network-manager
    - thunar
    - xfce4-power-manager
    - pulseaudio
    - pavucontrol

  late-commands:
    - mkdir -p /target/opt/linux-ai-setup
    - cp /cdrom/linux-ai/post-install.sh /target/opt/linux-ai-setup/
    - cp /cdrom/linux-ai/desktop-setup.sh /target/opt/linux-ai-setup/
    - cp /cdrom/linux-ai/full-install.sh /target/opt/linux-ai-setup/
    - chmod +x /target/opt/linux-ai-setup/*.sh
    - curtin in-target -- bash -c 'echo "@reboot root /opt/linux-ai-setup/post-install.sh" >> /etc/crontab'
USERDATA

    touch "$NOCLOUD_DIR/meta-data"

    info "Linux-AI dosyaları gömüldü."
}

# --- ISO'yu yeniden oluştur ---
build_iso() {
    step "5/6 - ISO Oluşturuluyor"

    EXTRACT_DIR="$WORK_DIR/iso-extract"
    OUTPUT_ISO="$WORK_DIR/$ISO_NAME"

    info "ISO derleniyor: $OUTPUT_ISO"
    info "Bu işlem birkaç dakika sürebilir..."

    # MBR dosyasını bul
    MBR_BIN=""
    if [ -f /usr/lib/ISOLINUX/isohdpfx.bin ]; then
        MBR_BIN="/usr/lib/ISOLINUX/isohdpfx.bin"
    elif [ -f "$EXTRACT_DIR/isolinux/isohdpfx.bin" ]; then
        MBR_BIN="$EXTRACT_DIR/isolinux/isohdpfx.bin"
    fi

    # xorriso ile ISO oluştur
    xorriso -as mkisofs \
        -r -V "$ISO_LABEL" \
        -J -joliet-long \
        -o "$OUTPUT_ISO" \
        -isohybrid-mbr "${MBR_BIN:-/usr/lib/ISOLINUX/isohdpfx.bin}" \
        -partition_offset 16 \
        --grub2-mbr "${MBR_BIN:-/usr/lib/ISOLINUX/isohdpfx.bin}" \
        -appended_part_as_gpt \
        -iso_mbr_part_type 0x00 \
        -c boot.catalog \
        -b boot/grub/i386-pc/eltorito.img \
        -no-emul-boot -boot-load-size 4 -boot-info-table --grub2-boot-info \
        -eltorito-alt-boot \
        -e EFI/boot/bootx64.efi \
        -no-emul-boot \
        "$EXTRACT_DIR" 2>/dev/null || {
            # Basit fallback
            warn "Gelişmiş ISO oluşturma başarısız, basit mod deneniyor..."
            xorriso -as mkisofs \
                -r -V "$ISO_LABEL" \
                -J -joliet-long \
                -o "$OUTPUT_ISO" \
                "$EXTRACT_DIR" 2>/dev/null
        }

    if [ -f "$OUTPUT_ISO" ]; then
        ISO_SIZE=$(du -h "$OUTPUT_ISO" | cut -f1)
        info "ISO oluşturuldu: $OUTPUT_ISO ($ISO_SIZE)"
    else
        error "ISO oluşturulamadı!"
        exit 1
    fi
}

# --- Rapor ---
final_report() {
    step "6/6 - Tamamlandı"

    OUTPUT_ISO="$WORK_DIR/$ISO_NAME"
    ISO_SIZE=$(du -h "$OUTPUT_ISO" | cut -f1)
    ISO_MD5=$(md5sum "$OUTPUT_ISO" | cut -d' ' -f1)

    echo -e "${BOLD}==========================================${NC}"
    echo -e "${BOLD}  Linux-AI OS ISO Hazır!${NC}"
    echo -e "${BOLD}==========================================${NC}"
    echo ""
    echo -e "  ${CYAN}Dosya:${NC}    $OUTPUT_ISO"
    echo -e "  ${CYAN}Boyut:${NC}    $ISO_SIZE"
    echo -e "  ${CYAN}MD5:${NC}      $ISO_MD5"
    echo -e "  ${CYAN}Sürüm:${NC}   $VERSION"
    echo ""
    echo -e "  ${CYAN}İçerik:${NC}"
    echo -e "    - Ubuntu 22.04 LTS Minimal"
    echo -e "    - XFCE4 Masaüstü (hafif)"
    echo -e "    - Linux-AI v${VERSION} (otomatik kurulum)"
    echo -e "    - Ollama AI Engine"
    echo -e "    - Tailscale VPN"
    echo ""
    echo -e "  ${CYAN}Kullanım:${NC}"
    echo -e "    1. ISO'yu USB'ye yaz: ${BOLD}sudo dd if=$OUTPUT_ISO of=/dev/sdX bs=4M status=progress${NC}"
    echo -e "       veya Rufus/balenaEtcher kullan"
    echo -e "    2. USB'den boot et"
    echo -e "    3. 'Linux-AI OS Kur' seçeneğini seç"
    echo -e "    4. Otomatik kurulum başlar (~15-30 dk)"
    echo ""
    echo -e "  ${CYAN}Varsayılan Giriş:${NC}"
    echo -e "    Kullanıcı: ${BOLD}aiadmin${NC}"
    echo -e "    Şifre:     ${BOLD}linux-ai${NC} (ilk girişte değiştir!)"
    echo ""
    echo -e "==========================================="

    # Temizlik öner
    EXTRACT_SIZE=$(du -sh "$WORK_DIR/iso-extract" 2>/dev/null | cut -f1)
    echo ""
    echo -e "  ${YELLOW}Temizlik:${NC} rm -rf $WORK_DIR/iso-extract (${EXTRACT_SIZE:-?} tasarruf)"
    echo ""
}

# --- Ana ---
main() {
    echo ""
    echo -e "${BOLD}============================================${NC}"
    echo -e "${BOLD}  Linux-AI OS - ISO Builder v${VERSION}${NC}"
    echo -e "${BOLD}============================================${NC}"
    echo ""

    check_deps
    get_source_iso
    extract_iso
    embed_linux_ai
    build_iso
    final_report
}

main "$@"

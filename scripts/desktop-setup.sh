#!/bin/bash
# =============================================================================
# Linux-AI OS - Desktop Setup (XFCE4 Özelleştirme)
# =============================================================================
# Hafif XFCE masaüstünü Linux-AI temasıyla yapılandırır.
# =============================================================================

USER_HOME="/home/aiadmin"
USER="aiadmin"

echo "[Desktop] XFCE yapılandırılıyor..."

# --- Masaüstü kısayolları ---
DESKTOP_DIR="$USER_HOME/Desktop"
mkdir -p "$DESKTOP_DIR"

# Terminal kısayolu
cat > "$DESKTOP_DIR/terminal.desktop" << 'DEOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Terminal
Comment=Linux-AI Terminal
Exec=xfce4-terminal
Icon=utilities-terminal
Terminal=false
Categories=System;TerminalEmulator;
DEOF

# AI Monitor Dashboard kısayolu
cat > "$DESKTOP_DIR/ai-monitor.desktop" << 'DEOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=AI Monitor
Comment=Linux-AI Sistem İzleme
Exec=xfce4-terminal -e "ai-monitor dashboard"
Icon=utilities-system-monitor
Terminal=false
Categories=System;Monitor;
DEOF

# AI Agent kısayolu
cat > "$DESKTOP_DIR/ai-agent.desktop" << 'DEOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=AI Agent
Comment=Linux-AI Akıllı Asistan
Exec=xfce4-terminal -e "ai-agent"
Icon=dialog-information
Terminal=false
Categories=System;
DEOF

# AI Logs kısayolu
cat > "$DESKTOP_DIR/ai-logs.desktop" << 'DEOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=AI Logs
Comment=Linux-AI Log Görüntüleyici
Exec=xfce4-terminal -e "ai-logs tail"
Icon=text-x-log
Terminal=false
Categories=System;
DEOF

# Backup kısayolu
cat > "$DESKTOP_DIR/ai-backup.desktop" << 'DEOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=AI Backup
Comment=Linux-AI Yedekleme
Exec=xfce4-terminal -e "ai-backup run"
Icon=drive-harddisk
Terminal=false
Categories=System;
DEOF

# Dosya Yöneticisi
cat > "$DESKTOP_DIR/files.desktop" << 'DEOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Dosyalar
Comment=Dosya Yöneticisi
Exec=thunar
Icon=system-file-manager
Terminal=false
Categories=System;FileTools;FileManager;
DEOF

chmod +x "$DESKTOP_DIR"/*.desktop

# --- XFCE Panel Yapılandırması ---
XFCE_DIR="$USER_HOME/.config/xfce4/xfconf/xfce-perchannel-xml"
mkdir -p "$XFCE_DIR"

# Panel ayarları - tek panel, alt kısımda
cat > "$XFCE_DIR/xfce4-panel.xml" << 'PEOF'
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfce4-panel" version="1.0">
  <property name="configver" type="int" value="2"/>
  <property name="panels" type="array">
    <value type="int" value="1"/>
    <property name="panel-1" type="empty">
      <property name="position" type="string" value="p=8;x=0;y=0"/>
      <property name="length" type="uint" value="100"/>
      <property name="position-locked" type="bool" value="true"/>
      <property name="size" type="uint" value="30"/>
      <property name="plugin-ids" type="array">
        <value type="int" value="1"/>
        <value type="int" value="2"/>
        <value type="int" value="3"/>
        <value type="int" value="4"/>
        <value type="int" value="5"/>
        <value type="int" value="6"/>
        <value type="int" value="7"/>
        <value type="int" value="8"/>
      </property>
    </property>
  </property>
  <property name="plugins" type="empty">
    <property name="plugin-1" type="string" value="applicationsmenu"/>
    <property name="plugin-2" type="string" value="tasklist"/>
    <property name="plugin-3" type="string" value="separator">
      <property name="expand" type="bool" value="true"/>
    </property>
    <property name="plugin-4" type="string" value="systray"/>
    <property name="plugin-5" type="string" value="pulseaudio"/>
    <property name="plugin-6" type="string" value="power-manager-plugin"/>
    <property name="plugin-7" type="string" value="clock"/>
    <property name="plugin-8" type="string" value="actions"/>
  </property>
</channel>
PEOF

# --- Terminal ayarları (koyu tema, daha iyi okunabilirlik) ---
TERM_DIR="$USER_HOME/.config/xfce4/terminal"
mkdir -p "$TERM_DIR"

cat > "$TERM_DIR/terminalrc" << 'TEOF'
[Configuration]
FontName=Monospace 11
MiscAlwaysShowTabs=FALSE
MiscBell=FALSE
MiscBellUrgent=FALSE
MiscBordersDefault=TRUE
MiscCursorBlinks=TRUE
MiscCursorShape=TERMINAL_CURSOR_SHAPE_BLOCK
MiscDefaultGeometry=120x35
MiscInheritGeometry=FALSE
MiscMenubarDefault=TRUE
MiscMouseAutohide=FALSE
MiscMouseWheelZoom=TRUE
MiscToolbarDefault=FALSE
MiscConfirmClose=TRUE
MiscCycleTabs=TRUE
MiscTabCloseButtons=TRUE
MiscTabCloseMiddleClick=TRUE
MiscTabPosition=GTK_POS_TOP
MiscHighlightUrls=TRUE
MiscMiddleClickOpensUri=FALSE
MiscCopyOnSelect=FALSE
MiscShowRelaunchDialog=TRUE
MiscRewrapOnResize=TRUE
MiscUseShiftArrowsToScroll=FALSE
MiscSlimTabs=FALSE
MiscNewTabAdjacent=FALSE
MiscSearchDialogOpacity=100
MiscShowUnsafePasteDialog=FALSE
ScrollingBar=TERMINAL_SCROLLBAR_NONE
ScrollingLines=10000
ColorForeground=#d0d0d0
ColorBackground=#1a1a2e
ColorCursor=#00d4aa
ColorPalette=#1a1a2e;#ff6b6b;#00d4aa;#ffd93d;#6bcbff;#c084fc;#00d4aa;#d0d0d0;#4a4a5e;#ff8585;#33e6be;#ffe566;#85d5ff;#d4a0ff;#33e6be;#ffffff
BackgroundMode=TERMINAL_BACKGROUND_TRANSPARENT
BackgroundDarkness=0.920000
TEOF

# --- Autostart - AI Monitor arka planda ---
AUTOSTART_DIR="$USER_HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"

# Sistem bilgisi göster (login'de)
cat > "$AUTOSTART_DIR/linux-ai-welcome.desktop" << 'AEOF'
[Desktop Entry]
Type=Application
Name=Linux-AI Welcome
Exec=xfce4-terminal --title="Linux-AI Dashboard" -e "bash -c 'ai-monitor dashboard; exec bash'"
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
AEOF

# --- Duvar kağıdı ayarı (koyu mavi tema) ---
cat > "$XFCE_DIR/xfce4-desktop.xml" << 'WEOF'
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfce4-desktop" version="1.0">
  <property name="backdrop" type="empty">
    <property name="screen0" type="empty">
      <property name="monitorVirtual-1" type="empty">
        <property name="workspace0" type="empty">
          <property name="color-style" type="int" value="1"/>
          <property name="color1" type="array">
            <value type="uint" value="6682"/>
            <value type="uint" value="6682"/>
            <value type="uint" value="11822"/>
          </property>
          <property name="color2" type="array">
            <value type="uint" value="2570"/>
            <value type="uint" value="2570"/>
            <value type="uint" value="7710"/>
          </property>
          <property name="image-style" type="int" value="0"/>
        </property>
      </property>
    </property>
  </property>
</channel>
WEOF

# --- Bash profil (aiadmin için) ---
cat >> "$USER_HOME/.bashrc" << 'BEOF'

# --- Linux-AI Environment ---
export LINUX_AI_HOME=/opt/linux-ai
export LINUX_AI_CONFIG=/var/AI-stump
export OLLAMA_NUM_GPU=0
export OLLAMA_MAX_LOADED_MODELS=1

# Kısa yollar
alias monitor='ai-monitor dashboard'
alias agent='ai-agent'
alias backup='ai-backup run'
alias logs='ai-logs tail'
alias status='ai-monitor check'

# Prompt
PS1='\[\033[0;36m\][\[\033[1;32m\]linux-ai\[\033[0;36m\]]\[\033[0;33m\] \w\[\033[0m\] \$ '

# İlk açılışta bilgi göster
if [ -z "$LINUX_AI_GREETED" ]; then
    export LINUX_AI_GREETED=1
    echo ""
    echo -e "\033[1;36m  Linux-AI OS v0.3.0\033[0m"
    echo -e "\033[0;32m  Komutlar: monitor | agent | backup | logs | status\033[0m"
    echo ""
fi
BEOF

# --- Sahiplik ayarla ---
chown -R "$USER:$USER" "$USER_HOME/.config" 2>/dev/null || true
chown -R "$USER:$USER" "$USER_HOME/Desktop" 2>/dev/null || true
chown "$USER:$USER" "$USER_HOME/.bashrc" 2>/dev/null || true

echo "[Desktop] XFCE yapılandırması tamamlandı."

# nproc-kernel - Linux-AI Kernel Module & Userspace Tools

Linux kernel modulu ve kullanici alani araclari. AI tabanli sistem yonetimi icin
kernel seviyesinde arayuzler saglar.

## Mimari

```
nproc-kernel/
  ├── include/               # Ortak header dosyalari (kernel + userspace)
  │   ├── ai_common.h        # Ortak tanimlar, veri yapilari
  │   ├── ai_ioctl.h         # ioctl komut tanimlari
  │   └── ai_permissions.h   # Izin yonetimi API
  ├── kmod/                   # Linux kernel modulu (.ko)
  │   ├── ai_core.c          # Ana kernel modulu, cdev, ioctl handler
  │   ├── ai_procfs.c        # /proc/ai_status, /proc/ai_config
  │   ├── ai_sysfs.c         # /sys/ai/* ozellikleri
  │   ├── Kbuild             # Kernel build yapilandirmasi
  │   └── Makefile           # DKMS uyumlu build
  ├── userspace/              # Kullanici alani araclari
  │   ├── ai_ctl.c           # ioctl tabanli kontrol araci
  │   ├── ai_status.c        # Sistem durumu sorgulama
  │   ├── ai_permissions.c   # Izin yonetimi araci
  │   └── Makefile
  ├── include-old/            # Eski header dosyalari (arsiv, silinecek)
  ├── kernel-start.c          # Eski test istemcisi (arsiv)
  ├── grant_permission_revoke.c # Eski izin kodu (arsiv)
  └── dkms.conf               # DKMS otomatik yukleme
```

## Kernel Arayuzleri

### /dev/ai_ctl (ioctl)
- `AI_IOC_GET_STATUS` - Sistem durumu sorgulama
- `AI_IOC_SET_GOVERNOR` - CPU governor modunu degistir
- `AI_IOC_REQUEST_PERM` - Izin talebi
- `AI_IOC_REGISTER_SVC` - Servis kaydi

### /proc/ai_status (read-only)
CPU frekanslari, modul durumu, governor bilgisi

### /proc/ai_config (read/write)
`governor=<mod>` ve `state=<durum>` yazmak icin

### /sys/ai/*
- `version` (RO), `state` (RW), `governor` (RW), `cpu_count` (RO), `services` (RO)

## Kullanici Araclari

```bash
# Durum sorgulama
ai_status
ai_status --json
ai_status --brief

# Kontrol
ai_ctl status
ai_ctl governor ai-adaptive
ai_ctl service add myapp
ai_ctl reset

# Izin yonetimi
ai_permissions check
sudo ai_permissions setup        # Gruplari olustur
sudo ai_permissions grant user1  # Kullanici ekle
sudo ai_permissions admin user1  # Admin yap
```

## Derleme

### Userspace araclari
```bash
cd userspace && make
```

### Kernel modulu (Linux gerektirir)
```bash
cd kmod && make
sudo insmod linux_ai.ko
```

### DKMS ile kurulum
```bash
sudo make -C kmod dkms-install
```

## Izin Sistemi

- `ai-admin` grubu: Tam erisim (governor, reset, config yazma)
- `ai-user` grubu: Okuma + servis kaydi
- root: Her seye erisim

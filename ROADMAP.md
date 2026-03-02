# Linux-AI Gelistirme Yol Haritasi

> Son guncelleme: 2026-03-02
> Versiyon: 0.3.0 -> 1.0.0 hedefi

---

## Proje Durumu

| Metrik | Deger |
|--------|-------|
| Toplam Dosya | 116 dosya |
| Python Dosyalari | 37 dosya, ~10,450 satir |
| C/C++ Dosyalari | 28 dosya, ~4,076 satir |
| Toplam Kaynak Kodu | ~14,500+ satir |
| CLI Komutlari | 19 entry point |
| Calisan Bilesenler | ~85% |
| Kirik/Eksik | ~15% (TPU modulu, kernel VM testi) |

---

## Oncelik Matrisi (Guncel)

| Modul | Aciliyet | Etki | Karmasiklik | Oncelik |
|-------|----------|------|-------------|---------|
| Kernel VM testi | Yuksek | Yuksek | Orta | **P0** |
| Test coverage artirma | Yuksek | Orta | Dusuk | **P0** |
| proc-CPUIO iyilestirme | Orta | Yuksek | Orta | **P1** |
| proc-GPUIO NVIDIA destegi | Orta | Yuksek | Orta | **P1** |
| AI model pipeline | Orta | Yuksek | Yuksek | **P2** |
| TPU modulu | Dusuk | Orta | Yuksek | **P3** |
| Multi-DE destegi | Dusuk | Orta | Orta | **P3** |
| Paketleme (DEB/RPM) | Dusuk | Orta | Orta | **P3** |

---

## FAZ 0: KRITIK DUZELTMELER (P0) - [TAMAMLANDI]

### Yapilan Degisiklikler

- [x] `setup.py` duplikat import ve duplikat `setup()` cagrisi duzeltildi
- [x] Lisans tutarsizligi giderildi (MIT -> GPL-2.0-only, tum dosyalarda)
- [x] Yazar bilgisi tutarli hale getirildi (Zaman Huseyinli)
- [x] `requirements.txt` ile `pyproject.toml` senkronize edildi
- [x] `cbinder-gbfs/` -> `cbinder_gbfs/` yeniden adlandirildi (Python import uyumlulugu)
- [x] Tum tireli Python dosyalari alt cizgiye donusturuldu
- [x] `cbinder_gbfs/__init__.py` eklendi
- [x] `ai-analyzer.py` icindeki `eval()` -> `json.loads()` guvenligi saglandi
- [x] Bare `except` -> spesifik exception handling eklendi
- [x] `ai_analyzer.py`'ye `main()` fonksiyonu eklendi (entry_point destegi)
- [x] `sentielcpu_io_stats.h` rastgele veri -> gercek `/proc/diskstats` okuma
- [x] `Makefile` ve `CMakeLists.txt` duzeltmeleri
- [x] `setup.py`, `setup.cfg`, `pyproject.toml` entry_points tire -> alt cizgi

---

## FAZ 1: STABILIZASYON VE TEST ALTYAPISI - [TAMAMLANDI]

- [x] Eski `cbinder-gbfs/` dizini temizlendi
- [x] `.gitignore` dosyasi olusturuldu
- [x] `/var/AI-stump/` init script ve varsayilan YAML sablonlari
- [x] pytest altyapisi (`tests/python/`, `tests/c/`)
- [x] CI/CD: GitHub Actions (`ci.yml` + `deploy.yml`)
- [x] Linting: `flake8` + `black` (Python), `clang-format` (C/C++)
- [x] Her module `README.md` eklendi
- [x] `CONTRIBUTING.md` ve `CHANGELOG.md` olusturuldu
- [ ] Test coverage hedefi: %60+ (testler genisletilecek)

---

## FAZ 2: KERNEL MODULU YENIDEN YAZIMI - [TAMAMLANDI]

Eski headerlar (AI-LFS.hpp, aistdio.hpp, aistdterm.h, permissioner.h) sifirdan yeniden yazildi.

### Yeni Mimari
```
nproc-kernel/
  ├── include/                 # Ortak header (kernel + userspace)
  │   ├── ai_common.h         # Ortak tanimlar, enum, struct
  │   ├── ai_ioctl.h          # ioctl komut tanimlari
  │   └── ai_permissions.h    # Izin yonetimi API
  ├── kmod/                    # Linux kernel modulu (.ko)
  │   ├── ai_core.c           # Ana modul, cdev, ioctl handler
  │   ├── ai_procfs.c         # /proc/ai_status, /proc/ai_config
  │   ├── ai_sysfs.c          # /sys/ai/* ozellikleri
  │   ├── Kbuild              # Kernel build
  │   └── Makefile            # DKMS uyumlu
  ├── userspace/               # Kullanici alani araclari
  │   ├── ai_ctl.c            # ioctl tabanli kontrol araci
  │   ├── ai_status.c         # Sistem durumu sorgulama
  │   ├── ai_permissions.c    # Izin yonetimi (grup tabanli)
  │   └── Makefile
  └── dkms.conf               # DKMS otomatik yukleme
```

### Tamamlanan
- [x] Kernel modulu (ai_core.c, ai_procfs.c, ai_sysfs.c)
- [x] ioctl arayuzu (`/dev/ai_ctl`)
- [x] procfs/sysfs arayuzleri
- [x] Izin sistemi (ai-admin, ai-user gruplari)
- [x] DKMS paketleme
- [x] Userspace araclari (ai_ctl, ai_status, ai_permissions)
- [x] Eski dosyalar tamamen silindi (include-old/, kernel-start.c, grant_permission_revoke.c)

### Kalan (Linux ortaminda test gerekli)
- [ ] Linux VM'de kernel modulu derleme ve test
- [ ] `insmod`/`rmmod` ile yukleme/kaldirma testi
- [ ] ioctl komutlarinin uctan uca testi

---

## FAZ 2.5: AI AGENT VE ALTYAPI EKOSISTEMI - [TAMAMLANDI]

> Bu faz ROADMAP'in orijinal planinda yoktu, v0.3.0 surumunde eklendi.

### AI Agent Sistemi
- [x] `ai_agent.py` - Ollama tabanli tool-calling AI agent (7B/3B model)
- [x] `ai_kernel_bridge.py` - Python ioctl koprusu (/dev/ai_ctl)
- [x] 7 built-in tool: system_info, process_list, kernel_status, governor, read_file, site_health, run_command
- [x] Guvenlik: komut whitelist, dosya yolu kisitlamalari, kullanici onay mekanizmasi

### Web Operasyonlari
- [x] `ai_webops.py` - Vercel, Cloudflare, Supabase, GitHub proje yonetimi
- [x] `ai_browser_agent.py` - API otomasyon agentlari (VercelAgent, CloudflareAgent, SupabaseAgent, GitHubAgent, FalAgent, CoolifyAgent, TailscaleAgent)
- [x] CloudflareAgent WAF: firewall rule CRUD, IP/country block
- [x] TailscaleAgent: mesh VPN yonetimi (status, peers, ping, serve)

### Izleme ve Altyapi
- [x] `ai_monitor.py` - Sistem + web + SSL izleme + Telegram/Discord alert
- [x] `ai_backup.py` - Otomatik yedekleme (config, Supabase, Coolify) + cron
- [x] `ai_logs.py` - Merkezi log toplama, arama, export
- [x] `ai_dashboard.py` - Bloomberg-tarz terminal dashboard (Rich)
- [x] `ai_help.py` - Turkce interaktif yardim sistemi

### Kurulum ve Dagitim
- [x] `ai_dev_setup.py` - Ollama + model + gelistirme ortami kurucu
- [x] `full-install.sh` - Ubuntu/Debian/WSL2 tam kurulum scripti
- [x] `build-iso.sh` - XFCE masaustu ile ozel Linux-AI OS ISO olusturucu
- [x] `deploy.yml` - GitHub Actions CI/CD (test -> Coolify -> Vercel -> notify)

---

## FAZ 3: GPU VE TPU DESTEGI (3-4 Hafta) - [BASLAMADI]

### 3.1 GPU Modulu Gelistirme
- [ ] NVIDIA destegi: `libnvml` (NVML C API) entegrasyonu
- [ ] Multi-GPU tespiti ve yonetimi
- [ ] GPU sicaklik/guc izleme (tum vendorlar icin)
- [ ] GPU frekans/guc profili yonetimi
- [ ] `libdrm` uzerinden dogrudan GPU erisimi
- [ ] Vulkan/OpenCL tabanli GPU izleme alternatifi
- [ ] GPU buffer unit'e gercek metrik yazma

### 3.2 TPU Modulu (Sifirdan)
Eski pseudo-kod dosyalari temizlendi (2026-03-02). Sifirdan yazilacak.

```
PCIO-TPU/
  ├── tpu_detect.c            # PCIe TPU cihaz kesfetme
  ├── tpu_offline.c           # Model donusum ve optimizasyon
  ├── tpu_online.c            # Gercek zamanli inference
  ├── tpu_scheduler.c         # TPU is planlama
  └── include/
      ├── tpu_common.h
      └── tpu_pcie.h
```

- [ ] PCIe cihaz kesfetme (`lspci` + sysfs)
- [ ] Google Edge TPU SDK entegrasyonu (opsiyonel)
- [ ] Offline: Model donusum pipeline (ONNX -> TPU format)
- [ ] Online: Gercek zamanli inference izleme
- [ ] TPU scheduling ve kaynak yonetimi

---

## FAZ 4: AI MODEL PIPELINE (2-3 Hafta) - [BASLAMADI]

### 4.1 Veri Toplama
- [ ] Otomatik veri toplama daemon (ilk kurulumda 24 saat)
- [ ] Sistem metrikleri -> CSV/Parquet formati
- [ ] Veri temizleme ve normalizasyon pipeline

### 4.2 Model Gelistirme
- [ ] LSTM -> Transformer gecisi (daha iyi zaman serisi tahmini)
- [ ] Anomali tespiti modeli ekleme (Isolation Forest veya Autoencoder)
- [ ] Model versiyonlama sistemi
- [ ] Otomatik model yeniden egitim (cron/systemd timer)
- [ ] Model rollback mekanizmasi

### 4.3 Inference Motoru
- [ ] ONNX Runtime entegrasyonu (torch yerine daha hafif)
- [ ] Batch prediction destegi
- [ ] Model performans metrikleri (latency, accuracy)

---

## FAZ 5: MASAUSTU ENTEGRASYONU (2-3 Hafta) - [KISMI]

### 5.1 Mevcut KDE Plasma Destegi
- [x] Plasma modulu temizlendi ve calisir durumda
- [ ] TensorFlow modeli icin egitim verisi pipeline
- [ ] `auto_prop` icin Polkit entegrasyonu (sudo yerine)
- [ ] Plasma System Tray widget

### 5.2 Yeni DE Destekleri
- [ ] GNOME Shell extension
- [x] XFCE destegi (build-iso.sh ile XFCE masaustu)
- [ ] Hyprland/Sway (Wayland) destegi
- [ ] DE-agnostik D-Bus API tasarimi

### 5.3 Kullanici Arayuzleri
- [x] CLI interaktif arayuz (Rich - ai-dashboard)
- [x] Turkce yardim sistemi (ai-help)
- [ ] Web dashboard (FastAPI + htmx/React)
- [ ] System tray ikonu ve bildirim merkezi

---

## FAZ 6: KALITE VE DAGITIM (2-3 Hafta) - [KISMI]

### 6.1 Kod Kalitesi
- [ ] Unit test coverage %80+
- [ ] Integration testleri (VM icerisinde)
- [x] Automated linting (CI/CD'de flake8 + black)
- [ ] Security audit (bandit, cppcheck)

### 6.2 Paketleme
- [ ] AUR paketi guncelleme (mevcut `plasma-system-ai`)
- [ ] DEB paketi (Debian/Ubuntu)
- [ ] RPM paketi (Fedora/RHEL)
- [x] ISO builder (build-iso.sh)
- [ ] Docker konteyneri (test ortami)

### 6.3 Surum Yonetimi
- [ ] Semantic versiyonlama (SemVer)
- [ ] Git tagging stratejisi
- [ ] Release notes otomasyonu
- [ ] GitHub Releases entegrasyonu

### 6.4 Dokumantasyon
- [x] Modul README dosyalari
- [x] CONTRIBUTING.md
- [x] CHANGELOG.md
- [x] GitHub Issue templates
- [ ] API dokumantasyonu (Sphinx veya MkDocs)
- [ ] Kullanici kilavuzu
- [ ] Gelistirici kilavuzu

---

## Modul Detay Analizi

### proc-CPUIO (CPU I/O Yonetimi)
- **Durum:** Fonksiyonel, iyilestirme gerekli
- **Dosyalar:** `proc-CPUIO.c` + 6 header
- **Sorunlar:** Implementasyon .h dosyalarinda, ARM CPU destegi yok, hard-coded buffer boyutlari
- **Iyilestirme:** .h -> .c ayirimi, ARM destegi, yapilandirma dosyasindan esik degerleri

### proc-GPUIO (GPU I/O Yonetimi)
- **Durum:** Kismi (NVIDIA devre disi)
- **Dosyalar:** `proc-GPUIO.cpp` + 2 header
- **Sorunlar:** NVIDIA destegi yok, multi-GPU yok
- **Iyilestirme:** libnvml, libdrm, multi-GPU, sicaklik/guc izleme

### nproc-kernel (Kernel Modulu)
- **Durum:** Kod tamamlandi, Linux VM testi bekliyor
- **Dosyalar:** 3 header + 3 kmod + 3 userspace + dkms.conf
- **Kalan:** Linux VM'de derleme ve uctan uca test

### PCIO-TPU (TPU Segmentasyon)
- **Durum:** Planlanmis - henuz gelistirilmedi
- **Not:** Eski bozuk kod temizlendi (2026-03-02), sifirdan yazilacak

### cbinder_gbfs (Python AI Araclari)
- **Durum:** Aktif, 22 modul
- **Yeni moduller (v0.3.0):** ai_agent, ai_browser_agent, ai_monitor, ai_backup, ai_logs, ai_dashboard, ai_help, ai_dev_setup, ai_kernel_bridge, ai_webops
- **19 CLI entry point** pyproject.toml uzerinden tanimli

### Plasma-system-AI (Masaustu AI)
- **Durum:** Fonksiyonel
- **Kalan:** TF model egitimi, Polkit, multi-DE destegi

---

## Bagimliliklari

### Sistem Bagimliliklari
- gcc/g++ >= 4.8, make >= 3.81, cmake >= 3.10
- linux-headers >= 4.15
- Python >= 3.8

### Python Temel Bagimliliklar
- psutil, PyYAML, numpy, scikit-learn, pandas, rich

### Python Opsiyonel Bagimliliklar
- torch (derin ogrenme), tensorflow (Keras/TFLite)
- pyttsx3 (text-to-speech), watchdog (dosya izleme)
- matplotlib, seaborn (gorsellestirme)
- requests (web API islemleri)

---

## Notlar

- Proje yedegi: `Linux-AI-backup/` dizininde
- Eski `cbinder-gbfs/` dizini tamamen temizlendi
- Eski kernel dosyalari (include-old/, kernel-start.c, grant_permission_revoke.c) silindi (2026-03-02)
- Eski TPU pseudo-kodu temizlendi (2026-03-02)
- FAZ 0, FAZ 1, FAZ 2, FAZ 2.5 tamamlandi
- Kernel modulu gelistirmesi icin Linux VM oneriliyor
- NVIDIA GPU destegi icin NVML SDK gerekli

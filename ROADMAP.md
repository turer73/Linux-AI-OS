# Linux-AI Gelistirme Yol Haritasi

> Son guncelleme: 2026-02-28
> Versiyon: 0.1.0 -> 1.0.0 hedefi

---

## Proje Durumu

| Metrik | Deger |
|--------|-------|
| Toplam Kaynak Kodu | ~3,500+ satir (46 dosya) |
| C/C++ Dosyalari | 13 dosya, ~750 satir |
| Python Dosyalari | 14 dosya, ~1,750 satir |
| Calisan Bilesenler | ~70% |
| Kirik/Eksik | ~30% (kernel headers, TPU modulu) |

---

## Oncelik Matrisi

| Modul | Aciliyet | Etki | Karmasiklik | Oncelik |
|-------|----------|------|-------------|---------|
| Konfigurasyon duzeltmeleri | Yuksek | Orta | Dusuk | **P0** |
| cbinder-gbfs guvenlik | Yuksek | Yuksek | Dusuk | **P0** |
| nproc-kernel yeniden yazim | Yuksek | Yuksek | Yuksek | **P1** |
| proc-CPUIO iyilestirme | Orta | Yuksek | Orta | **P1** |
| proc-GPUIO NVIDIA destegi | Orta | Yuksek | Orta | **P2** |
| Plasma-system-AI duzeltme | Orta | Orta | Dusuk | **P2** |
| TPU modulu | Dusuk | Orta | Yuksek | **P3** |
| Multi-DE destegi | Dusuk | Orta | Orta | **P3** |

---

## FAZ 0: KRITIK DUZELTMELER (P0) - [TAMAMLANDI]

### Yapilan Degisiklikler

- [x] `setup.py` duplikat import ve duplikat `setup()` cagrisi duzeltildi
- [x] Lisans tutarsizligi giderildi (MIT -> GPL-2.0-only, tum dosyalarda)
- [x] Yazar bilgisi tutarli hale getirildi (Zaman Huseyinli)
- [x] `requirements.txt` ile `pyproject.toml` senkronize edildi (PyYAML, watchdog, tensorflow eklendi)
- [x] `cbinder-gbfs/` -> `cbinder_gbfs/` yeniden adlandirildi (Python import uyumlulugu)
- [x] Tum tireli Python dosyalari alt cizgiye donusturuldu
- [x] `cbinder_gbfs/__init__.py` eklendi
- [x] `ai-analyzer.py` icindeki `eval()` -> `json.loads()` guvenligi saglandi
- [x] Bare `except` -> spesifik exception handling eklendi
- [x] `ai_analyzer.py`'ye `main()` fonksiyonu eklendi (entry_point destegi)
- [x] Duplikat `writereadout-tens.py` -> `writereadout_tens_cli.py` olarak yeniden adlandirildi
- [x] `main-fregio.py` -> `main_fregio.py` yeniden adlandirildi
- [x] `plasma_start.py` subprocess referanslari guncellendi
- [x] `sentielcpu_io_stats.h` rastgele veri -> gercek `/proc/diskstats` okuma
- [x] `Makefile` include path, pthread, kaynak referanslari duzeltildi
- [x] `CMakeLists.txt` include directories, pthread, kaynak referanslari duzeltildi
- [x] `setup.py`, `setup.cfg`, `pyproject.toml` entry_points tire -> alt cizgi

---

## FAZ 1: STABILIZASYON VE TEST ALTYAPISI (1-2 Hafta) - [TAMAMLANDI]

### 1.1 Eski Dosyalarin Temizligi
- [x] Eski `cbinder-gbfs/` dizinini sil (yeni `cbinder_gbfs/` aktif)
- [x] Eski `cbinder-gbfs/` referanslarinin hicbir yerde kalmadigini dogrula
- [x] `.gitignore` dosyasi olustur (bin/, *.o, *.pyc, __pycache__, *.pt, .eggs/, dist/)

### 1.2 Konfigurasyon Dizini Olusturma
- [x] Ilk calistirmada `/var/AI-stump/` dizin yapisini otomatik olusturan init script yaz
- [x] Varsayilan `AI-runtime.yml` sablonu olustur
- [x] Varsayilan `GPU-runtime.yml` sablonu olustur
- [x] Varsayilan `services/` dizini ve ornek `.svc.yml` dosyasi olustur

### 1.3 Test Altyapisi
- [x] Python testleri: `pytest` ile `tests/` dizini olustur
- [x] C testleri: `tests/c/` dizini, basit assert makrolari
- [x] CI/CD: GitHub Actions workflow dosyasi (`.github/workflows/ci.yml`)
- [x] Linting: `flake8` + `black` (Python), `clang-format` (C/C++)
- [ ] Test coverage hedefi: %60+ (testler genisletilecek)

### 1.4 Dokumantasyon Temeli
- [x] Her module `README.md` ekle
- [x] `CONTRIBUTING.md` olustur
- [x] `CHANGELOG.md` olustur

---

## FAZ 2: KERNEL MODULU YENIDEN YAZIMI (3-4 Hafta) - [TAMAMLANDI]

### 2.1 Eski Dosyalar (include-old/ altinda arsivlendi)
Asagidaki dosyalar derlenemiyordu ve sifirdan yazildi:
- `AI-LFS.hpp` -> `ai_common.h` + `ai_ioctl.h` ile degistirildi
- `aistdio.hpp` -> Kaldirildi (standart Linux API kullanildi)
- `aistdterm.h` -> Kaldirildi (POSIX terminal API kullanildi)
- `permissioner.h` -> `ai_permissions.h` ile degistirildi (0777 kaldirildi)

### 2.2 Yeni Mimari
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
  ├── include-old/             # Eski headerlar (arsiv)
  └── dkms.conf               # DKMS otomatik yukleme
```

### 2.3 Tamamlanan Gorevler
- [x] `AI-LFS.hpp` sil, `ai_common.h` + `ai_ioctl.h` ile degistir
- [x] `aistdio.hpp` sil, standart POSIX API kullan
- [x] `aistdterm.h` sil, standart POSIX terminal API kullan
- [x] Gercek kernel modulu (`kmod/ai_core.c`) yaz
- [x] `procfs` arayuzu: `/proc/ai_status`, `/proc/ai_config`
- [x] `sysfs` arayuzu: `/sys/ai/state`, `/sys/ai/governor`, `/sys/ai/version`
- [x] `ioctl` tabanli cihaz iletisimi (`/dev/ai_ctl`)
- [x] Izin sistemi: Linux grup tabanli (ai-admin, ai-user)
- [x] Kernel modulu DKMS paketleme (`dkms.conf`)
- [x] `permissioner.h` yeniden tasarlandi (ai_permissions.h, 0777 kaldirildi)
- [x] `grant_permission_revoke.c` yeniden yazildi (ai_permissions.c, gercek grup kontrol)
- [x] `kernel-start.c` yeniden yazildi (ai_ctl.c, gercek ioctl istemcisi)
- [x] Userspace araclari: `ai_ctl`, `ai_status`, `ai_permissions`
- [x] Makefile ve CMakeLists.txt guncellendi

### 2.4 Kalan (Linux ortaminda test gerekli)
- [ ] Linux VM'de kernel modulu derleme ve test
- [ ] `insmod`/`rmmod` ile yukleme/kaldirma testi
- [ ] ioctl komutlarinin uctan uca testi
- [ ] Eski dosyalarin tamamen silinmesi (include-old/, kernel-start.c, grant_permission_revoke.c)

---

## FAZ 3: GPU VE TPU DESTEGI (3-4 Hafta)

### 3.1 GPU Modulu Gelistirme
- [ ] NVIDIA destegi: `libnvml` (NVML C API) entegrasyonu
- [ ] Multi-GPU tespiti ve yonetimi
- [ ] GPU sicaklik/guc izleme (tum vendorlar icin)
- [ ] GPU frekans/guc profili yonetimi
- [ ] `libdrm` uzerinden dogrudan GPU erisimi
- [ ] Vulkan/OpenCL tabanli GPU izleme alternatifi
- [ ] GPU buffer unit'e gercek metrik yazma

### 3.2 TPU Modulu (Sifirdan)
Mevcut `PCIO-TPU-segoffline/` ve `PCIO-TPU-segonline/` tamamen bozuk.

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

## FAZ 4: AI MODEL PIPELINE (2-3 Hafta)

### 4.1 Veri Toplama
- [ ] Otomatik veri toplama daemon (ilk kurulumda 24 saat)
- [ ] Sistem metrikleri -> CSV/Parquet formati
- [ ] Veri temizleme ve normalizasyon pipeline

### 4.2 Model Gelistirme
- [ ] LSTM -> Transformer gecisi (daha iyi zaman serisi tahmini)
- [ ] Anomali tespiti modeli ekleme (Isolation Forest veya Autoencoder)
- [ ] Model versiyonlama sistemi (model_v1.pt, model_v2.pt, ...)
- [ ] Otomatik model yeniden egitim (cron/systemd timer)
- [ ] Model rollback mekanizmasi

### 4.3 Inference Motoru
- [ ] ONNX Runtime entegrasyonu (torch yerine daha hafif)
- [ ] Batch prediction destegi
- [ ] Model performans metrikleri (latency, accuracy)

### 4.4 Gizlilik
- [ ] Federated learning altyapisi (kullanici verisi cihazda kalir)
- [ ] Diferansiyel gizlilik (differential privacy) katmani

---

## FAZ 5: MASAUSTU ENTEGRASYONU (2-3 Hafta)

### 5.1 Mevcut KDE Plasma Destegi Iyilestirme
- [ ] Duplikat dosyalar temizlendi [TAMAMLANDI]
- [ ] TensorFlow modeli icin egitim verisi pipeline
- [ ] `auto_prop` icin Polkit entegrasyonu (sudo yerine)
- [ ] Plasma System Tray widget

### 5.2 Yeni DE Destekleri
- [ ] GNOME Shell extension
- [ ] XFCE panel plugin
- [ ] Hyprland/Sway (Wayland) destegi
- [ ] DE-agnostik D-Bus API tasarimi

### 5.3 Kullanici Arayuzleri
- [ ] Web dashboard (FastAPI + htmx/React)
- [ ] CLI interaktif arayuz (Rich veya Textual)
- [ ] System tray ikonu ve bildirim merkezi
- [ ] Desktop notification iyilestirme (notify-send -> D-Bus native)

---

## FAZ 6: KALITE VE DAGITIM (2-3 Hafta)

### 6.1 Kod Kalitesi
- [ ] Unit test coverage %80+
- [ ] Integration testleri (VM icerisinde)
- [ ] Automated linting (pre-commit hooks)
- [ ] Code review sureci dokumantasyonu
- [ ] Security audit (bandit, cppcheck)

### 6.2 Paketleme
- [ ] AUR paketi guncelleme (mevcut `plasma-system-ai`)
- [ ] DEB paketi (Debian/Ubuntu)
- [ ] RPM paketi (Fedora/RHEL)
- [ ] Flatpak (DE-AI icin)
- [ ] Docker konteyneri (test ortami)

### 6.3 Surum Yonetimi
- [ ] Semantic versiyonlama (SemVer)
- [ ] Git tagging stratejisi
- [ ] Release notes otomasyonu
- [ ] GitHub Releases entegrasyonu

### 6.4 Dokumantasyon
- [ ] API dokumantasyonu (Sphinx veya MkDocs)
- [ ] Kullanici kilavuzu
- [ ] Gelistirici kilavuzu
- [ ] Mimari karar kayitlari (ADR)

---

## Hedef Proje Mimarisi (v1.0.0)

```
Linux-AI/
├── kernel/                    # Kernel modulu (.ko)
│   ├── ai_core.c             # Ana kernel modulu
│   ├── ai_procfs.c           # /proc arayuzu
│   ├── ai_sysfs.c            # /sys arayuzu
│   ├── ai_permissions.c      # Izin yonetimi
│   └── Kbuild
├── daemon/                    # Sistem daemon'lari (C/C++)
│   ├── cpu/                   # CPU izleme & yonetim
│   ├── gpu/                   # GPU izleme & yonetim
│   └── tpu/                   # TPU/accelerator yonetimi
├── ai_engine/                 # AI motor (Python)
│   ├── models/                # Egitilmis modeller
│   ├── training/              # Egitim pipeline'lari
│   ├── inference/             # Gercek zamanli cikarim
│   └── data/                  # Veri toplama & isleme
├── desktop/                   # Masaustu entegrasyonu
│   ├── plasma/                # KDE Plasma
│   ├── gnome/                 # GNOME Shell
│   └── common/                # Ortak D-Bus API
├── cli/                       # Komut satiri araclari
├── tests/                     # Test altyapisi
│   ├── python/
│   ├── c/
│   └── integration/
├── docs/                      # Dokumantasyon
└── packaging/                 # Paketleme (AUR, DEB, RPM)
```

---

## Modul Detay Analizi

### proc-CPUIO (CPU I/O Yonetimi)
- **Durum:** Fonksiyonel, iyilestirme gerekli
- **Dosyalar:** `proc-CPUIO.c`, `cpu-buffer-unit.h`, `cpufreg-inline.h`, `cpu-sensivity-frogline.h`, `cpu_metrics_collector.h`, `sentielcpu_io_stats.h`
- **Sorunlar:** Implementasyon .h dosyalarinda (tasinmali), ARM CPU destegi yok, hard-coded buffer boyutlari
- **Iyilestirme:** .h -> .c ayirimi, ARM destegi, yapilandirma dosyasindan esik degerleri

### proc-GPUIO (GPU I/O Yonetimi)
- **Durum:** Kismi (NVIDIA devre disi)
- **Dosyalar:** `proc-GPUIO.cpp`, `gpu-buffer-unit.hpp`, `gpu_model_runner.hpp`
- **Sorunlar:** NVIDIA destegi yok, multi-GPU yok, Intel icin intel_gpu_top bagimliligi
- **Iyilestirme:** libnvml, libdrm, multi-GPU, sicaklik/guc izleme

### nproc-kernel (Kernel & Izinler)
- **Durum:** KRITIK - Derlenemiyor
- **Dosyalar:** `kernel-start.c`, `grant_permission_revoke.c`, `include/` (4 header)
- **Sorunlar:** 3 header dosyasi tanimsiz semboller, /dev/AI-lfs yok, 0777 guvenlik riski
- **Iyilestirme:** Tamamen sifirdan yazilmali

### PCIO-TPU (TPU Segmentasyon)
- **Durum:** KRITIK - Tamamen bozuk
- **Sorunlar:** Tum fonksiyonlar tanimsiz, gecersiz preprocessor, pseudo-kod
- **Iyilestirme:** Sifirdan tasarlanmali

### cbinder_gbfs (Python AI Araclari)
- **Durum:** Fonksiyonel (P0 duzeltmeleri tamamlandi)
- **Dosyalar:** 9 Python scripti + __init__.py
- **Yapilan:** eval() guvenligi, dosya adlari, main() fonksiyonu
- **Kalan:** Logging framework, type hints, model egitim otomasyonu

### Plasma-system-AI (Masaustu AI)
- **Durum:** Fonksiyonel (P0 duzeltmeleri tamamlandi)
- **Dosyalar:** `plasma_start.py`, `main_fregio.py`, `writereadout_tens.py`, `writereadout_tens_cli.py`
- **Yapilan:** Duplikat temizlik, dosya adlari, subprocess referanslari
- **Kalan:** TF model egitimi, Polkit, multi-DE destegi

---

## Bagimliliklari

### Sistem Bagimliliklari
- gcc/g++ >= 4.8
- make >= 3.81
- cmake >= 3.10
- linux-headers >= 4.15
- libc6, libc6-dev, libstdc++-dev
- procps
- Python >= 3.8

### Python Paket Bagimliliklari
- pyttsx3 (text-to-speech)
- psutil (sistem izleme)
- PyYAML (konfigurasyon)
- watchdog (dosya izleme)
- matplotlib, seaborn (gorselleotirme)
- numpy (sayisal hesaplama)
- torch (derin ogrenme - cbinder)
- scikit-learn (ML on isleme)
- pandas (veri analizi)
- tensorflow (Keras - Plasma AI)

---

## Notlar

- Proje yedegi: `D:/Linux-AI-backup/` (2026-02-28)
- Eski `cbinder-gbfs/` dizini temizlendi, sadece `cbinder_gbfs/` aktif
- FAZ 0 ve FAZ 1 tamamlandi, FAZ 2 (kernel yeniden yazim) sirada
- Kernel modulu gelistirmesi icin Linux VM oneriliyor
- NVIDIA GPU destegi icin NVML SDK gerekli

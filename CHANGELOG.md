# Changelog

Tum onemli degisiklikler bu dosyada belgelenir.
Format [Keep a Changelog](https://keepachangelog.com/) standardina uygundur.

## [0.3.1] - 2026-03-02

### Temizlik
- Eski dosyalar silindi: `grant_permission_revoke.c`, `kernel-start.c`
- `include-old/` dizini tamamen kaldirildi (4 eski header arsivi)
- TPU bozuk placeholder dosyalari temizlendi (`a` bos dosyalari, pseudo-kod `tpu-track-simulation.c`)
- `nproc-kernel/README.md` guncellendi (eski dosya referanslari kaldirildi)

### Duzeltilen
- `ai_agent.py`: `global OLLAMA_MODEL` bildirimi fonksiyon basina tasindi (Python 3.13+ SyntaxError)
- `pyproject.toml`: `[tool.setuptools.packages.find] where = ["proc-utils-AI"]` eklendi (package discovery)
- `test_train_ai_model.py`: `IOModel` import hatasi duzeltildi (sinif fonksiyon icinde tanimli)

### Test Altyapisi
- Yeni test dosyalari: `test_ai_agent.py` (13 test), `test_ai_logs.py` (14 test), `test_ai_help.py` (13 test), `test_ai_backup.py` (12 test), `test_ai_kernel_bridge.py` (13 test, Linux-only)
- Toplam: 96 test (96 passed, 2 skipped) - onceki: 31 test
- Windows platformunda Linux-only testler icin `pytest.skip(allow_module_level=True)` eklendi

### Dokumantasyon
- `ROADMAP.md` tamamen yeniden yazildi (guncel proje durumu, FAZ 2.5 eklendi)
- TPU modulleri icin `README.md` dosyalari eklendi (PCIO-TPU-segoffline, PCIO-TPU-segonline)

---

## [0.3.0] - 2026-02-28

### Eklenen (Sikistirma ve Performans Optimizasyonu)
- `compressed_buffer.h` - Bit-packed buffer (144 → 16 byte/entry, 9x sikistirma)
- `compressed_log.py` - Delta encoding + gzip log writer (10-20x sikistirma)
- `quantize_model.py` - Model quantization araci (Float32 → Int8 TFLite, 4x kucuk)
- Compact binary output modu (`--compact` flag, 18x kucuk CPU metrikleri)
- `gpu_compact_t` struct - GPU metrikleri icin 12 byte binary format (16x sikistirma)
- TFLite quantized model backend (ai_lfs.py - en hizli inference)

### Degistirilen (Dusuk Donanim Optimizasyonu - i7-M640 / GT 330M)
- `AI-runtime.yml` - buffer_size:32, max_cores:4, poll 3s, RAM alert %85
- `GPU-runtime.yml` - nvml:false, legacy_mode:true, poll 5s, vram_total:973MB
- `cpu-buffer-unit.h` - MAX_ENTRIES 512→64, buffer_max 64→32
- `cpufreg-inline.h` - MAX_CPUS 128→8, auto-detect CPU count
- `cpu-sensivity-frogline.h` - CHECK_INTERVAL 2s→3s, system()→fopen() guvenlik
- `proc-CPUIO.c` - Non-blocking modular, cbuffer subcommand eklendi
- `ai_lfs.py` - 4-tier backend (tflite→sklearn→torch→rules), compressed log
- `ai_cpufregd.py` - watchdog→stat() (bagimlilk kaldirildi), bellek limiti
- `ai_affinity.py` - os.system()→subprocess (injection fix), poll 5s→10s
- `writereadout_tens.py` - tensorflow→tflite-runtime (1.5GB→20MB RAM)
- `writereadout_tens_cli.py` - Yeni modular CLI
- `pyproject.toml` - v0.3.0, quantize script eklendi

### Guvenlik
- `ai_affinity.py`: `os.system(f"renice ...")` → `subprocess.run()` (injection fix)
- `cpu-sensivity-frogline.h`: `system("cat ...")` → `fopen()/fgets()` (injection fix)
- `writereadout_tens.py`: Module-level code temizlendi, CRITICAL_PROCESSES frozenset

### Performans Metrikleri
- Buffer bellek: 18 KB → 2 KB (9x azalma)
- Log dosyasi: 10-20x kucuk (delta + gzip)
- Model dosyasi: 4x kucuk (Int8 quantization)
- AI inference: 2-3x hizli (TFLite runtime)
- RAM kullanimi: ~1.5 GB → ~200 MB (TensorFlow → TFLite)
- CPU polling: %30-40 daha az (artirilmis intervaller)

---

## [0.2.0] - 2026-02-28

### Eklenen (FAZ 2 - Kernel Modulu Yeniden Yazimi)
- `nproc-kernel/include/ai_common.h` - Ortak tanimlar (kernel + userspace)
- `nproc-kernel/include/ai_ioctl.h` - ioctl komut tanimlari (12 komut)
- `nproc-kernel/include/ai_permissions.h` - Grup tabanli izin API
- `nproc-kernel/kmod/ai_core.c` - Ana kernel modulu (cdev, ioctl handler)
- `nproc-kernel/kmod/ai_procfs.c` - /proc/ai_status ve /proc/ai_config
- `nproc-kernel/kmod/ai_sysfs.c` - /sys/ai/* sysfs arayuzu
- `nproc-kernel/kmod/Kbuild` - Kernel build yapilandirmasi
- `nproc-kernel/kmod/Makefile` - DKMS uyumlu kernel build
- `nproc-kernel/dkms.conf` - DKMS otomatik yukleme yapilandirmasi
- `nproc-kernel/userspace/ai_ctl.c` - ioctl tabanli kontrol araci
- `nproc-kernel/userspace/ai_status.c` - Sistem durumu sorgulama (JSON destekli)
- `nproc-kernel/userspace/ai_permissions.c` - Izin yonetimi araci
- `nproc-kernel/userspace/Makefile` - Userspace build

### Degistirilen
- `Makefile` - Yeni userspace araclari eklendi, eski kernel_mod kaldirildi
- `CMakeLists.txt` - ai_ctl, ai_status, ai_permissions hedefleri eklendi

### Guvenlik
- `permissioner.h` (0777 izin) -> `ai_permissions.h` (grup tabanli, 0660)
- `system("mount ...")` komut enjeksiyonu kaldirildi
- `system(makeing_and_compiling)` runtime derleme kaldirildi
- `eval()` benzeri tehlikeli kaliplar tamamen temizlendi
- Tum izinler Linux grup sistemi uzerinden (ai-admin, ai-user)

### Arsivlenen (include-old/)
- `AI-LFS.hpp` - Tanimsiz semboller, derlenmiyordu
- `aistdio.hpp` - Tip/fonksiyon cakilmalari
- `aistdterm.h` - Runtime system() cagirilari, guvenlik riski
- `permissioner.h` - 0777 izinler, komut enjeksiyonu

---

## [0.1.0] - 2026-02-28

### Eklenen
- `.gitignore` dosyasi (build, Python, AI model, IDE, OS dosyalari)
- `scripts/init_config.sh` - Konfigurasyon dizini otomatik olusturma
- `scripts/defaults/AI-runtime.yml` - Varsayilan AI runtime yapilandirmasi
- `scripts/defaults/GPU-runtime.yml` - Varsayilan GPU runtime yapilandirmasi
- `scripts/defaults/example.svc.yml` - Ornek servis profili sablonu
- `ROADMAP.md` - Detayli gelistirme yol haritasi
- `CONTRIBUTING.md` - Katki kilavuzu
- `CHANGELOG.md` - Degisiklik kaydi
- `tests/` dizini - Python (pytest) ve C test altyapisi
- `.github/workflows/ci.yml` - GitHub Actions CI/CD pipeline
- `.flake8` ve `.clang-format` - Lint/format yapilandirmalari
- `pytest.ini` - Pytest yapilandirmasi

### Duzeltilen
- `setup.py` duplikat import ve duplikat `setup()` cagrisi
- Lisans tutarsizligi giderildi (MIT -> GPL-2.0-only)
- Yazar bilgisi tum dosyalarda tutarli hale getirildi
- `requirements.txt` ile `pyproject.toml` senkronize edildi
- `cbinder-gbfs/` -> `cbinder_gbfs/` (Python import uyumlulugu)
- Tum tireli Python dosya adlari alt cizgiye donusturuldu
- `cbinder_gbfs/__init__.py` eklendi
- `ai_analyzer.py`: `eval()` -> `json.loads()` guvenlik duzeltmesi
- `ai_analyzer.py`: Bare `except` -> spesifik exception handling
- `ai_analyzer.py`: `main()` fonksiyonu eklendi (entry_point destegi)
- `plasma_start.py`: subprocess referanslari guncellendi
- `sentielcpu_io_stats.h`: Rastgele veri -> gercek `/proc/diskstats` okuma
- `Makefile`: include path, pthread, kaynak referanslari duzeltildi
- `CMakeLists.txt`: include directories, pthread, kaynak referanslari duzeltildi
- `setup.py`, `setup.cfg`, `pyproject.toml`: entry_points tire -> alt cizgi

### Guvenlik
- `ai_analyzer.py`: `eval()` kullanimi kaldirildi, `json.loads()` ile degistirildi
- Exception handling iyilestirildi (bare except kaldirildi)

## [0.0.1] - 2026-02-04

### Eklenen
- Ilk proje yapisi
- proc-CPUIO: CPU I/O izleme ve yonetim modulu
- proc-GPUIO: GPU I/O izleme modulu (Intel/AMD)
- nproc-kernel: Kernel modulu iskeleti
- cbinder_gbfs: Python AI araclari (9 modul)
- DE-AI/Plasma-system-AI: KDE Plasma masaustu entegrasyonu
- PCIO-TPU: TPU segmentasyon modulu (prototip)
- Makemanifest: Python tabanli build araci
- AUR paketi destegi (plasma-system-ai)

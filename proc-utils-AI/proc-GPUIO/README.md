# proc-GPUIO - GPU I/O Management Module

C++ tabanli GPU I/O izleme modulu. AMD, Intel ve NVIDIA GPU'lar icin sysfs tabanli destek.

## Dosyalar

| Dosya | Aciklama |
|-------|----------|
| `proc-GPUIO.cpp` | Ana giris noktasi |
| `gpu-buffer-unit.hpp` | GPU metrik buffer yapisi |
| `gpu_model_runner.hpp` | GPU vendor algilama ve metrik okuma |
| `gpu_sysfs_monitor.hpp` | Saf sysfs GPU izleme (popen/shell yok) |

## Mimari

### Vendor Algilama
- `/sys/class/drm/cardN/device/vendor` uzerinden PCI vendor ID okuma
- 0x1002 = AMD, 0x8086 = Intel, 0x10de = NVIDIA
- Shell komutu kullanilmaz (`lspci` bagimliligi kaldirildi)

### Metrik Kaynaklari

| Vendor | Kaynak | Metrikler |
|--------|--------|-----------|
| AMD | sysfs | gpu_busy_percent, vram_used/total, temp, power, freq |
| Intel | sysfs | gt_cur_freq_mhz, gt_max_freq_mhz, temp |
| NVIDIA | sysfs + nvidia-smi | temp (sysfs), util/vram/power (nvidia-smi) |

### Binary Format
- `gpu_compact_t`: 12 byte packed struct (16x JSON sikistrma)
- vendor:2, temp:8, util:7, vram:32, freq:12, power:10, flags:5 bit

## Derleme

```bash
cd proc-utils-AI
make all    # veya cmake
```

## Notlar

- NVIDIA GT 330M (Fermi): NVML desteklenmiyor, nvidia-smi CLI kullanilir
- Tum sysfs okumalari fopen/fgets ile yapilir (guvenlik)
- Multi-GPU: card0-card7 taranir, ayrik GPU (AMD/NVIDIA) tercih edilir

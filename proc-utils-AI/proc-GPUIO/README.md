# proc-GPUIO - GPU I/O Management Module

C++ tabanli GPU I/O izleme modulu. Intel ve AMD GPU'lar icin temel destek saglar.

## Dosyalar

| Dosya | Aciklama |
|-------|----------|
| `proc-GPUIO.cpp` | Ana giris noktasi |
| `gpu-buffer-unit.hpp` | GPU metrik buffer yapisi |
| `gpu_model_runner.hpp` | GPU uzerinde model calistirma |

## Durum

- Intel GPU: `intel_gpu_top` uzerinden temel destek
- AMD GPU: sysfs uzerinden temel destek
- NVIDIA: Desteklenmiyor (libnvml entegrasyonu planlanmakta)

## Planlanan Iyilestirmeler

- NVIDIA NVML entegrasyonu
- Multi-GPU yonetimi
- libdrm uzerinden dogrudan GPU erisimi
- Sicaklik/guc izleme

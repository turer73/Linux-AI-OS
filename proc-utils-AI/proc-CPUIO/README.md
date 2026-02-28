# proc-CPUIO - CPU I/O Management Module

C tabanli CPU I/O izleme ve yonetim modulu. `/proc` dosya sisteminden CPU metrikleri okur ve buffer yapisinda depolar.

## Dosyalar

| Dosya | Aciklama |
|-------|----------|
| `proc-CPUIO.c` | Ana giris noktasi |
| `cpu-buffer-unit.h` | CPU metrik buffer yapisi |
| `cpufreg-inline.h` | CPU frekans okuma (inline) |
| `cpu-sensivity-frogline.h` | CPU hassasiyet esik degerleri |
| `cpu_metrics_collector.h` | Metrik toplama fonksiyonlari |
| `sentielcpu_io_stats.h` | Disk I/O istatistik okuma (/proc/diskstats) |

## Derleme

```bash
gcc -o proc-cpuio proc-CPUIO.c -Iinclude -lpthread -Wall -Wextra
```

## Bilinen Sorunlar

- Implementasyon .h dosyalarinda (ayrilmali)
- ARM CPU destegi yok
- Hard-coded buffer boyutlari

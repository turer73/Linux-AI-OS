# PCIO-TPU-segoffline - TPU Offline Processing

> **Durum:** Planlanmis (FAZ 3) - Henuz gelistirilmedi

## Amac
TPU cihazlarinda offline model donusum ve optimizasyon.

## Planlanan Ozellikler
- PCIe TPU cihaz kesfetme (`lspci` + sysfs)
- ONNX -> TPU format model donusum
- Model optimizasyon pipeline
- Google Edge TPU SDK entegrasyonu (opsiyonel)

## Gereksinimler
- Linux kernel >= 4.15
- PCIe TPU cihazi (Google Coral, vb.)
- Edge TPU runtime (opsiyonel)

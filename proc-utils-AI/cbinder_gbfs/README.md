# cbinder_gbfs - AI Binding & Utility Tools

Python tabanli AI araclari: CPU affinity yonetimi, frekans kontrolu, ML analizi, TTS ve gorselleotirme.

## Moduller

| Dosya | Aciklama |
|-------|----------|
| `ai_analyzer.py` | Servis profillerine gore AI affinity onerileri |
| `ai_affinity.py` | Gercek zamanli CPU affinity ve nice deger uygulamasi |
| `ai_cpufregd.py` | CPU frekans yonetimi daemon |
| `ai_greeting.py` | Sistem baslatma selamlamasi (TTS destekli) |
| `ai_lfs.py` | AI Log File System - metrik toplama |
| `ai_voicer.py` | Text-to-speech motor yonetimi |
| `cpu_mapping_visualizer.py` | CPU cekirdek haritasi gorselleotirme |
| `simulate_io_stats.py` | I/O istatistik simulasyonu (egitim verisi) |
| `train_ai_model.py` | LSTM tabanli I/O karar modeli egitimi |

## Kullanim

```bash
# Entry points (pip install -e . sonrasi)
ai-analyzer --json
ai-affinity
ai-cpufregd
simulate-io-stats
train-ai-model
```

## Bagimliliklar

psutil, PyYAML, torch, scikit-learn, pandas, numpy, matplotlib, seaborn, pyttsx3

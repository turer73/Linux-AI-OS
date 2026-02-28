# AI Destekli Gelistirme Rehberi

## Hizli Baslangic

### 1. Kurulum (tek sefere mahsus)
```bash
chmod +x scripts/setup-ai-dev.sh
./scripts/setup-ai-dev.sh
```

Bu script otomatik olarak:
- Ollama kurar (CPU-only mod, i7-M640 icin optimize)
- Qwen2.5-Coder 3B modelini indirir (~1.8 GB)
- `linux-ai-coder` ozel profilini olusturur
- Continue.dev VS Code eklentisini kurar
- Claude Code'u kurar (npm gerekli)

### 2. Gunluk Kullanim

#### Yerel AI (Ollama) - Hizli, ucretsiz, cevrimdisi
```bash
# Terminal'den soru sor
ollama run linux-ai-coder "proc-CPUIO icin per-core temperature okuma yaz"

# Interaktif sohbet
ollama run linux-ai-coder
```

#### VS Code (Continue.dev) - Kod yazarken AI yardimi
- `Ctrl+L` - AI sohbet panelini ac
- `Ctrl+I` - Secili kodu duzenle
- Tab - Otomatik tamamlama (kod yazarken)
- `@file` - Dosya icerigini AI'ya gonder
- `@codebase` - Tum proje hakkinda soru sor

**Ozel komutlar:**
- `/optimize` - Dusuk donanim icin optimizasyon oner
- `/secure` - Guvenlik denetimi yap
- `/kernel-style` - Linux kernel kod stiline donustur

#### Claude Code - Karmasik gorevler, refactoring, analiz
```bash
# Proje klasorunde baslat
cd /path/to/Linux-AI
claude

# Tek seferlik soru
claude "ai_lfs.py'deki 4-tier backend mantigini acikla"
```

## Hibrit Strateji

| Gorev                          | Arac              | Neden                    |
|--------------------------------|--------------------|--------------------------|
| Kucuk fonksiyon yaz            | Continue (Ctrl+L)  | Hizli, yerel, gecikme yok |
| Otomatik tamamlama             | Continue (Tab)     | Anlik, akis bozmaz       |
| Buyuk refactoring              | Claude Code        | Coklu dosya, derin analiz |
| Hata ayiklama                  | Claude Code        | Baglamsal kod okuma      |
| Kernel kodu yaz                | Ollama terminal    | Ozel profil, cevrimdisi  |
| Guvenlik denetimi              | Continue /secure   | Hizli tarama             |
| Mimari karar                   | Claude Code        | Uzun baglamsal muhakeme  |
| Commit mesaji                  | Claude /commit     | Otomatik, tutarli        |

## Performans Notlari

- **RAM:** Ollama ~2-3 GB kullanir. VS Code + Continue ile toplam ~5 GB.
  Kalan ~3 GB sistem + derleme icin yeterli.
- **CPU:** Inference 4 thread kullanir. Derleme sirasinda Ollama'yi kapatabilirsiniz:
  ```bash
  systemctl stop ollama   # veya
  killall ollama
  ```
- **Disk:** Model ~1.8 GB. Toplam kurulum ~3 GB.
- **Ilk cevap:** 3-8 saniye (model yukleme). Sonraki cevaplar 1-3 sn.

## Sorun Giderme

```bash
# Ollama calisiyor mu?
ollama list

# Model var mi?
ollama list | grep linux-ai-coder

# Servis baslatma
ollama serve &

# RAM kontrol
free -h

# Model silip yeniden indirme
ollama rm linux-ai-coder
ollama pull qwen2.5-coder:3b
```

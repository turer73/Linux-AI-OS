# Plasma-system-AI - KDE Plasma Desktop Integration

KDE Plasma masaustu ortami icin AI otomasyon ve izleme modulu.

## Dosyalar

| Dosya | Aciklama |
|-------|----------|
| `plasma_start.py` | Ana baslatma scripti (systemd uyumlu) |
| `main_fregio.py` | Masaustu UI yonetimi |
| `writereadout_tens.py` | TensorFlow tabanli okuma/yazma analizi |
| `writereadout_tens_cli.py` | CLI versiyonu |

## Kurulum

```bash
# AUR uzerinden (Arch Linux)
yay -S plasma-system-ai

# Manuel
cd DE-AI/Plasma-system-AI
pip install .
```

## Systemd Servisi

```bash
sudo cp plasma-system-ai.service /etc/systemd/system/
sudo systemctl enable plasma-system-ai
sudo systemctl start plasma-system-ai
```

## Planlanan Iyilestirmeler

- TensorFlow model egitim pipeline
- Polkit entegrasyonu (sudo yerine)
- Plasma System Tray widget

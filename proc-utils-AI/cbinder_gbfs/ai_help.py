#!/usr/bin/env python3
"""
Linux-AI Yardım Sistemi (Türkçe)
=================================
Tüm komutların detaylı açıklamaları.

Kullanım:
    ai-help                  # Ana menü
    ai-help dashboard        # Dashboard detayları
    ai-help agent            # AI Agent detayları
    ai-help komutlar         # Tüm komut listesi
"""

import argparse
import sys

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.columns import Columns
    from rich import box
    from rich.markdown import Markdown
except ImportError:
    # rich yoksa düz metin fallback
    pass


console = Console() if "rich" in sys.modules else None


# ─── Yardım İçerikleri ──────────────────────────────────────────────────────

HELP_MAIN = """
[bold cyan]╔══════════════════════════════════════════════════════════════╗
║                  LINUX-AI OS v0.3.0                         ║
║              AI Destekli Sistem Yönetimi                    ║
╚══════════════════════════════════════════════════════════════╝[/bold cyan]

[bold white]TEMEL KOMUTLAR:[/bold white]

  [bold green]ai-dashboard[/bold green]          Canlı kontrol paneli (Bloomberg tarzı)
  [bold green]ai-agent[/bold green]              AI asistan ile sohbet (yerel, internetsiz)
  [bold green]ai-monitor[/bold green]            Sistem izleme ve sağlık kontrolü
  [bold green]ai-backup[/bold green]             Yedekleme işlemleri
  [bold green]ai-logs[/bold green]               Log görüntüleme ve analiz
  [bold green]ai-web-agent[/bold green]          Web servis yönetimi (Cloudflare, Coolify, Vercel)
  [bold green]ai-dev-setup[/bold green]          Geliştirici ortamı kurulumu
  [bold green]ai-help[/bold green]               Bu yardım ekranı

[bold white]DETAYLI BİLGİ İÇİN:[/bold white]

  [cyan]ai-help dashboard[/cyan]     Dashboard kullanımı
  [cyan]ai-help agent[/cyan]         AI Asistan kullanımı
  [cyan]ai-help monitor[/cyan]       Sistem izleme detayları
  [cyan]ai-help backup[/cyan]        Yedekleme detayları
  [cyan]ai-help logs[/cyan]          Log yönetimi
  [cyan]ai-help web[/cyan]           Web servis yönetimi
  [cyan]ai-help tailscale[/cyan]     VPN kullanımı
  [cyan]ai-help cloudflare[/cyan]    Güvenlik duvarı (WAF)
  [cyan]ai-help ollama[/cyan]        Yerel AI modelleri
  [cyan]ai-help kurulum[/cyan]       İlk kurulum adımları
  [cyan]ai-help komutlar[/cyan]      Tüm komutların tam listesi
  [cyan]ai-help sorun[/cyan]         Sık karşılaşılan sorunlar

[dim]Çıkış: q | Geri: ai-help[/dim]
"""

HELP_DASHBOARD = """
[bold cyan]◆ DASHBOARD - Canlı Kontrol Paneli[/bold cyan]

[bold white]Ne İşe Yarar?[/bold white]
  Terminal üzerinde Bloomberg Terminal benzeri canlı izleme ekranı.
  Masaüstü ortamına gerek yok - SSH üzerinden bile çalışır.

[bold white]Kullanım:[/bold white]

  [green]ai-dashboard[/green]              Tam ekran dashboard başlat
  [green]ai-dashboard --minimal[/green]    Hafif mod (düşük kaynak)
  [green]ai-dashboard --refresh 3[/green]  3 saniyede bir yenile (varsayılan: 5)

[bold white]Ekranda Gösterilen Paneller:[/bold white]

  [cyan]◆ CPU[/cyan]           Her çekirdek yüzdesi, frekans, sıcaklık
  [cyan]◆ Bellek[/cyan]        RAM ve Swap kullanımı, kalan alan
  [cyan]◆ Disk[/cyan]          Bölüm doluluk oranları
  [cyan]◆ Ağ[/cyan]            Gönderilen/alınan veri, bağlantı sayısı
  [cyan]◆ Servisler[/cyan]     Ollama, Tailscale, SSH... (yeşil=aktif, kırmızı=kapalı)
  [cyan]◆ AI Modeller[/cyan]   Ollama'da yüklü modeller ve boyutları
  [cyan]◆ Tailscale[/cyan]     VPN durumu, IP adresi, bağlı cihazlar
  [cyan]◆ SSL[/cyan]           Sertifika süreleri (kırmızı=acil, sarı=yakında)
  [cyan]◆ Süreçler[/cyan]      En çok CPU/RAM yiyen 8 süreç
  [cyan]◆ Loglar[/cyan]        Tüm bileşenlerden son log satırları
  [cyan]◆ Uyarılar[/cyan]      Kritik durumlar (CPU yüksek, disk dolu vb.)

[bold white]Renk Kodları:[/bold white]
  [green]█ Yeşil[/green]   = Normal (<%70)
  [yellow]█ Sarı[/yellow]    = Uyarı (%70-90)
  [red]█ Kırmızı[/red]  = Kritik (>%90)

[bold white]Kısayollar:[/bold white]
  Ctrl+C    Dashboard'dan çık

[dim]Not: Veriler her 5 saniyede yenilenir. SSL ve Tailscale her 30 saniyede.[/dim]
"""

HELP_AGENT = """
[bold cyan]◆ AI AGENT - Akıllı Asistan[/bold cyan]

[bold white]Ne İşe Yarar?[/bold white]
  Yerel AI modeli (Ollama) kullanarak sorularını cevapler.
  İnternet gerektirmez. Veriler bilgisayarından çıkmaz.

[bold white]Kullanım:[/bold white]

  [green]ai-agent[/green]                        İnteraktif mod (sohbet)
  [green]ai-agent "CPU neden yüksek?"[/green]    Tek soru sor
  [green]ai-agent --model qwen2.5:7b[/green]     Farklı model kullan

[bold white]Neler Yapabilir?[/bold white]

  [cyan]Sistem Analizi[/cyan]
    "Sistem durumu nasıl?"
    "Neden CPU yüksek?"
    "Disk alanı azalıyor, ne yapmalıyım?"

  [cyan]Kod Yazma[/cyan]
    "Python ile dosya yedekleme scripti yaz"
    "Bu hata ne anlama geliyor: [hata mesajı]"
    "Nginx config dosyasını optimize et"

  [cyan]Sistem Yönetimi[/cyan]
    "Firewall kuralı nasıl eklerim?"
    "SSH güvenliğini nasıl artırırım?"
    "Cron job nasıl oluştururum?"

[bold white]Araçları (Otomatik Kullanır):[/bold white]

  [yellow]system_info[/yellow]         Sistem bilgisi toplar
  [yellow]process_list[/yellow]        Çalışan süreçleri listeler
  [yellow]disk_usage[/yellow]          Disk kullanımını gösterir
  [yellow]network_info[/yellow]        Ağ bilgilerini getirir
  [yellow]run_command[/yellow]         Güvenli komut çalıştırır
  [yellow]read_file[/yellow]           Dosya okur
  [yellow]tailscale_status[/yellow]    VPN durumunu kontrol eder
  ... ve 20+ araç daha

[bold white]Model Seçimi:[/bold white]

  [green]qwen2.5-coder:3b[/green]   Hızlı, kod odaklı (1.8 GB RAM)
  [green]qwen2.5:7b[/green]         Daha akıllı, genel amaçlı (4.4 GB RAM)

[dim]Not: İlk soru biraz yavaş olabilir (model yükleniyor). Sonrakiler hızlıdır.[/dim]
"""

HELP_MONITOR = """
[bold cyan]◆ AI MONITOR - Sistem İzleme[/bold cyan]

[bold white]Ne İşe Yarar?[/bold white]
  Sistemi 7/24 izler. Sorun olunca Telegram/Discord'a uyarı gönderir.
  Arka planda systemd servisi olarak çalışır.

[bold white]Kullanım:[/bold white]

  [green]ai-monitor dashboard[/green]     Anlık sistem durumu göster
  [green]ai-monitor check[/green]         Hızlı sağlık kontrolü (exit code döner)
  [green]ai-monitor run[/green]           İzleme döngüsü başlat (arka plan)
  [green]ai-monitor run -i 60[/green]     60 saniye aralıkla izle

[bold white]İzlenen Metrikler:[/bold white]

  [cyan]CPU[/cyan]         Kullanım yüzdesi, sıcaklık, frekans
  [cyan]RAM[/cyan]         Kullanım, swap, boş alan
  [cyan]Disk[/cyan]        Doluluk oranı, I/O hızı
  [cyan]Ağ[/cyan]          Bağlantı sayısı, trafik
  [cyan]SSL[/cyan]         Sertifika süreleri (tüm domainler)
  [cyan]Servisler[/cyan]   Ollama, Tailscale, SSH durumları
  [cyan]Tailscale[/cyan]   VPN bağlantı durumu

[bold white]Uyarı Eşikleri:[/bold white]

  CPU > %90       → [red]Telegram/Discord uyarı[/red]
  RAM > %90       → [red]Telegram/Discord uyarı[/red]
  Disk > %85      → [yellow]Uyarı[/yellow]
  SSL < 7 gün     → [red]Kritik uyarı[/red]
  SSL < 30 gün    → [yellow]Uyarı[/yellow]
  Servis çöktü    → [red]Anında uyarı[/red]

[bold white]Servis Olarak Çalıştırma:[/bold white]

  [green]sudo systemctl start ai-monitor[/green]    Başlat
  [green]sudo systemctl enable ai-monitor[/green]   Boot'ta otomatik başlat
  [green]sudo systemctl status ai-monitor[/green]   Durumu gör

[dim]Yapılandırma: /var/AI-stump/monitor.yml[/dim]
"""

HELP_BACKUP = """
[bold cyan]◆ AI BACKUP - Yedekleme Sistemi[/bold cyan]

[bold white]Ne İşe Yarar?[/bold white]
  Config dosyalarını, Supabase veritabanını ve Coolify ayarlarını yedekler.
  Günlük otomatik yedekleme (cron) destekler.

[bold white]Kullanım:[/bold white]

  [green]ai-backup run[/green]                 Tüm kaynakları yedekle
  [green]ai-backup config[/green]              Sadece config dosyalarını yedekle
  [green]ai-backup supabase[/green]            Supabase veritabanını dışa aktar
  [green]ai-backup coolify[/green]             Coolify ayarlarını yedekle
  [green]ai-backup list[/green]                Mevcut yedekleri listele
  [green]ai-backup restore <dosya>[/green]     Yedekten geri yükle
  [green]ai-backup cron --enable[/green]       Günlük otomatik yedekleme aç
  [green]ai-backup cron --disable[/green]      Otomatik yedeklemeyi kapat

[bold white]Yedek Nereye Kaydedilir?[/bold white]

  [cyan]/var/AI-stump/backups/[/cyan]
  ├── config_20260228_143000.tar.gz
  ├── supabase_20260228_143000.json
  └── coolify_20260228_143000.json

[bold white]Saklama Süresi:[/bold white]
  7 gün (eski yedekler otomatik silinir)

[bold white]Geri Yükleme:[/bold white]

  [green]ai-backup list[/green]                           Yedekleri gör
  [green]ai-backup restore config_20260228.tar.gz[/green] Geri yükle

[dim]Yapılandırma: /var/AI-stump/backup.yml | .env (API tokenleri)[/dim]
"""

HELP_LOGS = """
[bold cyan]◆ AI LOGS - Log Yönetimi[/bold cyan]

[bold white]Ne İşe Yarar?[/bold white]
  Tüm Linux-AI bileşenlerinin loglarını tek yerden görüntüler,
  arar, filtreler ve analiz eder.

[bold white]Kullanım:[/bold white]

  [green]ai-logs view[/green]                  Son logları göster
  [green]ai-logs view -n 50[/green]            Son 50 satır
  [green]ai-logs view --source agent[/green]   Sadece agent logları
  [green]ai-logs tail[/green]                  Canlı log takibi (tail -f gibi)
  [green]ai-logs search "error"[/green]        Hata ara
  [green]ai-logs search "backup" --source monitor[/green]
  [green]ai-logs stats[/green]                 Log istatistikleri
  [green]ai-logs export[/green]                JSON formatında dışa aktar
  [green]ai-logs clean[/green]                 Eski logları temizle

[bold white]Log Kaynakları:[/bold white]

  [cyan]agent[/cyan]       AI Agent konuşma logları
  [cyan]monitor[/cyan]     Sistem izleme logları
  [cyan]backup[/cyan]      Yedekleme işlem logları
  [cyan]webops[/cyan]      Web operasyonları
  [cyan]deploy[/cyan]      CI/CD dağıtım logları

[bold white]Canlı Takip:[/bold white]

  [green]ai-logs tail[/green]         Tüm kaynaklar
  [green]ai-logs tail --source monitor[/green]  Sadece monitor

  Ctrl+C ile çık

[dim]Log dizini: /var/log/linux-ai/[/dim]
"""

HELP_WEB = """
[bold cyan]◆ AI WEB-AGENT - Web Servis Yönetimi[/bold cyan]

[bold white]Ne İşe Yarar?[/bold white]
  Cloudflare, Coolify ve Vercel servislerini komut satırından yönetir.
  Panel açmaya gerek kalmadan her şeyi terminalden yaparsın.

[bold white]CLOUDFLARE (CDN + Güvenlik):[/bold white]

  [green]ai-web-agent cloudflare dns-list[/green]         DNS kayıtlarını listele
  [green]ai-web-agent cloudflare purge-cache[/green]      Cache temizle
  [green]ai-web-agent cloudflare waf-list[/green]         Güvenlik kurallarını gör
  [green]ai-web-agent cloudflare block-ip 1.2.3.4[/green] IP engelle
  [green]ai-web-agent cloudflare block-country CN[/green]  Ülke engelle
  [green]ai-web-agent cloudflare protect-admin[/green]     Admin yollarını koru
  [green]ai-web-agent cloudflare challenge-threats[/green] Şüpheli IP'lere captcha

[bold white]COOLIFY (Uygulama Sunucu):[/bold white]

  [green]ai-web-agent coolify list[/green]        Uygulamaları listele
  [green]ai-web-agent coolify deploy[/green]      Deploy et
  [green]ai-web-agent coolify restart[/green]     Yeniden başlat
  [green]ai-web-agent coolify logs[/green]        Uygulama logları

[bold white]VERCEL (Frontend):[/bold white]

  [green]ai-web-agent vercel list[/green]         Projeleri listele
  [green]ai-web-agent vercel deploy[/green]       Deploy et
  [green]ai-web-agent vercel domains[/green]      Domain yönetimi

[bold white]TAILSCALE (VPN):[/bold white]

  [green]ai-web-agent tailscale status[/green]    Bağlantı durumu
  [green]ai-web-agent tailscale up[/green]        VPN'i aç
  [green]ai-web-agent tailscale down[/green]      VPN'i kapat
  [green]ai-web-agent tailscale ping <host>[/green]  Cihaza ping at

[dim]Yapılandırma: .env dosyasında API tokenleri gerekli[/dim]
"""

HELP_TAILSCALE = """
[bold cyan]◆ TAILSCALE - VPN (Uzaktan Erişim)[/bold cyan]

[bold white]Ne İşe Yarar?[/bold white]
  Sunucuna dünyanın her yerinden güvenli bağlantı sağlar.
  Port açmaya, IP adresi bilmeye gerek yok.

[bold white]İlk Kurulum:[/bold white]

  [green]sudo tailscale up[/green]              VPN'e bağlan (tarayıcıda onay gerekir)
  [green]tailscale ip[/green]                   Tailscale IP adresini gör

[bold white]Günlük Kullanım:[/bold white]

  [green]tailscale status[/green]               Bağlantı durumu ve cihazlar
  [green]tailscale ping <cihaz>[/green]         Cihaza ping at
  [green]tailscale netcheck[/green]             Ağ kalitesi testi

[bold white]Uzaktan Erişim:[/bold white]

  Başka bilgisayardan:
    [green]ssh aiadmin@100.64.x.x[/green]      Tailscale IP ile SSH

  Telefondan:
    1. Tailscale uygulamasını kur (iOS/Android)
    2. Aynı hesapla giriş yap
    3. Termius/JuiceSSH ile bağlan

[bold white]Port Paylaşma:[/bold white]

  [green]tailscale serve 8080[/green]           8080 portunu paylaş
  [green]tailscale serve off[/green]            Paylaşımı kapat

[bold white]Gelişmiş:[/bold white]

  [green]sudo tailscale up --ssh[/green]              Tailscale SSH aç
  [green]sudo tailscale up --exit-node[/green]        Çıkış noktası ol
  [green]sudo tailscale up --advertise-routes=10.0.0.0/24[/green]  Subnet paylaş

[dim]Ücretsiz plan: 100 cihaz, 3 kullanıcı. Kişisel kullanım için yeterli.[/dim]
"""

HELP_CLOUDFLARE = """
[bold cyan]◆ CLOUDFLARE - Güvenlik Duvarı (WAF)[/bold cyan]

[bold white]Ne İşe Yarar?[/bold white]
  Web sitelerini DDoS, bot ve saldırılardan korur.
  Ücretsiz plan ile 5 firewall kuralı oluşturabilirsin.

[bold white]Kurulum:[/bold white]

  1. cloudflare.com'da ücretsiz hesap aç
  2. Domain'ini Cloudflare DNS'e yönlendir
  3. API tokeni oluştur (Zone.Firewall Services izni)
  4. .env dosyasına ekle:
     [green]CLOUDFLARE_API_TOKEN=token_buraya[/green]
     [green]CLOUDFLARE_ZONE_ID=zone_id_buraya[/green]

[bold white]Sık Kullanılan Komutlar:[/bold white]

  [green]ai-web-agent cloudflare block-ip 1.2.3.4[/green]
    → Belirli IP adresini engelle

  [green]ai-web-agent cloudflare block-country CN[/green]
    → Tüm ülkeyi engelle (ülke kodu: CN, RU, vb.)

  [green]ai-web-agent cloudflare protect-admin[/green]
    → /admin, /wp-admin, /login yollarını koru

  [green]ai-web-agent cloudflare challenge-threats[/green]
    → Şüpheli IP'lere CAPTCHA göster

  [green]ai-web-agent cloudflare waf-list[/green]
    → Mevcut kuralları listele

  [green]ai-web-agent cloudflare waf-delete --rule-id abc123[/green]
    → Kuralı sil

[bold white]Ücretsiz Planda:[/bold white]
  ✓ DNS yönetimi
  ✓ CDN (içerik hızlandırma)
  ✓ SSL/TLS sertifikası (otomatik)
  ✓ DDoS koruması (sınırsız)
  ✓ 5 güvenlik duvarı kuralı
  ✓ Temel analitik

[dim]Daha fazla kural? Pro plan: 20$/ay → 20 kural[/dim]
"""

HELP_OLLAMA = """
[bold cyan]◆ OLLAMA - Yerel AI Modelleri[/bold cyan]

[bold white]Ne İşe Yarar?[/bold white]
  Bilgisayarında yerel olarak çalışan AI modelleri.
  İnternet gerektirmez. Veriler senden çıkmaz. Tamamen ücretsiz.

[bold white]Temel Komutlar:[/bold white]

  [green]ollama list[/green]                    Yüklü modelleri gör
  [green]ollama run qwen2.5-coder:3b[/green]   Kodlama modeli ile sohbet
  [green]ollama run qwen2.5:7b[/green]         Genel amaçlı model
  [green]ollama pull <model>[/green]            Yeni model indir
  [green]ollama rm <model>[/green]              Model sil
  [green]ollama ps[/green]                      Çalışan modelleri gör

[bold white]Mevcut Modeller:[/bold white]

  [cyan]qwen2.5-coder:3b[/cyan]    Kod yazma/düzeltme (1.8 GB, hızlı)
  [cyan]qwen2.5:7b[/cyan]          Genel amaçlı (4.4 GB, daha akıllı)

[bold white]Doğrudan Kullanım:[/bold white]

  [green]ollama run qwen2.5-coder:3b[/green]
  >>> Python ile HTTP sunucu yaz
  >>> Bu hatayı düzelt: [hata yapıştır]
  >>> Nginx config'i optimize et

[bold white]ai-agent İle Kullanım:[/bold white]

  [green]ai-agent[/green]
  → Otomatik olarak Ollama'yı kullanır
  → Sistem araçlarına da erişir (disk, CPU, süreçler)
  → Daha akıllı: önce durumu analiz eder, sonra cevaplar

[bold white]Kaynak Kullanımı:[/bold white]

  3B model: ~1.8 GB RAM, cevap süresi 5-15 sn
  7B model: ~4.4 GB RAM, cevap süresi 15-45 sn
  Boşta: ~150 MB RAM (model bellekte kalır)

[bold white]CPU-Only Ayarlar:[/bold white]

  [green]export OLLAMA_NUM_GPU=0[/green]           GPU kullanma
  [green]export OLLAMA_NUM_THREAD=4[/green]        4 thread kullan
  [green]export OLLAMA_MAX_LOADED_MODELS=1[/green] Aynı anda 1 model

[dim]Model deposu: https://ollama.com/library[/dim]
"""

HELP_KURULUM = """
[bold cyan]◆ İLK KURULUM ADIMLARI[/bold cyan]

[bold white]1. Ubuntu Server Kur (USB'den)[/bold white]
   ISO'yu USB'ye yaz → bilgisayarı USB'den başlat → kur

[bold white]2. Linux-AI Kur[/bold white]
   [green]sudo apt update && sudo apt install -y git curl
   git clone https://github.com/turer73/Linux-AI.git /opt/linux-ai
   cd /opt/linux-ai
   sudo bash scripts/full-install.sh[/green]

[bold white]3. API Anahtarlarını Ayarla[/bold white]
   [green]nano /opt/linux-ai/.env[/green]

   Ekle:
     TELEGRAM_BOT_TOKEN=...
     TELEGRAM_CHAT_ID=...
     CLOUDFLARE_API_TOKEN=...
     CLOUDFLARE_ZONE_ID=...
     SUPABASE_URL=...
     SUPABASE_KEY=...
     COOLIFY_URL=...
     COOLIFY_TOKEN=...

[bold white]4. Tailscale Bağlan[/bold white]
   [green]sudo tailscale up[/green]
   → Tarayıcıda onay ver

[bold white]5. Kontrol Et[/bold white]
   [green]ai-dashboard[/green]              Her şey yeşil mi?
   [green]ai-monitor check[/green]          Sağlık kontrolü
   [green]ai-agent "merhaba"[/green]        AI çalışıyor mu?

[bold white]6. Otomatikleri Aç[/bold white]
   [green]sudo systemctl enable ai-monitor[/green]    İzleme 7/24
   [green]ai-backup cron --enable[/green]              Günlük yedek

[bold yellow]Varsayılan Giriş:[/bold yellow]
   Kullanıcı: [bold]aiadmin[/bold]
   Şifre:     [bold]linux-ai[/bold]  (hemen değiştir: passwd)
"""

HELP_KOMUTLAR = """
[bold cyan]◆ TÜM KOMUTLAR LİSTESİ[/bold cyan]

[bold white]━━━ Kontrol Paneli ━━━[/bold white]
  [green]ai-dashboard[/green]              Canlı terminal dashboard
  [green]ai-dashboard --minimal[/green]    Hafif mod
  [green]ai-help[/green]                   Bu yardım ekranı

[bold white]━━━ AI Asistan ━━━[/bold white]
  [green]ai-agent[/green]                  İnteraktif AI sohbet
  [green]ai-agent "soru"[/green]           Tek soru sor
  [green]ollama run qwen2.5-coder:3b[/green]   Doğrudan AI sohbet

[bold white]━━━ Sistem İzleme ━━━[/bold white]
  [green]ai-monitor dashboard[/green]     Sistem durumu özeti
  [green]ai-monitor check[/green]         Hızlı sağlık kontrolü
  [green]ai-monitor run[/green]           İzleme başlat (arka plan)

[bold white]━━━ Yedekleme ━━━[/bold white]
  [green]ai-backup run[/green]            Tüm kaynakları yedekle
  [green]ai-backup list[/green]           Yedekleri listele
  [green]ai-backup restore <dosya>[/green]  Geri yükle
  [green]ai-backup cron --enable[/green]  Günlük otomatik yedek

[bold white]━━━ Log Yönetimi ━━━[/bold white]
  [green]ai-logs view[/green]             Son loglar
  [green]ai-logs tail[/green]             Canlı log takibi
  [green]ai-logs search "hata"[/green]    Log ara
  [green]ai-logs stats[/green]            İstatistikler

[bold white]━━━ Web Yönetimi ━━━[/bold white]
  [green]ai-web-agent cloudflare ...[/green]   Cloudflare yönet
  [green]ai-web-agent coolify ...[/green]      Coolify yönet
  [green]ai-web-agent vercel ...[/green]       Vercel yönet
  [green]ai-web-agent tailscale ...[/green]    Tailscale yönet

[bold white]━━━ Güvenlik (Cloudflare) ━━━[/bold white]
  [green]ai-web-agent cloudflare block-ip <IP>[/green]
  [green]ai-web-agent cloudflare block-country <KOD>[/green]
  [green]ai-web-agent cloudflare protect-admin[/green]
  [green]ai-web-agent cloudflare waf-list[/green]

[bold white]━━━ VPN (Tailscale) ━━━[/bold white]
  [green]tailscale status[/green]         Bağlantı durumu
  [green]tailscale up[/green]             VPN aç
  [green]tailscale down[/green]           VPN kapat

[bold white]━━━ Geliştirici ━━━[/bold white]
  [green]ai-dev-setup install[/green]     Dev ortamı kur
  [green]ai-dev-setup status[/green]      Dev araçları durumu
  [green]ai-dev-setup model-pull[/green]  AI modeli indir

[bold white]━━━ Sistem ━━━[/bold white]
  [green]ai-cpufregd[/green]              CPU frekans yöneticisi
  [green]ai-webops[/green]                Web operasyonları
  [green]ai-analyzer[/green]              Süreç analizi
  [green]ai-affinity[/green]              CPU çekirdek ataması
"""

HELP_SORUN = """
[bold cyan]◆ SIK KARŞILAŞILAN SORUNLAR[/bold cyan]

[bold red]S: Ollama çalışmıyor / "connection refused"[/bold red]
[white]C: Servisi başlat:[/white]
   [green]sudo systemctl start ollama[/green]
   veya: [green]ollama serve &[/green]

[bold red]S: AI model çok yavaş[/bold red]
[white]C: 3B modeli kullan (daha hızlı):[/white]
   [green]ai-agent --model qwen2.5-coder:3b[/green]

[bold red]S: RAM yetersiz / sistem donuyor[/bold red]
[white]C: 7B modeli kaldır, sadece 3B kullan:[/white]
   [green]ollama rm qwen2.5:7b[/green]

[bold red]S: Telegram/Discord uyarı gelmiyor[/bold red]
[white]C: .env dosyasını kontrol et:[/white]
   [green]nano /opt/linux-ai/.env[/green]
   TELEGRAM_BOT_TOKEN ve CHAT_ID doğru mu?

[bold red]S: SSL kontrolü çalışmıyor[/bold red]
[white]C: Domain listesi yapılandır:[/white]
   [green]nano /var/AI-stump/monitor.yml[/green]
   ssl_domains: altına domainlerini ekle

[bold red]S: Tailscale bağlanamıyor[/bold red]
[white]C: Servisi başlat ve giriş yap:[/white]
   [green]sudo systemctl start tailscaled[/green]
   [green]sudo tailscale up[/green]

[bold red]S: Cloudflare API hatası[/bold red]
[white]C: Token izinlerini kontrol et:[/white]
   cloudflare.com → API Tokens → Zone.Firewall Services izni var mı?

[bold red]S: Dashboard açılmıyor / "rich not found"[/bold red]
[white]C: Kütüphaneyi kur:[/white]
   [green]pip install rich[/green]

[bold red]S: ai-backup "permission denied"[/bold red]
[white]C: Root olarak çalıştır:[/white]
   [green]sudo ai-backup run[/green]

[bold red]S: Disk dolu uyarısı[/bold red]
[white]C: Eski logları ve yedekleri temizle:[/white]
   [green]ai-logs clean[/green]
   [green]ai-backup list[/green]  → eski yedekleri kontrol et

[bold yellow]Hâlâ çözülmediyse:[/bold yellow]
  [green]ai-logs search "error"[/green]        Hata loglarını incele
  [green]ai-monitor check[/green]              Genel durum kontrolü
  [green]ai-agent "şu hata ne: ..."[/green]   AI'a sor
"""

# ─── Konu Haritası ───────────────────────────────────────────────────────────

TOPICS = {
    "dashboard": HELP_DASHBOARD,
    "panel": HELP_DASHBOARD,
    "ekran": HELP_DASHBOARD,
    "agent": HELP_AGENT,
    "asistan": HELP_AGENT,
    "ai": HELP_AGENT,
    "monitor": HELP_MONITOR,
    "izleme": HELP_MONITOR,
    "backup": HELP_BACKUP,
    "yedek": HELP_BACKUP,
    "yedekleme": HELP_BACKUP,
    "logs": HELP_LOGS,
    "log": HELP_LOGS,
    "web": HELP_WEB,
    "webops": HELP_WEB,
    "tailscale": HELP_TAILSCALE,
    "vpn": HELP_TAILSCALE,
    "cloudflare": HELP_CLOUDFLARE,
    "waf": HELP_CLOUDFLARE,
    "guvenlik": HELP_CLOUDFLARE,
    "güvenlik": HELP_CLOUDFLARE,
    "ollama": HELP_OLLAMA,
    "model": HELP_OLLAMA,
    "kurulum": HELP_KURULUM,
    "install": HELP_KURULUM,
    "setup": HELP_KURULUM,
    "komutlar": HELP_KOMUTLAR,
    "komut": HELP_KOMUTLAR,
    "liste": HELP_KOMUTLAR,
    "hepsi": HELP_KOMUTLAR,
    "sorun": HELP_SORUN,
    "hata": HELP_SORUN,
    "problem": HELP_SORUN,
    "fix": HELP_SORUN,
}


# ─── Düz Metin Fallback ─────────────────────────────────────────────────────

def strip_rich_tags(text):
    """Rich etiketlerini kaldır (rich yoksa)."""
    import re
    return re.sub(r'\[/?[^\]]+\]', '', text)


# ─── Ana ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Linux-AI Yardım Sistemi (Türkçe)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "konu", nargs="?", default=None,
        help="Yardım konusu (dashboard, agent, monitor, backup, logs, web, "
             "tailscale, cloudflare, ollama, kurulum, komutlar, sorun)"
    )
    args = parser.parse_args()

    # Konu belirle
    topic = args.konu
    if topic:
        topic = topic.lower().strip()
        content = TOPICS.get(topic)
        if not content:
            # Yakın eşleşme dene
            for key in TOPICS:
                if topic in key or key in topic:
                    content = TOPICS[key]
                    break
        if not content:
            content = (
                f"\n[red]'{topic}' konusu bulunamadı.[/red]\n\n"
                "[white]Mevcut konular:[/white] "
                "dashboard, agent, monitor, backup, logs, web, "
                "tailscale, cloudflare, ollama, kurulum, komutlar, sorun\n"
            )
    else:
        content = HELP_MAIN

    # Göster
    if console:
        console.print(content)
    else:
        print(strip_rich_tags(content))


if __name__ == "__main__":
    main()

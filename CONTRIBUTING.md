# Contributing to Linux-AI

Linux-AI projesine katkida bulundugunuz icin tesekkurler!

## Gelistirme Ortami Kurulumu

```bash
git clone https://github.com/Zamanhuseyinli/Linux-AI
cd Linux-AI
python -m venv venv
source venv/bin/activate  # Linux/macOS
pip install -e .
pip install pytest flake8 black
```

## Kod Standartlari

### Python
- **Formatter:** `black` (satir uzunlugu: 120)
- **Linter:** `flake8` (satir uzunlugu: 120)
- Python >= 3.8 uyumlulugu saglanmali

```bash
black --line-length=120 proc-utils-AI/cbinder_gbfs/
flake8 proc-utils-AI/cbinder_gbfs/ --max-line-length=120
```

### C/C++
- **Formatter:** `clang-format` (LLVM tabani, indent: 4)
- gcc >= 4.8 uyumlulugu
- `-Wall -Wextra` ile temiz derleme

```bash
clang-format -i proc-utils-AI/proc-CPUIO/*.c
```

## Test Calistirma

### Python testleri
```bash
pytest tests/python/ -v
```

### C testleri
```bash
gcc -o tests/c/test_cpu_buffer tests/c/test_cpu_buffer.c -Itests/c/ -Wall -Wextra
./tests/c/test_cpu_buffer
```

## Pull Request Sureci

1. Yeni bir branch olusturun: `git checkout -b feature/ozellik-adi`
2. Degisikliklerinizi yapin ve test edin
3. Commit mesajlari aciklayici olmali:
   - `feat: CPU sicaklik izleme eklendi`
   - `fix: ai_analyzer YAML parse hatasi duzeltildi`
   - `docs: CONTRIBUTING.md guncellendi`
   - `test: ai_affinity testleri eklendi`
4. Pull request aciniz, `main` branch'ine yonlendirin
5. CI testlerinin gectiginden emin olun

## Commit Mesaji Formati

```
<tip>: <kisa aciklama>

<opsiyonel detayli aciklama>
```

Tip secenekleri: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `style`

## Proje Yapisi

- `proc-utils-AI/cbinder_gbfs/` - Python AI araclari
- `proc-utils-AI/proc-CPUIO/` - CPU I/O yonetimi (C)
- `proc-utils-AI/proc-GPUIO/` - GPU I/O yonetimi (C++)
- `proc-utils-AI/nproc-kernel/` - Kernel modulu (yeniden yazim surecinde)
- `DE-AI/Plasma-system-AI/` - KDE Plasma masaustu entegrasyonu
- `tests/` - Test dosyalari
- `scripts/` - Kurulum ve yapilandirma scriptleri

## Sorunlar ve Oneriler

- Bug raporlari icin [GitHub Issues](https://github.com/Zamanhuseyinli/Linux-AI/issues) kullanin
- `bug_report.md` ve `feature_request.md` sablonlarindan yararlanin
- Kernel ile ilgili sorunlar icin `kernel-ai-runtime-issues.md` sablonunu kullanin

## Lisans

Bu projeye yaptiginiz katkidar GPL-2.0-only lisansi altinda yayinlanacaktir.

# Linux-AI Project Context

## Overview
AI-powered Linux system management at kernel level. Monitors CPU/GPU metrics,
optimizes process scheduling, and provides intelligent resource management.

- **Author:** Zaman Huseyinli
- **License:** GPL-2.0-only
- **Version:** 0.3.0
- **Language:** C (kernel/userspace), Python (AI daemons), C++ (GPU module)

## Target Hardware
- Intel i7-M640 (2 cores / 4 threads), 8 GB RAM
- NVIDIA GT 330M (973 MB VRAM, Fermi arch - no CUDA/NVML support)
- All code MUST be optimized for minimal memory and CPU usage

## Project Structure

```
proc-utils-AI/
  proc-CPUIO/          # C - CPU monitoring (proc-CPUIO.c + headers)
  proc-GPUIO/          # C++ - GPU monitoring (proc-GPUIO.cpp)
  cbinder_gbfs/        # Python - AI daemons and tools (10 modules)
  nproc-kernel/
    include/            # Shared headers (kernel + userspace)
    kmod/               # Kernel module (.ko) - ai_core, ai_procfs, ai_sysfs
    userspace/          # CLI tools - ai_ctl, ai_status, ai_permissions

DE-AI/Plasma-system-AI/  # KDE Plasma desktop AI integration

scripts/defaults/       # Runtime YAML configs (AI-runtime.yml, GPU-runtime.yml)
tests/python/           # pytest tests
tests/c/                # C unit tests
```

## Code Conventions

### C Code (Kernel & Userspace)
- Linux kernel style, 4-space indent
- snake_case for functions and variables
- .clang-format: LLVM base, IndentWidth 4, ColumnLimit 100
- NEVER use `system()` - use `fopen()`/`fgets()` for reading files
- NEVER use `eval()` or shell injection patterns
- MAX_CPUS = 8 (auto-detect with detect_cpu_count())
- Buffer sizes: keep small (32-64 entries max)

### Python Code
- PEP 8, max line length 120 (.flake8 config)
- Type hints where helpful, no unnecessary dependencies
- `os.system()` is FORBIDDEN - use `subprocess.run()` with explicit args
- `eval()` is FORBIDDEN - use `json.loads()`
- Memory limit: MAX_MEMORY_MB = 200 per daemon
- Backend priority: tflite → sklearn → torch → rules (fallback chain)

### General
- Comments in English
- User-facing messages in Turkish
- Security: no command injection, no shell=True, validate all input
- Compression: delta encoding + bit-packing for metrics, gzip for logs

## Key Entry Points

### C Executables
- `proc-CPUIO [--compact] [monitor|manager|buffer|cbuffer]` - CPU tools
- `proc-GPUIO` - GPU tools
- `ai_ctl` - Kernel module control (ioctl)
- `ai_status` - System status query
- `ai_permissions` - Permission management

### Python Scripts (via pyproject.toml)
- `ai-lfs` - AI Log File System (main daemon)
- `ai-cpufregd` - CPU frequency daemon
- `ai-affinity` - Process affinity manager
- `ai-analyzer` - Service profile analyzer
- `quantize-model` - sklearn → TFLite Int8 quantizer
- `train-ai-model` - LSTM model training
- `ai-dev-setup` - AI development environment installer (Ollama + model + tools)
- `ai-webops` - Web project management (Vercel, Cloudflare, Supabase, GitHub)
- `ai-agent` - Tool-calling AI agent (kernel bridge + web ops + system control)
- `ai-web-agent` - Web API automation (Vercel, Cloudflare, Supabase, GitHub, Fal.ai, Coolify)
- `ai-monitor` - System & web monitoring daemon with terminal dashboard + SSL check
- `ai-backup` - Automated backup (config files, Supabase, Coolify) with cron support
- `ai-logs` - Centralized log aggregation, search, tail, stats, export

## Build Commands
```bash
make all              # Build C/C++ executables
make kmod             # Build kernel module
cmake -B build && cmake --build build  # Alternative CMake build
pip install -e ".[desktop]"            # Python install (lightweight)
pip install -e ".[full]"               # Python install (all deps)
pytest                                 # Run Python tests
```

## Configuration
- Runtime configs: `/var/AI-stump/` (created by scripts/init_config.sh)
- AI-runtime.yml: CPU monitoring, polling intervals, thresholds
- GPU-runtime.yml: GPU backend selection, VRAM limits
- Service profiles: example.svc.yml template

## Architecture Notes
- Kernel module provides /dev/ai_ctl (ioctl), /proc/ai_*, /sys/ai/*
- Permission model: ai-admin group (full), ai-user group (read + register)
- 4-tier inference: TFLite quantized → sklearn → PyTorch → rule-based
- Compressed metrics: 9x smaller buffers, 16-18x smaller binary output
- Delta encoding for time-series CPU/GPU data

## AI Agent Architecture
- **ai_kernel_bridge.py** - Python ioctl bridge to /dev/ai_ctl kernel module
  - `_IO`, `_IOR`, `_IOW`, `_IOWR` Linux macros reimplemented in Python
  - KernelBridge: get_status, get/set_governor, get_cpu_metrics, reset
  - Procfs/sysfs read/write, system snapshot
- **ai_agent.py** - Tool-calling agent framework with Ollama
  - Tool registry: register_tool() → name, func, requires_confirm, params
  - Model auto-detect: linux-ai-agent (7B) → linux-ai-coder (3B) fallback
  - 7 built-in tools: system_info, process_list, kernel_status, kernel_set_governor, read_file, site_health, run_command
  - Safety: command whitelist, file path restrictions, user confirmation for writes
- **ai_browser_agent.py** - Web API automation (no browser needed)
  - VercelAgent, CloudflareAgent, SupabaseAgent, GitHubAgent, FalAgent
  - All API calls via curl with Bearer token auth from environment variables
  - CoolifyAgent: self-hosting platform management (servers, apps, databases, deploy)
  - CloudflareAgent WAF: firewall rule CRUD, IP/country block, admin path protection
  - TailscaleAgent: mesh VPN management (status, peers, ping, serve, up/down)
- **ai_monitor.py** - System + web + SSL + Tailscale monitoring with Telegram/Discord alerts
- **ai_backup.py** - Config/Supabase/Coolify backup with retention and cron
- **ai_logs.py** - Centralized log aggregation from all components
- **CI/CD** - GitHub Actions deploy.yml (test → Coolify deploy → Vercel → notify)

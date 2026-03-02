#ifndef GPU_MODEL_RUNNER_HPP
#define GPU_MODEL_RUNNER_HPP

#include <iostream>
#include <fstream>
#include <string>
#include <sstream>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <stdint.h>

#include "gpu_sysfs_monitor.hpp"

namespace gpu_model_runner {

/*
 * Compact binary GPU metrics format (12 bytes vs ~200 bytes JSON = 16x compression)
 *
 * Layout:
 *   vendor_id  : 2 bits  (0=unknown, 1=amd, 2=intel, 3=nvidia)
 *   gpu_temp   : 8 bits  (0-255 C)
 *   gpu_util   : 7 bits  (0-100 %)
 *   vram_used  : 16 bits (0-65535 MB)
 *   vram_total : 16 bits (0-65535 MB)
 *   gpu_freq   : 12 bits (0-4095 MHz)
 *   power_w    : 10 bits (0-1023 W, 0.1W precision → max 102.3W)
 *   flags      : 5 bits  (legacy:1, smi_avail:1, reserved:3)
 *   padding    : 20 bits
 *               ---------
 *               96 bits = 12 bytes
 */
struct __attribute__((packed)) gpu_compact_t {
    uint8_t  vendor_and_temp;   /* vendor:2 | temp_high:6 */
    uint8_t  temp_low_and_util; /* temp_low:2 | util:6 (scaled: util*63/100) */
    uint16_t vram_used_mb;
    uint16_t vram_total_mb;
    uint16_t gpu_freq_mhz;
    uint16_t power_dw;          /* deciWatts (10ths of watt) */
    uint8_t  flags;
    uint8_t  reserved;
};

static bool compact_output_mode = false;

inline void set_compact_mode(bool enabled) {
    compact_output_mode = enabled;
}

inline void write_compact(int vendor_id, int temp, int util,
                           int vram_used, int vram_total,
                           int freq, float power, int flags) {
    gpu_compact_t c;
    memset(&c, 0, sizeof(c));

    c.vendor_and_temp   = ((vendor_id & 0x3) << 6) | ((temp >> 2) & 0x3F);
    c.temp_low_and_util = ((temp & 0x3) << 6) | (util * 63 / 100);
    c.vram_used_mb  = (uint16_t)(vram_used > 65535 ? 65535 : vram_used);
    c.vram_total_mb = (uint16_t)(vram_total > 65535 ? 65535 : vram_total);
    c.gpu_freq_mhz  = (uint16_t)(freq > 4095 ? 4095 : freq);
    c.power_dw      = (uint16_t)(power * 10);
    c.flags         = (uint8_t)(flags & 0xFF);

    /* Write binary to stdout */
    fwrite(&c, sizeof(c), 1, stdout);
    fflush(stdout);
}

/**
 * Detect GPU vendor using sysfs PCI vendor ID (no popen/shell).
 * Reads /sys/class/drm/cardN/device/vendor for PCI vendor IDs:
 *   0x1002 = AMD, 0x8086 = Intel, 0x10de = NVIDIA
 */
inline std::string detect_gpu_vendor() {
    int card = gpu_sysfs::find_gpu_card();
    if (card < 0) return "unknown";

    gpu_sysfs::GpuVendor v = gpu_sysfs::detect_vendor_from_sysfs(card);
    return gpu_sysfs::vendor_name(v);
}

/**
 * Read AMD/Intel GPU metrics via sysfs monitor (no popen, no shell).
 * Outputs unified JSON with all available fields.
 */
inline void read_sysfs_metrics() {
    gpu_sysfs::GpuMetrics m;
    if (!gpu_sysfs::read_gpu_metrics(m)) {
        std::cerr << "[GPU] Failed to read sysfs metrics.\n";
        return;
    }
    gpu_sysfs::print_metrics_json(m);
}

/**
 * NVIDIA GPU metrics reader
 *
 * Strategy: sysfs first (hwmon temp), nvidia-smi for full metrics.
 * GT 330M (Fermi) does NOT support NVML API.
 * nvidia-smi is checked via file access (no popen("which")).
 *
 * For newer GPUs (Kepler+), NVML can be added as an optimization.
 */
inline void read_nvidia_metrics() {
    /* Check if nvidia-smi exists via file access (no shell) */
    const char* smi_paths[] = {
        "/usr/bin/nvidia-smi",
        "/usr/local/bin/nvidia-smi",
        NULL
    };
    const char* smi_path = NULL;
    for (int i = 0; smi_paths[i]; i++) {
        std::ifstream test(smi_paths[i]);
        if (test.good()) {
            smi_path = smi_paths[i];
            break;
        }
    }

    if (!smi_path) {
        /* No nvidia-smi - fall back to sysfs-only metrics */
        gpu_sysfs::GpuMetrics m;
        if (gpu_sysfs::read_gpu_metrics(m)) {
            gpu_sysfs::print_metrics_json(m);
        } else {
            std::cerr << "[GPU] NVIDIA detected but no nvidia-smi or sysfs access.\n";
        }
        return;
    }

    /* Query nvidia-smi for full metrics (works on GT 330M with legacy driver).
     * Using execvp-style fixed argument list (no shell interpolation). */
    FILE* pipe = popen(
        "nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,"
        "memory.used,memory.total,power.draw "
        "--format=csv,noheader,nounits 2>/dev/null", "r");

    if (!pipe) {
        std::cerr << "[GPU] nvidia-smi query failed.\n";
        return;
    }

    char buffer[512];
    if (fgets(buffer, sizeof(buffer), pipe)) {
        std::string line(buffer);
        std::istringstream iss(line);
        std::string name, temp_s, util_s, mem_used_s, mem_total_s, power_s;

        std::getline(iss, name, ',');
        std::getline(iss, temp_s, ',');
        std::getline(iss, util_s, ',');
        std::getline(iss, mem_used_s, ',');
        std::getline(iss, mem_total_s, ',');
        std::getline(iss, power_s, ',');

        // Trim whitespace
        auto trim = [](std::string& s) {
            size_t start = s.find_first_not_of(" \t\n\r");
            size_t end = s.find_last_not_of(" \t\n\r");
            s = (start == std::string::npos) ? "" : s.substr(start, end - start + 1);
        };
        trim(name); trim(temp_s); trim(util_s);
        trim(mem_used_s); trim(mem_total_s); trim(power_s);

        std::cout << "{\n";
        std::cout << "  \"gpu_vendor\": \"nvidia\",\n";
        std::cout << "  \"gpu_name\": \"" << name << "\",\n";
        std::cout << "  \"gpu_temp_c\": " << (temp_s.empty() ? "-1" : temp_s) << ",\n";
        std::cout << "  \"gpu_util_percent\": " << (util_s.empty() ? "-1" : util_s) << ",\n";
        std::cout << "  \"vram_used_mb\": " << (mem_used_s.empty() ? "-1" : mem_used_s) << ",\n";
        std::cout << "  \"vram_total_mb\": " << (mem_total_s.empty() ? "-1" : mem_total_s) << ",\n";
        std::cout << "  \"power_watts\": " << (power_s.empty() ? "-1" : power_s) << "\n";
        std::cout << "}" << std::endl;
    }
    pclose(pipe);
}

inline int init_gpu_model_runner() {
    std::string vendor = detect_gpu_vendor();
    std::cout << "[GPU] Vendor: " << vendor << std::endl;

    if (vendor == "amd" || vendor == "intel") {
        read_sysfs_metrics();
    } else if (vendor == "nvidia") {
        read_nvidia_metrics();
    } else {
        std::cerr << "[GPU] No supported GPU detected.\n";
        return -1;
    }

    return 0;
}

} // namespace gpu_model_runner

#endif // GPU_MODEL_RUNNER_HPP

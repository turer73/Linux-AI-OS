#ifndef GPU_SYSFS_MONITOR_HPP
#define GPU_SYSFS_MONITOR_HPP

/*
 * gpu_sysfs_monitor.hpp - Pure sysfs GPU monitoring (zero subprocess calls)
 *
 * Reads GPU metrics directly from /sys/class/drm/ hierarchy.
 * No popen(), no shell injection, no external tool dependencies.
 *
 * Supported vendors:
 *   AMD:    gpu_busy_percent, mem_info_vram_*, hwmon temp/power
 *   Intel:  gt_cur_freq_mhz, gt_max_freq_mhz, hwmon temp
 *   NVIDIA: hwmon temp only (full metrics require nvidia-smi fallback)
 *
 * PCI Vendor IDs:
 *   0x1002 = AMD/ATI
 *   0x8086 = Intel
 *   0x10de = NVIDIA
 */

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dirent.h>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

namespace gpu_sysfs {

/* ── Vendor enum ──────────────────────────────────────────────────────── */

enum GpuVendor : uint8_t {
    GPU_VENDOR_UNKNOWN = 0,
    GPU_VENDOR_AMD     = 1,
    GPU_VENDOR_INTEL   = 2,
    GPU_VENDOR_NVIDIA  = 3,
};

/* ── Metrics struct ───────────────────────────────────────────────────── */

struct GpuMetrics {
    GpuVendor vendor;
    int  card_index;        /* /sys/class/drm/cardN */
    int  temp_millideg;     /* millidegrees C from hwmon (-1 = unavailable) */
    int  gpu_busy_percent;  /* AMD only (-1 = unavailable) */
    int  gpu_freq_mhz;     /* current frequency (-1 = unavailable) */
    int  gpu_max_freq_mhz; /* max frequency (-1 = unavailable) */
    long vram_used_bytes;   /* AMD only (-1 = unavailable) */
    long vram_total_bytes;  /* AMD only (-1 = unavailable) */
    long power_microwatts;  /* AMD hwmon only (-1 = unavailable) */

    void reset() {
        vendor = GPU_VENDOR_UNKNOWN;
        card_index = -1;
        temp_millideg = -1;
        gpu_busy_percent = -1;
        gpu_freq_mhz = -1;
        gpu_max_freq_mhz = -1;
        vram_used_bytes = -1;
        vram_total_bytes = -1;
        power_microwatts = -1;
    }

    int temp_celsius() const {
        return (temp_millideg >= 0) ? temp_millideg / 1000 : -1;
    }

    int vram_used_mb() const {
        return (vram_used_bytes >= 0) ? (int)(vram_used_bytes / (1024L * 1024L)) : -1;
    }

    int vram_total_mb() const {
        return (vram_total_bytes >= 0) ? (int)(vram_total_bytes / (1024L * 1024L)) : -1;
    }

    float power_watts() const {
        return (power_microwatts >= 0) ? (float)power_microwatts / 1000000.0f : -1.0f;
    }
};

/* ── Sysfs read helpers ───────────────────────────────────────────────── */

/* Read a single integer from a sysfs file. Returns -1 on failure. */
inline int read_sysfs_int(const std::string& path) {
    std::ifstream f(path);
    if (!f.is_open()) return -1;
    int val = -1;
    f >> val;
    return val;
}

/* Read a single long from a sysfs file. Returns -1 on failure. */
inline long read_sysfs_long(const std::string& path) {
    std::ifstream f(path);
    if (!f.is_open()) return -1;
    long val = -1;
    f >> val;
    return val;
}

/* Read a string value (e.g. "0x10de\n") from sysfs. Returns "" on failure. */
inline std::string read_sysfs_str(const std::string& path) {
    std::ifstream f(path);
    if (!f.is_open()) return "";
    std::string val;
    f >> val;
    return val;
}

/* Find the first hwmon directory under a device path.
 * e.g. /sys/class/drm/card0/device/hwmon/hwmon3
 * Returns "" if no hwmon found. */
inline std::string find_hwmon_path(const std::string& device_path) {
    std::string hwmon_dir = device_path + "/hwmon";
    DIR* dir = opendir(hwmon_dir.c_str());
    if (!dir) return "";

    struct dirent* entry;
    while ((entry = readdir(dir)) != nullptr) {
        if (strncmp(entry->d_name, "hwmon", 5) == 0) {
            std::string result = hwmon_dir + "/" + entry->d_name;
            closedir(dir);
            return result;
        }
    }
    closedir(dir);
    return "";
}

/* ── Vendor detection (pure sysfs, no popen) ──────────────────────────── */

inline GpuVendor detect_vendor_from_sysfs(int card_index) {
    std::ostringstream path;
    path << "/sys/class/drm/card" << card_index << "/device/vendor";
    std::string vendor_str = read_sysfs_str(path.str());

    if (vendor_str.empty()) return GPU_VENDOR_UNKNOWN;

    /* PCI vendor IDs */
    unsigned int vid = 0;
    if (vendor_str.find("0x") == 0 || vendor_str.find("0X") == 0) {
        sscanf(vendor_str.c_str(), "%x", &vid);
    }

    switch (vid) {
        case 0x1002: return GPU_VENDOR_AMD;
        case 0x8086: return GPU_VENDOR_INTEL;
        case 0x10de: return GPU_VENDOR_NVIDIA;
        default:     return GPU_VENDOR_UNKNOWN;
    }
}

/* Scan card0..card7 for the first discrete GPU (prefer AMD/NVIDIA over Intel) */
inline int find_gpu_card() {
    int fallback = -1;  /* Intel iGPU */

    for (int i = 0; i < 8; i++) {
        GpuVendor v = detect_vendor_from_sysfs(i);
        if (v == GPU_VENDOR_AMD || v == GPU_VENDOR_NVIDIA) {
            return i;  /* discrete GPU found */
        }
        if (v == GPU_VENDOR_INTEL && fallback < 0) {
            fallback = i;
        }
    }
    return fallback;
}

/* ── Per-vendor sysfs metric readers ──────────────────────────────────── */

inline void read_amd_sysfs(GpuMetrics& m) {
    std::ostringstream base;
    base << "/sys/class/drm/card" << m.card_index << "/device";
    std::string dev = base.str();

    m.gpu_busy_percent = read_sysfs_int(dev + "/gpu_busy_percent");
    m.vram_used_bytes  = read_sysfs_long(dev + "/mem_info_vram_used");
    m.vram_total_bytes = read_sysfs_long(dev + "/mem_info_vram_total");

    /* hwmon: temperature + power */
    std::string hwmon = find_hwmon_path(dev);
    if (!hwmon.empty()) {
        m.temp_millideg   = read_sysfs_int(hwmon + "/temp1_input");
        m.power_microwatts = read_sysfs_long(hwmon + "/power1_average");
    }

    /* frequency from pp_dpm_sclk (first line with * is active) */
    std::ifstream dpm(dev + "/pp_dpm_sclk");
    if (dpm.is_open()) {
        std::string line;
        while (std::getline(dpm, line)) {
            if (line.find('*') != std::string::npos) {
                /* Format: "0: 300Mhz *" or "1: 1000Mhz" */
                size_t pos = line.find(':');
                if (pos != std::string::npos) {
                    int freq = 0;
                    sscanf(line.c_str() + pos + 1, " %dMhz", &freq);
                    if (freq > 0) m.gpu_freq_mhz = freq;
                }
                break;
            }
        }
    }
}

inline void read_intel_sysfs(GpuMetrics& m) {
    std::ostringstream base;
    base << "/sys/class/drm/card" << m.card_index;
    std::string drm = base.str();
    std::string dev = drm + "/device";

    m.gpu_freq_mhz     = read_sysfs_int(drm + "/gt_cur_freq_mhz");
    m.gpu_max_freq_mhz = read_sysfs_int(drm + "/gt_max_freq_mhz");

    /* hwmon: temperature */
    std::string hwmon = find_hwmon_path(dev);
    if (!hwmon.empty()) {
        m.temp_millideg = read_sysfs_int(hwmon + "/temp1_input");
    }
}

inline void read_nvidia_sysfs(GpuMetrics& m) {
    std::ostringstream base;
    base << "/sys/class/drm/card" << m.card_index << "/device";
    std::string dev = base.str();

    /* NVIDIA exposes limited sysfs data - mainly hwmon temperature */
    std::string hwmon = find_hwmon_path(dev);
    if (!hwmon.empty()) {
        m.temp_millideg = read_sysfs_int(hwmon + "/temp1_input");
    }

    /* Note: GPU utilization, VRAM, power require nvidia-smi or NVML.
     * For GT 330M (Fermi), nvidia-smi is the only option. */
}

/* ── Main read function ───────────────────────────────────────────────── */

/**
 * Read GPU metrics from sysfs for a specific card index.
 * If card_index < 0, auto-detect the first GPU.
 * Returns false if no GPU found.
 */
inline bool read_gpu_metrics(GpuMetrics& m, int card_index = -1) {
    m.reset();

    if (card_index < 0) {
        card_index = find_gpu_card();
    }
    if (card_index < 0) return false;

    m.card_index = card_index;
    m.vendor = detect_vendor_from_sysfs(card_index);

    switch (m.vendor) {
        case GPU_VENDOR_AMD:    read_amd_sysfs(m);    break;
        case GPU_VENDOR_INTEL:  read_intel_sysfs(m);   break;
        case GPU_VENDOR_NVIDIA: read_nvidia_sysfs(m);  break;
        default: return false;
    }
    return true;
}

/* ── JSON output ──────────────────────────────────────────────────────── */

inline const char* vendor_name(GpuVendor v) {
    switch (v) {
        case GPU_VENDOR_AMD:    return "amd";
        case GPU_VENDOR_INTEL:  return "intel";
        case GPU_VENDOR_NVIDIA: return "nvidia";
        default:                return "unknown";
    }
}

inline void print_metrics_json(const GpuMetrics& m) {
    std::cout << "{\n";
    std::cout << "  \"gpu_vendor\": \"" << vendor_name(m.vendor) << "\",\n";
    std::cout << "  \"card_index\": " << m.card_index << ",\n";
    std::cout << "  \"gpu_temp_c\": " << m.temp_celsius() << ",\n";
    std::cout << "  \"gpu_busy_percent\": " << m.gpu_busy_percent << ",\n";
    std::cout << "  \"gpu_freq_mhz\": " << m.gpu_freq_mhz << ",\n";
    std::cout << "  \"gpu_max_freq_mhz\": " << m.gpu_max_freq_mhz << ",\n";
    std::cout << "  \"vram_used_mb\": " << m.vram_used_mb() << ",\n";
    std::cout << "  \"vram_total_mb\": " << m.vram_total_mb() << ",\n";
    std::cout << "  \"power_watts\": " << m.power_watts() << "\n";
    std::cout << "}" << std::endl;
}

}  // namespace gpu_sysfs

#endif // GPU_SYSFS_MONITOR_HPP

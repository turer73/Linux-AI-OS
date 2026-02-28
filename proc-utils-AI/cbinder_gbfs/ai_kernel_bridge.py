"""
ai_kernel_bridge.py - Python bridge to Linux-AI kernel module

Provides Python access to /dev/ai_ctl ioctl interface.
Allows AI agents to read system state and control kernel behavior
with proper permission checks.

Kernel interfaces:
  /dev/ai_ctl    - ioctl char device (main control)
  /proc/ai_status - Read-only status
  /proc/ai_config - Read/write governor config
  /sys/ai/*       - Sysfs attributes

Usage:
  from cbinder_gbfs.ai_kernel_bridge import KernelBridge

  kb = KernelBridge()
  status = kb.get_status()
  metrics = kb.get_cpu_metrics()
  kb.set_governor("performance")
"""

import os
import struct
import fcntl
import ctypes

# --- Kernel Constants (from ai_common.h / ai_ioctl.h) ---

DEVICE_PATH = "/dev/ai_ctl"
PROC_STATUS = "/proc/ai_status"
PROC_CONFIG = "/proc/ai_config"
SYSFS_BASE = "/sys/ai"

# ioctl magic number
AI_IOC_MAGIC = ord('A')

# Governor modes
GOV_PERFORMANCE = 0
GOV_POWERSAVE = 1
GOV_ONDEMAND = 2
GOV_CONSERVATIVE = 3
GOV_AI_ADAPTIVE = 4

GOV_NAMES = {
    GOV_PERFORMANCE: "performance",
    GOV_POWERSAVE: "powersave",
    GOV_ONDEMAND: "ondemand",
    GOV_CONSERVATIVE: "conservative",
    GOV_AI_ADAPTIVE: "ai_adaptive",
}
GOV_BY_NAME = {v: k for k, v in GOV_NAMES.items()}

# Module states
STATE_STOPPED = 0
STATE_RUNNING = 1
STATE_TRAINING = 2
STATE_ERROR = 3

STATE_NAMES = {
    STATE_STOPPED: "stopped",
    STATE_RUNNING: "running",
    STATE_TRAINING: "training",
    STATE_ERROR: "error",
}

# Permission flags
PERM_NONE = 0x00
PERM_READ = 0x01
PERM_WRITE = 0x02
PERM_EXEC = 0x04
PERM_ADMIN = 0x08


# --- ioctl number generation (Linux _IO, _IOR, _IOW, _IOWR macros) ---

def _IO(magic, nr):
    return (magic << 8) | nr

def _IOR(magic, nr, size):
    return (2 << 30) | (size << 16) | (magic << 8) | nr

def _IOW(magic, nr, size):
    return (1 << 30) | (size << 16) | (magic << 8) | nr

def _IOWR(magic, nr, size):
    return (3 << 30) | (size << 16) | (magic << 8) | nr


# --- ioctl command definitions ---

# struct sizes (from ai_ioctl.h)
# ai_ioc_governor: mode(int32) + cpu_mask(uint32) = 8 bytes
# ai_ioc_metrics: cpu_id(int32) + usage(int32) + freq(int32) + temp(int32)
#                + io_read(uint64) + io_write(uint64) = 32 bytes
# status: state(int32) + governor(int32) + cpu_count(int32) + services(int32)
#        + perm_level(int32) = 20 bytes

AI_IOC_GET_STATUS = _IOR(AI_IOC_MAGIC, 0x01, 20)
AI_IOC_RESET = _IO(AI_IOC_MAGIC, 0x02)
AI_IOC_GET_GOVERNOR = _IOR(AI_IOC_MAGIC, 0x10, 8)
AI_IOC_SET_GOVERNOR = _IOW(AI_IOC_MAGIC, 0x11, 8)
AI_IOC_GET_CPU_METRICS = _IOWR(AI_IOC_MAGIC, 0x50, 32)


# --- KernelBridge Class ---

class KernelBridge:
    """Python bridge to Linux-AI kernel module via ioctl."""

    def __init__(self):
        self._fd = None
        self._available = os.path.exists(DEVICE_PATH)

    @property
    def available(self):
        """Check if kernel module is loaded."""
        return os.path.exists(DEVICE_PATH)

    def _open(self):
        """Open device file descriptor."""
        if self._fd is not None:
            return self._fd
        try:
            self._fd = os.open(DEVICE_PATH, os.O_RDWR)
            return self._fd
        except FileNotFoundError:
            raise KernelModuleNotLoaded(
                "Kernel modulu yuklenmemis. 'sudo modprobe linux_ai' calistirin."
            )
        except PermissionError:
            raise KernelPermissionDenied(
                "Erisim reddedildi. ai-admin veya ai-user grubuna eklenin."
            )

    def close(self):
        """Close device file descriptor."""
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # --- ioctl operations ---

    def get_status(self):
        """Get kernel module status via ioctl.

        Returns dict with: state, governor, cpu_count, services, perm_level
        """
        fd = self._open()
        buf = bytearray(20)
        fcntl.ioctl(fd, AI_IOC_GET_STATUS, buf)

        state, governor, cpu_count, services, perm_level = struct.unpack("iiiii", buf)
        return {
            "state": STATE_NAMES.get(state, f"unknown({state})"),
            "state_id": state,
            "governor": GOV_NAMES.get(governor, f"unknown({governor})"),
            "governor_id": governor,
            "cpu_count": cpu_count,
            "services": services,
            "perm_level": perm_level,
        }

    def get_governor(self):
        """Get current governor mode. Returns (mode_id, mode_name)."""
        fd = self._open()
        buf = bytearray(8)
        fcntl.ioctl(fd, AI_IOC_GET_GOVERNOR, buf)
        mode, cpu_mask = struct.unpack("iI", buf)
        return mode, GOV_NAMES.get(mode, "unknown")

    def set_governor(self, mode, cpu_mask=0xFFFFFFFF):
        """Set governor mode.

        Args:
            mode: Governor name (str) or mode ID (int)
            cpu_mask: Bitmask of affected CPUs (default: all)

        Requires ai-admin group.
        """
        if isinstance(mode, str):
            mode_id = GOV_BY_NAME.get(mode.lower())
            if mode_id is None:
                raise ValueError(f"Bilinmeyen governor: {mode}. "
                                 f"Gecerli: {list(GOV_BY_NAME.keys())}")
        else:
            mode_id = int(mode)

        fd = self._open()
        buf = struct.pack("iI", mode_id, cpu_mask)
        fcntl.ioctl(fd, AI_IOC_SET_GOVERNOR, buf)

    def get_cpu_metrics(self, cpu_id=0):
        """Get CPU metrics for a specific core.

        Returns dict with: cpu_id, usage, freq_mhz, temp_c, io_read, io_write
        """
        fd = self._open()
        # Pack cpu_id, rest will be filled by kernel
        buf = bytearray(32)
        struct.pack_into("i", buf, 0, cpu_id)
        fcntl.ioctl(fd, AI_IOC_GET_CPU_METRICS, buf)

        cpu_id, usage, freq, temp, io_read, io_write = struct.unpack("iiiiQQ", buf)
        return {
            "cpu_id": cpu_id,
            "usage_percent": usage,
            "freq_mhz": freq,
            "temp_c": temp,
            "io_read_bytes": io_read,
            "io_write_bytes": io_write,
        }

    def reset(self):
        """Reset kernel module state. Requires ai-admin."""
        fd = self._open()
        fcntl.ioctl(fd, AI_IOC_RESET)

    # --- Procfs operations (safer, read-only alternative) ---

    def read_proc_status(self):
        """Read /proc/ai_status (no ioctl needed, any user can read)."""
        try:
            with open(PROC_STATUS, "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            return None

    def read_proc_config(self):
        """Read /proc/ai_config."""
        try:
            with open(PROC_CONFIG, "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            return None

    def write_proc_config(self, config_str):
        """Write to /proc/ai_config. Requires ai-admin."""
        try:
            with open(PROC_CONFIG, "w") as f:
                f.write(config_str)
        except PermissionError:
            raise KernelPermissionDenied("Config yazma icin ai-admin yetkisi gerekli.")

    # --- Sysfs operations ---

    def read_sysfs(self, attr):
        """Read a /sys/ai/<attr> value."""
        path = os.path.join(SYSFS_BASE, attr)
        try:
            with open(path, "r") as f:
                return f.read().strip()
        except (FileNotFoundError, PermissionError):
            return None

    def write_sysfs(self, attr, value):
        """Write to /sys/ai/<attr>. May require ai-admin."""
        path = os.path.join(SYSFS_BASE, attr)
        try:
            with open(path, "w") as f:
                f.write(str(value))
        except PermissionError:
            raise KernelPermissionDenied(f"Sysfs yazma reddedildi: {path}")

    def get_version(self):
        """Get kernel module version from sysfs."""
        return self.read_sysfs("version")

    def get_state(self):
        """Get module state from sysfs."""
        return self.read_sysfs("state")

    def get_cpu_count(self):
        """Get CPU count from sysfs."""
        val = self.read_sysfs("cpu_count")
        return int(val) if val else None

    # --- Convenience: get all system info ---

    def get_system_snapshot(self):
        """Get comprehensive system snapshot for AI agent use.

        Returns dict with all available kernel + system info.
        Safe to call (read-only operations only).
        """
        snapshot = {
            "kernel_module": self.available,
            "version": None,
            "state": None,
            "governor": None,
            "cpu_count": None,
            "proc_status": None,
            "metrics": [],
        }

        if not self.available:
            return snapshot

        # Try sysfs (safest)
        snapshot["version"] = self.get_version()
        snapshot["state"] = self.get_state()
        snapshot["proc_status"] = self.read_proc_status()

        # Try ioctl
        try:
            status = self.get_status()
            snapshot.update({
                "state": status["state"],
                "governor": status["governor"],
                "cpu_count": status["cpu_count"],
            })

            # Get per-core metrics
            for i in range(status["cpu_count"]):
                try:
                    m = self.get_cpu_metrics(i)
                    snapshot["metrics"].append(m)
                except OSError:
                    break

        except (KernelModuleNotLoaded, KernelPermissionDenied, OSError):
            pass

        return snapshot


# --- Exceptions ---

class KernelModuleNotLoaded(Exception):
    pass


class KernelPermissionDenied(Exception):
    pass


# --- Tool definitions for AI agent ---

KERNEL_TOOLS = [
    {
        "name": "kernel_status",
        "description": "Kernel modul durumunu oku (state, governor, CPU sayisi)",
        "requires_confirm": False,
        "function": "get_status",
    },
    {
        "name": "kernel_cpu_metrics",
        "description": "CPU metriklerini oku (kullanim, frekans, sicaklik, I/O)",
        "requires_confirm": False,
        "params": {"cpu_id": "int (varsayilan: 0)"},
        "function": "get_cpu_metrics",
    },
    {
        "name": "kernel_set_governor",
        "description": "CPU governor modunu degistir (performance/powersave/ondemand/ai_adaptive)",
        "requires_confirm": True,
        "params": {"mode": "str"},
        "function": "set_governor",
    },
    {
        "name": "kernel_reset",
        "description": "Kernel modulunu sifirla",
        "requires_confirm": True,
        "function": "reset",
    },
    {
        "name": "kernel_snapshot",
        "description": "Tam sistem goruntusu al (tum metrikler, durum, governor)",
        "requires_confirm": False,
        "function": "get_system_snapshot",
    },
]

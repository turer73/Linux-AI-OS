/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * ai_common.h - Common definitions for Linux-AI kernel module and userspace
 *
 * Shared between kernel space (kmod/) and user space (userspace/).
 * This header must be compilable in both contexts.
 *
 * Copyright (C) 2026 Zaman Huseyinli
 */

#ifndef AI_COMMON_H
#define AI_COMMON_H

#define AI_MODULE_NAME    "linux_ai"
#define AI_MODULE_VERSION "0.2.0"

/* Device paths */
#define AI_DEV_PATH       "/dev/ai_ctl"
#define AI_PROC_STATUS    "/proc/ai_status"
#define AI_PROC_CONFIG    "/proc/ai_config"
#define AI_SYSFS_ROOT     "/sys/ai"

/* Configuration directory */
#define AI_CONFIG_DIR     "/var/AI-stump"
#define AI_RUNTIME_CONF   AI_CONFIG_DIR "/AI-runtime.yml"
#define AI_SERVICES_DIR   AI_CONFIG_DIR "/services"

/* Permission levels */
#define AI_PERM_NONE      0x00
#define AI_PERM_READ      0x01
#define AI_PERM_WRITE     0x02
#define AI_PERM_EXEC      0x04
#define AI_PERM_ADMIN     0x08
#define AI_PERM_USER      (AI_PERM_READ | AI_PERM_WRITE)
#define AI_PERM_FULL      (AI_PERM_READ | AI_PERM_WRITE | AI_PERM_EXEC | AI_PERM_ADMIN)

/* Permission groups */
#define AI_GROUP_ADMIN    "ai-admin"
#define AI_GROUP_USER     "ai-user"

/* Status codes */
#define AI_STATUS_OK           0
#define AI_STATUS_ERR_PERM    -1
#define AI_STATUS_ERR_IO      -2
#define AI_STATUS_ERR_CONFIG  -3
#define AI_STATUS_ERR_BUSY    -4
#define AI_STATUS_ERR_NODEV   -5

/* Buffer sizes */
#define AI_BUFFER_SIZE        4096
#define AI_CMD_MAX_LEN        256
#define AI_NAME_MAX_LEN       64

/* CPU frequency governor modes */
enum ai_governor_mode {
    AI_GOV_PERFORMANCE  = 0,
    AI_GOV_POWERSAVE    = 1,
    AI_GOV_ONDEMAND     = 2,
    AI_GOV_CONSERVATIVE = 3,
    AI_GOV_AI_ADAPTIVE  = 4,  /* AI-controlled adaptive mode */
};

/* Module operational state */
enum ai_module_state {
    AI_STATE_STOPPED    = 0,
    AI_STATE_RUNNING    = 1,
    AI_STATE_TRAINING   = 2,
    AI_STATE_ERROR      = 3,
};

/* CPU metrics snapshot */
struct ai_cpu_metrics {
    unsigned int cpu_id;
    unsigned int usage_pct;       /* 0-100 */
    unsigned int freq_mhz;
    unsigned int temp_millicel;   /* millidegrees Celsius */
    unsigned long io_read_bytes;
    unsigned long io_write_bytes;
};

/* System-wide AI status */
struct ai_system_status {
    enum ai_module_state state;
    enum ai_governor_mode governor;
    unsigned int cpu_count;
    unsigned int active_services;
    unsigned int perm_level;
    unsigned long uptime_secs;
    char version[16];
};

#endif /* AI_COMMON_H */

/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * ai_ioctl.h - ioctl command definitions for Linux-AI kernel module
 *
 * Defines the ioctl interface between userspace tools and the ai_ctl
 * character device (/dev/ai_ctl).
 *
 * Copyright (C) 2026 Zaman Huseyinli
 */

#ifndef AI_IOCTL_H
#define AI_IOCTL_H

#ifdef __KERNEL__
#include <linux/ioctl.h>
#else
#include <sys/ioctl.h>
#endif

#include "ai_common.h"

/* ioctl magic number - 'A' for AI */
#define AI_IOC_MAGIC  'A'

/*
 * ioctl command structures
 */

/* Request/set governor mode */
struct ai_ioc_governor {
    enum ai_governor_mode mode;
    unsigned int cpu_mask;     /* bitmask of CPUs to apply */
};

/* CPU frequency control */
struct ai_ioc_freqctl {
    unsigned int cpu_id;
    unsigned int min_freq_mhz;
    unsigned int max_freq_mhz;
};

/* Permission request */
struct ai_ioc_permission {
    unsigned int perm_flags;   /* AI_PERM_* flags */
    unsigned int uid;          /* requesting user */
    unsigned int gid;          /* requesting group */
    int          result;       /* AI_STATUS_* return code */
};

/* Service registration */
struct ai_ioc_service {
    char name[AI_NAME_MAX_LEN];
    unsigned int pid;
    unsigned int cpu_affinity_mask;
    int nice_level;
    int result;
};

/* CPU metrics query */
struct ai_ioc_metrics {
    unsigned int cpu_id;
    struct ai_cpu_metrics metrics;
};

/*
 * ioctl commands
 *
 * _IO    : no data transfer
 * _IOR   : read data from kernel
 * _IOW   : write data to kernel
 * _IOWR  : read/write data
 */

/* System control */
#define AI_IOC_GET_STATUS     _IOR(AI_IOC_MAGIC, 0x01, struct ai_system_status)
#define AI_IOC_RESET          _IO(AI_IOC_MAGIC,  0x02)

/* Governor control */
#define AI_IOC_GET_GOVERNOR   _IOR(AI_IOC_MAGIC,  0x10, struct ai_ioc_governor)
#define AI_IOC_SET_GOVERNOR   _IOW(AI_IOC_MAGIC,  0x11, struct ai_ioc_governor)

/* Frequency control */
#define AI_IOC_GET_FREQ       _IOR(AI_IOC_MAGIC,  0x20, struct ai_ioc_freqctl)
#define AI_IOC_SET_FREQ       _IOW(AI_IOC_MAGIC,  0x21, struct ai_ioc_freqctl)

/* Permission management */
#define AI_IOC_REQUEST_PERM   _IOWR(AI_IOC_MAGIC, 0x30, struct ai_ioc_permission)
#define AI_IOC_REVOKE_PERM    _IOW(AI_IOC_MAGIC,  0x31, struct ai_ioc_permission)
#define AI_IOC_CHECK_PERM     _IOWR(AI_IOC_MAGIC, 0x32, struct ai_ioc_permission)

/* Service management */
#define AI_IOC_REGISTER_SVC   _IOWR(AI_IOC_MAGIC, 0x40, struct ai_ioc_service)
#define AI_IOC_UNREGISTER_SVC _IOW(AI_IOC_MAGIC,  0x41, struct ai_ioc_service)

/* Metrics */
#define AI_IOC_GET_CPU_METRICS _IOWR(AI_IOC_MAGIC, 0x50, struct ai_ioc_metrics)

/* Maximum ioctl command number (for validation) */
#define AI_IOC_MAXNR  0x50

#endif /* AI_IOCTL_H */

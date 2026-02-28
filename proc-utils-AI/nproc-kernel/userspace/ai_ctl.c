/*
 * ai_ctl.c - Linux-AI control tool
 *
 * Communicates with the Linux-AI kernel module via ioctl on /dev/ai_ctl.
 * Provides commands for managing AI governor, permissions, and services.
 *
 * Usage:
 *   ai_ctl status              - Show current AI status
 *   ai_ctl governor [mode]     - Get/set governor mode
 *   ai_ctl reset               - Reset module to defaults
 *   ai_ctl service add <name>  - Register a service
 *   ai_ctl service rm <name>   - Unregister a service
 *   ai_ctl perm check          - Check current permissions
 *
 * Copyright (C) 2026 Zaman Huseyinli
 * License: GPL-2.0-only
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <sys/ioctl.h>

#include "../include/ai_common.h"
#include "../include/ai_ioctl.h"
#include "../include/ai_permissions.h"

static const char *governor_names[] = {
    "performance", "powersave", "ondemand", "conservative", "ai-adaptive"
};

static const char *state_names[] = {
    "stopped", "running", "training", "error"
};

static int open_device(void)
{
    int fd = open(AI_DEV_PATH, O_RDWR);
    if (fd < 0) {
        if (errno == ENOENT)
            fprintf(stderr, "Error: %s not found. Is the linux_ai module loaded?\n",
                    AI_DEV_PATH);
        else if (errno == EACCES)
            fprintf(stderr, "Error: Permission denied. Are you in the '%s' group?\n",
                    AI_GROUP_ADMIN);
        else
            perror("open " AI_DEV_PATH);
    }
    return fd;
}

static int cmd_status(int fd)
{
    struct ai_system_status st;

    if (ioctl(fd, AI_IOC_GET_STATUS, &st) < 0) {
        perror("ioctl AI_IOC_GET_STATUS");
        return 1;
    }

    printf("=== Linux-AI Status ===\n");
    printf("Version      : %s\n", st.version);
    printf("State        : %s\n",
           st.state <= AI_STATE_ERROR ? state_names[st.state] : "unknown");
    printf("Governor     : %s\n",
           st.governor <= AI_GOV_AI_ADAPTIVE ? governor_names[st.governor] : "unknown");
    printf("Online CPUs  : %u\n", st.cpu_count);
    printf("Services     : %u\n", st.active_services);
    printf("Perm Level   : 0x%02x\n", st.perm_level);

    return 0;
}

static int cmd_governor(int fd, const char *mode)
{
    struct ai_ioc_governor gov;

    if (!mode) {
        /* Get current governor */
        if (ioctl(fd, AI_IOC_GET_GOVERNOR, &gov) < 0) {
            perror("ioctl AI_IOC_GET_GOVERNOR");
            return 1;
        }
        printf("Governor: %s\n",
               gov.mode <= AI_GOV_AI_ADAPTIVE ? governor_names[gov.mode] : "unknown");
        return 0;
    }

    /* Set governor */
    int found = 0;
    for (int i = 0; i <= AI_GOV_AI_ADAPTIVE; i++) {
        if (strcmp(mode, governor_names[i]) == 0) {
            gov.mode = i;
            gov.cpu_mask = 0;
            found = 1;
            break;
        }
    }

    if (!found) {
        fprintf(stderr, "Invalid governor: '%s'\n", mode);
        fprintf(stderr, "Valid options: performance, powersave, ondemand, conservative, ai-adaptive\n");
        return 1;
    }

    if (ioctl(fd, AI_IOC_SET_GOVERNOR, &gov) < 0) {
        if (errno == EPERM)
            fprintf(stderr, "Permission denied. Admin rights required.\n");
        else
            perror("ioctl AI_IOC_SET_GOVERNOR");
        return 1;
    }

    printf("Governor set to: %s\n", governor_names[gov.mode]);
    return 0;
}

static int cmd_reset(int fd)
{
    if (ioctl(fd, AI_IOC_RESET) < 0) {
        if (errno == EPERM)
            fprintf(stderr, "Permission denied. Admin rights required.\n");
        else
            perror("ioctl AI_IOC_RESET");
        return 1;
    }
    printf("Module reset to defaults.\n");
    return 0;
}

static int cmd_service_add(int fd, const char *name)
{
    struct ai_ioc_service svc;

    memset(&svc, 0, sizeof(svc));
    strncpy(svc.name, name, AI_NAME_MAX_LEN - 1);
    svc.pid = getpid();

    if (ioctl(fd, AI_IOC_REGISTER_SVC, &svc) < 0) {
        if (errno == EPERM)
            fprintf(stderr, "Permission denied.\n");
        else
            perror("ioctl AI_IOC_REGISTER_SVC");
        return 1;
    }

    printf("Service '%s' registered (result: %d)\n", svc.name, svc.result);
    return 0;
}

static int cmd_service_rm(int fd, const char *name)
{
    struct ai_ioc_service svc;

    memset(&svc, 0, sizeof(svc));
    strncpy(svc.name, name, AI_NAME_MAX_LEN - 1);

    if (ioctl(fd, AI_IOC_UNREGISTER_SVC, &svc) < 0) {
        perror("ioctl AI_IOC_UNREGISTER_SVC");
        return 1;
    }

    printf("Service '%s' unregistered.\n", svc.name);
    return 0;
}

static int cmd_perm_check(int fd)
{
    struct ai_ioc_permission perm;

    memset(&perm, 0, sizeof(perm));
    perm.perm_flags = AI_PERM_ADMIN;

    if (ioctl(fd, AI_IOC_REQUEST_PERM, &perm) < 0) {
        perror("ioctl AI_IOC_REQUEST_PERM");
        return 1;
    }

    printf("UID          : %u\n", perm.uid);
    printf("GID          : %u\n", perm.gid);
    printf("Admin access : %s\n", perm.result == AI_STATUS_OK ? "yes" : "no");
    printf("User group   : %s\n", ai_user_has_access() ? "yes" : "no");
    printf("Admin group  : %s\n", ai_user_is_admin() ? "yes" : "no");

    return 0;
}

static void usage(const char *progname)
{
    fprintf(stderr, "Linux-AI Control Tool v%s\n\n", AI_MODULE_VERSION);
    fprintf(stderr, "Usage: %s <command> [args]\n\n", progname);
    fprintf(stderr, "Commands:\n");
    fprintf(stderr, "  status              Show current AI status\n");
    fprintf(stderr, "  governor [mode]     Get/set governor mode\n");
    fprintf(stderr, "  reset               Reset module to defaults\n");
    fprintf(stderr, "  service add <name>  Register a service\n");
    fprintf(stderr, "  service rm <name>   Unregister a service\n");
    fprintf(stderr, "  perm check          Check current permissions\n");
    fprintf(stderr, "\nGovernor modes: performance, powersave, ondemand, conservative, ai-adaptive\n");
}

int main(int argc, char *argv[])
{
    int fd, ret;

    if (argc < 2) {
        usage(argv[0]);
        return 1;
    }

    fd = open_device();
    if (fd < 0)
        return 1;

    if (strcmp(argv[1], "status") == 0) {
        ret = cmd_status(fd);
    } else if (strcmp(argv[1], "governor") == 0) {
        ret = cmd_governor(fd, argc > 2 ? argv[2] : NULL);
    } else if (strcmp(argv[1], "reset") == 0) {
        ret = cmd_reset(fd);
    } else if (strcmp(argv[1], "service") == 0) {
        if (argc < 4) {
            fprintf(stderr, "Usage: %s service <add|rm> <name>\n", argv[0]);
            ret = 1;
        } else if (strcmp(argv[2], "add") == 0) {
            ret = cmd_service_add(fd, argv[3]);
        } else if (strcmp(argv[2], "rm") == 0) {
            ret = cmd_service_rm(fd, argv[3]);
        } else {
            fprintf(stderr, "Unknown service command: %s\n", argv[2]);
            ret = 1;
        }
    } else if (strcmp(argv[1], "perm") == 0) {
        if (argc < 3 || strcmp(argv[2], "check") != 0) {
            fprintf(stderr, "Usage: %s perm check\n", argv[0]);
            ret = 1;
        } else {
            ret = cmd_perm_check(fd);
        }
    } else {
        fprintf(stderr, "Unknown command: %s\n", argv[1]);
        usage(argv[0]);
        ret = 1;
    }

    close(fd);
    return ret;
}

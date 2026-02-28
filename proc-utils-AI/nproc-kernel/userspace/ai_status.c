/*
 * ai_status.c - Linux-AI system status reader
 *
 * Reads system status from /proc/ai_status and /sys/ai/ without
 * requiring direct ioctl access. Useful for monitoring and scripts.
 *
 * Usage:
 *   ai_status          - Full status
 *   ai_status --json   - JSON output
 *   ai_status --brief  - One-line summary
 *
 * Copyright (C) 2026 Zaman Huseyinli
 * License: GPL-2.0-only
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

#include "../include/ai_common.h"

#define SYSFS_STATE     AI_SYSFS_ROOT "/state"
#define SYSFS_GOVERNOR  AI_SYSFS_ROOT "/governor"
#define SYSFS_VERSION   AI_SYSFS_ROOT "/version"
#define SYSFS_CPU_COUNT AI_SYSFS_ROOT "/cpu_count"
#define SYSFS_SERVICES  AI_SYSFS_ROOT "/services"

static int read_sysfs_str(const char *path, char *buf, size_t len)
{
    FILE *f = fopen(path, "r");
    if (!f)
        return -1;

    if (!fgets(buf, len, f)) {
        fclose(f);
        return -1;
    }

    /* Strip trailing newline */
    size_t slen = strlen(buf);
    if (slen > 0 && buf[slen - 1] == '\n')
        buf[slen - 1] = '\0';

    fclose(f);
    return 0;
}

static int read_sysfs_uint(const char *path, unsigned int *val)
{
    char buf[32];
    if (read_sysfs_str(path, buf, sizeof(buf)) < 0)
        return -1;
    *val = (unsigned int)strtoul(buf, NULL, 10);
    return 0;
}

static int output_full(void)
{
    char state[32], governor[32], version[16];
    unsigned int cpu_count, services;

    if (read_sysfs_str(SYSFS_VERSION, version, sizeof(version)) < 0) {
        fprintf(stderr, "Error: Cannot read %s. Is the linux_ai module loaded?\n",
                SYSFS_VERSION);
        return 1;
    }

    read_sysfs_str(SYSFS_STATE, state, sizeof(state));
    read_sysfs_str(SYSFS_GOVERNOR, governor, sizeof(governor));
    read_sysfs_uint(SYSFS_CPU_COUNT, &cpu_count);
    read_sysfs_uint(SYSFS_SERVICES, &services);

    printf("=== Linux-AI Status ===\n");
    printf("Version      : %s\n", version);
    printf("State        : %s\n", state);
    printf("Governor     : %s\n", governor);
    printf("Online CPUs  : %u\n", cpu_count);
    printf("Services     : %u\n", services);

    /* Also show /proc/ai_status if available */
    FILE *proc = fopen(AI_PROC_STATUS, "r");
    if (proc) {
        char line[256];
        printf("\n=== /proc/ai_status ===\n");
        while (fgets(line, sizeof(line), proc))
            fputs(line, stdout);
        fclose(proc);
    }

    return 0;
}

static int output_json(void)
{
    char state[32], governor[32], version[16];
    unsigned int cpu_count, services;

    if (read_sysfs_str(SYSFS_VERSION, version, sizeof(version)) < 0) {
        fprintf(stderr, "{\"error\": \"module not loaded\"}\n");
        return 1;
    }

    read_sysfs_str(SYSFS_STATE, state, sizeof(state));
    read_sysfs_str(SYSFS_GOVERNOR, governor, sizeof(governor));
    read_sysfs_uint(SYSFS_CPU_COUNT, &cpu_count);
    read_sysfs_uint(SYSFS_SERVICES, &services);

    printf("{\n");
    printf("  \"version\": \"%s\",\n", version);
    printf("  \"state\": \"%s\",\n", state);
    printf("  \"governor\": \"%s\",\n", governor);
    printf("  \"cpu_count\": %u,\n", cpu_count);
    printf("  \"services\": %u\n", services);
    printf("}\n");

    return 0;
}

static int output_brief(void)
{
    char state[32], governor[32], version[16];
    unsigned int services;

    if (read_sysfs_str(SYSFS_VERSION, version, sizeof(version)) < 0) {
        printf("linux-ai: not loaded\n");
        return 1;
    }

    read_sysfs_str(SYSFS_STATE, state, sizeof(state));
    read_sysfs_str(SYSFS_GOVERNOR, governor, sizeof(governor));
    read_sysfs_uint(SYSFS_SERVICES, &services);

    printf("linux-ai v%s [%s] gov=%s svc=%u\n",
           version, state, governor, services);

    return 0;
}

int main(int argc, char *argv[])
{
    if (argc > 1 && strcmp(argv[1], "--json") == 0)
        return output_json();

    if (argc > 1 && strcmp(argv[1], "--brief") == 0)
        return output_brief();

    if (argc > 1 && (strcmp(argv[1], "-h") == 0 || strcmp(argv[1], "--help") == 0)) {
        printf("Usage: %s [--json|--brief|-h]\n", argv[0]);
        printf("  (no args)   Full status output\n");
        printf("  --json      JSON formatted output\n");
        printf("  --brief     One-line summary\n");
        return 0;
    }

    return output_full();
}

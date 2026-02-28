/*
 * proc-CPUIO.c - Main entry point for CPU I/O monitoring
 *
 * Optimized for: i7-M640 (2 cores / 4 threads), 8 GB RAM
 *
 * Output modes:
 *   --json     JSON text output (default, human-readable)
 *   --compact  Packed binary output (8-16x smaller, for daemon IPC)
 *
 * Subcommands:
 *   (no args)  - one-shot CPU metrics + I/O stats
 *   monitor    - CPU sensitivity threshold monitor
 *   manager    - CPU governor/turbo manager
 *   buffer     - circular buffer CLI (old format)
 *   cbuffer    - compressed circular buffer with delta encoding
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "cpu_metrics_collector.h"
#include "sentielcpu_io_stats.h"
#include "cpu-sensivity-frogline.h"
#include "cpufreg-inline.h"
#include "cpu-buffer-unit.h"
#include "compressed_buffer.h"

int main(int argc, char *argv[]) {
    /* Check for output mode flags first */
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--compact") == 0) {
            compact_cpu_mode = 1;
        }
    }

    /* Find subcommand (first non-flag argument) */
    const char *subcmd = NULL;
    for (int i = 1; i < argc; i++) {
        if (argv[i][0] != '-') {
            subcmd = argv[i];
            break;
        }
    }

    if (!compact_cpu_mode)
        printf("[proc-CPUIO] Starting (optimized for 2C/4T)...\n");

    if (subcmd == NULL) {
        /* One-shot: collect and display current metrics */
        if (!compact_cpu_mode) {
            printf("\n--- CPU Metrics ---\n");
        }
        init_cpu_metrics_collector();

        if (!compact_cpu_mode) {
            printf("\n--- I/O Stats ---\n");
        }
        init_sentiel_cpu_io_stats();

    } else if (strcmp(subcmd, "monitor") == 0) {
        init_cpu_sensivity_frogline();

    } else if (strcmp(subcmd, "manager") == 0) {
        init_cpufreg_inline();

    } else if (strcmp(subcmd, "buffer") == 0) {
        init_cpu_buffer_unit();

    } else if (strcmp(subcmd, "cbuffer") == 0) {
        /* Compressed buffer demo */
        if (cb_init() != 0) return 1;

        printf("[cbuffer] Compressed buffer ready. Commands: push / stats / list / exit\n");
        char cmd[128];
        while (1) {
            printf("> ");
            if (!fgets(cmd, sizeof(cmd), stdin)) break;
            cmd[strcspn(cmd, "\n")] = 0;

            if (strcmp(cmd, "push") == 0) {
                /* Collect current metrics and push to compressed buffer */
                raw_metrics_t m;
                sleep(1);
                m.cpu_percent = (int)get_cpu_using();
                m.cpu_freq_mhz = get_cpu_freq();
                m.cpu_temp = get_cpu_temp();
                m.io_read_kb = 0;
                m.io_write_kb = 0;
                m.turbo = is_turbo_enabled();
                m.alert = (m.cpu_percent > 80 || m.cpu_temp > 75) ? 1 : 0;
                char pol[64];
                get_current_policy(pol);
                m.governor_id = governor_to_id(pol);

                cb_push(&m);
                printf("Pushed: CPU %d%% %d MHz %dC\n",
                       m.cpu_percent, m.cpu_freq_mhz, m.cpu_temp);
            } else if (strcmp(cmd, "stats") == 0) {
                cb_print_stats();
            } else if (strcmp(cmd, "list") == 0) {
                cb_print_entries();
            } else if (strcmp(cmd, "exit") == 0) {
                break;
            } else {
                printf("Commands: push, stats, list, exit\n");
            }
        }
        cb_destroy();

    } else {
        printf("Usage: %s [--compact] [subcommand]\n", argv[0]);
        printf("  (no args)  - one-shot CPU metrics + I/O stats\n");
        printf("  monitor    - CPU sensitivity threshold monitor\n");
        printf("  manager    - CPU governor/turbo manager\n");
        printf("  buffer     - classic circular buffer CLI\n");
        printf("  cbuffer    - compressed buffer with delta encoding (8x smaller)\n");
        printf("\nFlags:\n");
        printf("  --compact  - binary output (18x smaller than JSON)\n");
        return 1;
    }

    if (!compact_cpu_mode)
        printf("[proc-CPUIO] Done.\n");

    return 0;
}

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stddef.h>

/*
 * sentielcpu_io_stats - Reads real disk I/O statistics from /proc/diskstats
 *
 * Falls back to /proc/self/io for per-process I/O if diskstats is unavailable.
 * Fields read from /proc/diskstats (sector-based, 512 bytes per sector):
 *   - Field 6: sectors read
 *   - Field 10: sectors written
 */

static void print_sentielcpu_io_stats(void) {
    uint64_t total_read_sectors = 0;
    uint64_t total_write_sectors = 0;
    char line[512];
    FILE *fp;

    /* Try /proc/diskstats first (system-wide disk I/O) */
    fp = fopen("/proc/diskstats", "r");
    if (fp != NULL) {
        while (fgets(line, sizeof(line), fp)) {
            unsigned int major, minor;
            char dev_name[64];
            uint64_t rd_sectors, wr_sectors;
            uint64_t dummy;

            /* Parse: major minor name rd_ios rd_merges rd_sectors rd_ticks
               wr_ios wr_merges wr_sectors wr_ticks ... */
            int matched = sscanf(line,
                " %u %u %63s %lu %lu %lu %lu %lu %lu %lu",
                &major, &minor, dev_name,
                &dummy, &dummy, &rd_sectors, &dummy,
                &dummy, &dummy, &wr_sectors);

            if (matched >= 10) {
                /* Skip partitions (minor != 0) to avoid double counting.
                   Only count whole disks like sda, nvme0n1, vda */
                if (minor == 0 ||
                    strncmp(dev_name, "nvme", 4) == 0 ||
                    strncmp(dev_name, "dm-", 3) == 0) {
                    total_read_sectors += rd_sectors;
                    total_write_sectors += wr_sectors;
                }
            }
        }
        fclose(fp);

        /* Convert sectors (512 bytes each) to bytes */
        uint64_t read_bytes = total_read_sectors * 512;
        uint64_t write_bytes = total_write_sectors * 512;

        printf("read: %lu\nwrite: %lu\n", read_bytes, write_bytes);
        return;
    }

    /* Fallback: /proc/self/io (per-process I/O) */
    fp = fopen("/proc/self/io", "r");
    if (fp != NULL) {
        uint64_t read_bytes = 0, write_bytes = 0;
        while (fgets(line, sizeof(line), fp)) {
            if (strncmp(line, "read_bytes:", 11) == 0) {
                sscanf(line + 11, " %lu", &read_bytes);
            } else if (strncmp(line, "write_bytes:", 12) == 0) {
                sscanf(line + 12, " %lu", &write_bytes);
            }
        }
        fclose(fp);
        printf("read: %lu\nwrite: %lu\n", read_bytes, write_bytes);
        return;
    }

    /* No I/O source available */
    fprintf(stderr, "[sentielcpu_io_stats] Warning: Cannot read /proc/diskstats or /proc/self/io\n");
    printf("read: 0\nwrite: 0\n");
}

void init_sentiel_cpu_io_stats(void) {
    print_sentielcpu_io_stats();
}

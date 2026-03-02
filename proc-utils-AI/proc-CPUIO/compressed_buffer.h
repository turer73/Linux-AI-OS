/*
 * compressed_buffer.h - Bit-packed circular buffer with delta encoding
 *
 * Standard buffer_entry:  144 bytes (timespec=16 + data[128])
 * Packed entry:            16 bytes (8x compression)
 *
 * Layout per packed_entry (16 bytes total):
 *   timestamp_ms : 32 bits  (relative to buffer start, wraps at ~49 days)
 *   cpu_percent  :  7 bits  (0-100)
 *   cpu_freq_mhz : 12 bits  (0-4095 MHz, enough for i7-M640 @ 2.8 GHz)
 *   cpu_temp     :  7 bits  (0-127 C)
 *   io_read_kb   : 20 bits  (0-1048575 KB = ~1 GB delta per sample)
 *   io_write_kb  : 20 bits  (0-1048575 KB)
 *   flags        :  6 bits  (governor_id:3, turbo:1, alert:1, reserved:1)
 *   delta_mode   :  1 bit   (0=absolute, 1=delta from previous)
 *   reserved     : 23 bits
 *                 --------
 *                 128 bits = 16 bytes
 *
 * Delta encoding: When delta_mode=1, cpu_percent/freq/temp/io values
 * store signed differences from previous entry. This typically reduces
 * values to near-zero, enabling future variable-length encoding.
 *
 * Governor IDs: 0=unknown, 1=performance, 2=powersave, 3=schedutil,
 *               4=ondemand, 5=conservative, 6=userspace, 7=ai-adaptive
 */

#ifndef COMPRESSED_BUFFER_H
#define COMPRESSED_BUFFER_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#include <pthread.h>
#include "governor_ids.h"

#define CB_MAX_ENTRIES 128   /* 128 * 16 = 2048 bytes total (vs 128*144 = 18 KB) */
#define CB_CONFIG_PATH "/var/AI-stump/AI-runtime.yml"

/* 16-byte packed entry (verified by static assert below) */
typedef struct __attribute__((packed)) {
    uint32_t timestamp_ms;     /* relative ms from epoch_ms */
    uint8_t  cpu_percent;      /* 0-100 (7 bits used, 1 bit for delta flag) */
    uint16_t cpu_freq_mhz;     /* 0-4095 (12 bits) + temp high nibble */
    uint8_t  cpu_temp;         /* 0-127 */
    uint8_t  io_packed[5];     /* 2x 20-bit IO values packed into 5 bytes */
    uint8_t  flags;            /* governor:3 | turbo:1 | alert:1 | delta:1 | rsv:2 */
    uint8_t  reserved[2];      /* pad to exactly 16 bytes */
} packed_entry_t;

_Static_assert(sizeof(packed_entry_t) == 16, "packed_entry_t must be 16 bytes");

/* Pack two 20-bit IO values into 5 bytes */
static inline void cb_set_io(packed_entry_t *e, uint32_t read_kb, uint32_t write_kb) {
    read_kb  &= 0xFFFFF;  /* clamp to 20 bits */
    write_kb &= 0xFFFFF;
    e->io_packed[0] = (uint8_t)(read_kb >> 12);
    e->io_packed[1] = (uint8_t)(read_kb >> 4);
    e->io_packed[2] = (uint8_t)((read_kb & 0xF) << 4) | (uint8_t)(write_kb >> 16);
    e->io_packed[3] = (uint8_t)(write_kb >> 8);
    e->io_packed[4] = (uint8_t)(write_kb);
}

static inline uint32_t cb_get_read_kb(const packed_entry_t *e) {
    return ((uint32_t)e->io_packed[0] << 12)
         | ((uint32_t)e->io_packed[1] << 4)
         | ((uint32_t)e->io_packed[2] >> 4);
}

static inline uint32_t cb_get_write_kb(const packed_entry_t *e) {
    return ((uint32_t)(e->io_packed[2] & 0x0F) << 16)
         | ((uint32_t)e->io_packed[3] << 8)
         | ((uint32_t)e->io_packed[4]);
}

/* Uncompressed metrics for easy population */
typedef struct {
    int      cpu_percent;      /* 0-100 */
    int      cpu_freq_mhz;    /* 0-4095 */
    int      cpu_temp;         /* 0-127 */
    uint32_t io_read_kb;       /* delta or absolute (20-bit range) */
    uint32_t io_write_kb;
    int      governor_id;      /* 0-7 */
    int      turbo;            /* 0 or 1 */
    int      alert;            /* 0 or 1 */
} raw_metrics_t;

/* Compressed circular buffer state */
static packed_entry_t *cb_entries = NULL;
static int cb_write_idx = 0;
static int cb_count = 0;
static int cb_max = 64;
static uint64_t cb_epoch_ms = 0;
static raw_metrics_t cb_prev_metrics;
static int cb_has_prev = 0;
static pthread_mutex_t cb_lock = PTHREAD_MUTEX_INITIALIZER;

/* Governor mapping now in governor_ids.h (single source of truth) */

static uint64_t get_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

/* Clamp helpers */
static inline uint8_t  clamp8(int v, int lo, int hi)  { return (uint8_t)(v < lo ? lo : (v > hi ? hi : v)); }
static inline uint16_t clamp16(int v, int lo, int hi)  { return (uint16_t)(v < lo ? lo : (v > hi ? hi : v)); }
static inline uint32_t clamp32(uint32_t v, uint32_t hi) { return v > hi ? hi : v; }

int cb_init(void) {
    /* Allocate at runtime size instead of CB_MAX_ENTRIES (50% savings) */
    cb_entries = (packed_entry_t *)calloc(cb_max, sizeof(packed_entry_t));
    if (!cb_entries) {
        perror("[compressed_buffer] alloc failed");
        return -1;
    }

    cb_epoch_ms = get_ms();
    cb_has_prev = 0;
    cb_write_idx = 0;
    cb_count = 0;

    size_t total_bytes = cb_max * sizeof(packed_entry_t);
    printf("[compressed_buffer] Init: %d entries x %zu bytes = %zu bytes total\n",
           cb_max, sizeof(packed_entry_t), total_bytes);
    printf("[compressed_buffer] Compression: 144 -> %zu bytes/entry (%.1fx)\n",
           sizeof(packed_entry_t), 144.0 / sizeof(packed_entry_t));

    return 0;
}

void cb_push(const raw_metrics_t *m) {
    pthread_mutex_lock(&cb_lock);

    packed_entry_t e;
    memset(&e, 0, sizeof(e));

    e.timestamp_ms = (uint32_t)(get_ms() - cb_epoch_ms);
    e.flags = 0;

    if (cb_has_prev) {
        /* Delta encoding: store differences from previous */
        int d_cpu  = m->cpu_percent  - cb_prev_metrics.cpu_percent;
        int d_freq = m->cpu_freq_mhz - cb_prev_metrics.cpu_freq_mhz;
        int d_temp = m->cpu_temp     - cb_prev_metrics.cpu_temp;
        int32_t d_rd = (int32_t)m->io_read_kb  - (int32_t)cb_prev_metrics.io_read_kb;
        int32_t d_wr = (int32_t)m->io_write_kb - (int32_t)cb_prev_metrics.io_write_kb;

        /* Use delta if values fit in smaller range (common case) */
        if (d_cpu >= -50 && d_cpu <= 50 &&
            d_freq >= -2000 && d_freq <= 2000 &&
            d_temp >= -30 && d_temp <= 30) {
            e.cpu_percent  = clamp8(d_cpu + 50, 0, 100);   /* offset by 50 */
            e.cpu_freq_mhz = clamp16(d_freq + 2048, 0, 4095);
            e.cpu_temp     = clamp8(d_temp + 63, 0, 127);
            cb_set_io(&e,
                      clamp32((uint32_t)(d_rd < 0 ? 0 : d_rd), 1048575),
                      clamp32((uint32_t)(d_wr < 0 ? 0 : d_wr), 1048575));
            e.flags |= (1 << 5); /* delta_mode = 1 */
        } else {
            /* Absolute values (delta too large) */
            e.cpu_percent  = clamp8(m->cpu_percent, 0, 100);
            e.cpu_freq_mhz = clamp16(m->cpu_freq_mhz, 0, 4095);
            e.cpu_temp     = clamp8(m->cpu_temp, 0, 127);
            cb_set_io(&e,
                      clamp32(m->io_read_kb, 1048575),
                      clamp32(m->io_write_kb, 1048575));
        }
    } else {
        /* First entry: always absolute */
        e.cpu_percent  = clamp8(m->cpu_percent, 0, 100);
        e.cpu_freq_mhz = clamp16(m->cpu_freq_mhz, 0, 4095);
        e.cpu_temp     = clamp8(m->cpu_temp, 0, 127);
        cb_set_io(&e,
                  clamp32(m->io_read_kb, 1048575),
                  clamp32(m->io_write_kb, 1048575));
    }

    e.flags |= (m->governor_id & 0x7);         /* bits 0-2: governor */
    e.flags |= (m->turbo ? (1 << 3) : 0);      /* bit 3: turbo */
    e.flags |= (m->alert ? (1 << 4) : 0);      /* bit 4: alert */

    /* Write to circular buffer */
    cb_entries[cb_write_idx] = e;
    cb_write_idx = (cb_write_idx + 1) % cb_max;
    if (cb_count < cb_max) cb_count++;

    /* Store for next delta */
    cb_prev_metrics = *m;
    cb_has_prev = 1;

    pthread_mutex_unlock(&cb_lock);
}

void cb_print_stats(void) {
    pthread_mutex_lock(&cb_lock);

    int delta_count = 0;
    for (int i = 0; i < cb_count; i++) {
        if (cb_entries[i].flags & (1 << 5))
            delta_count++;
    }

    size_t used_bytes = cb_count * sizeof(packed_entry_t);
    size_t old_bytes  = cb_count * 144;  /* old buffer_entry size */
    float ratio = old_bytes > 0 ? (float)old_bytes / used_bytes : 0;

    printf("[compressed_buffer] Entries: %d/%d\n", cb_count, cb_max);
    printf("[compressed_buffer] Memory: %zu bytes (was %zu bytes, %.1fx compression)\n",
           used_bytes, old_bytes, ratio);
    printf("[compressed_buffer] Delta-encoded: %d/%d (%.0f%%)\n",
           delta_count, cb_count,
           cb_count > 0 ? (float)delta_count / cb_count * 100 : 0);

    pthread_mutex_unlock(&cb_lock);
}

void cb_print_entries(void) {
    pthread_mutex_lock(&cb_lock);

    /* Reconstruct absolute values from deltas for display */
    raw_metrics_t reconstructed;
    memset(&reconstructed, 0, sizeof(reconstructed));

    int start = (cb_count < cb_max) ? 0 : cb_write_idx;
    for (int n = 0; n < cb_count; n++) {
        int idx = (start + n) % cb_max;
        packed_entry_t *e = &cb_entries[idx];

        int is_delta = (e->flags >> 5) & 1;
        int gov_id   = e->flags & 0x7;
        int turbo    = (e->flags >> 3) & 1;
        int alert    = (e->flags >> 4) & 1;

        int cpu, freq, temp;
        uint32_t rd, wr;

        uint32_t e_rd = cb_get_read_kb(e);
        uint32_t e_wr = cb_get_write_kb(e);

        if (is_delta) {
            cpu  = (int)e->cpu_percent - 50 + reconstructed.cpu_percent;
            freq = (int)e->cpu_freq_mhz - 2048 + reconstructed.cpu_freq_mhz;
            temp = (int)e->cpu_temp - 63 + reconstructed.cpu_temp;
            rd   = e_rd + reconstructed.io_read_kb;
            wr   = e_wr + reconstructed.io_write_kb;
        } else {
            cpu  = e->cpu_percent;
            freq = e->cpu_freq_mhz;
            temp = e->cpu_temp;
            rd   = e_rd;
            wr   = e_wr;
        }

        reconstructed.cpu_percent  = cpu;
        reconstructed.cpu_freq_mhz = freq;
        reconstructed.cpu_temp     = temp;
        reconstructed.io_read_kb   = rd;
        reconstructed.io_write_kb  = wr;

        printf("[%3d] %8u ms | CPU:%3d%% %4d MHz %3dC | IO R:%u W:%u KB | %s%s%s\n",
               n, e->timestamp_ms,
               cpu, freq, temp, rd, wr,
               id_to_governor(gov_id),
               turbo ? " TURBO" : "",
               alert ? " ALERT" : "");
    }

    pthread_mutex_unlock(&cb_lock);
}

void cb_destroy(void) {
    if (cb_entries) {
        free(cb_entries);
        cb_entries = NULL;
    }
}

#endif /* COMPRESSED_BUFFER_H */

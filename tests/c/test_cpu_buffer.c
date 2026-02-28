/**
 * test_cpu_buffer.c - Tests for CPU buffer unit structures
 *
 * Compile: gcc -o test_cpu_buffer test_cpu_buffer.c -I../../proc-utils-AI/proc-CPUIO
 * Run:     ./test_cpu_buffer
 */

#include "test_framework.h"
#include <stdlib.h>

/* Minimal struct definitions matching cpu-buffer-unit.h logic */
typedef struct {
    float cpu_usage;
    float cpu_temp;
    int   cpu_freq_mhz;
    int   core_count;
} cpu_snapshot_t;

typedef struct {
    cpu_snapshot_t snapshots[64];
    int count;
    int capacity;
} cpu_buffer_t;

static void cpu_buffer_init(cpu_buffer_t *buf, int capacity) {
    buf->count = 0;
    buf->capacity = (capacity > 64) ? 64 : capacity;
}

static int cpu_buffer_push(cpu_buffer_t *buf, cpu_snapshot_t snapshot) {
    if (buf->count >= buf->capacity) return -1;
    buf->snapshots[buf->count++] = snapshot;
    return 0;
}

static cpu_snapshot_t *cpu_buffer_get(cpu_buffer_t *buf, int index) {
    if (index < 0 || index >= buf->count) return NULL;
    return &buf->snapshots[index];
}

/* Tests */

TEST(buffer_init) {
    cpu_buffer_t buf;
    cpu_buffer_init(&buf, 32);
    ASSERT_EQ(0, buf.count);
    ASSERT_EQ(32, buf.capacity);
}

TEST(buffer_push) {
    cpu_buffer_t buf;
    cpu_buffer_init(&buf, 4);
    cpu_snapshot_t snap = {45.5f, 55.0f, 3600, 8};
    int rc = cpu_buffer_push(&buf, snap);
    ASSERT_EQ(0, rc);
    ASSERT_EQ(1, buf.count);
}

TEST(buffer_push_overflow) {
    cpu_buffer_t buf;
    cpu_buffer_init(&buf, 2);
    cpu_snapshot_t snap = {0};
    cpu_buffer_push(&buf, snap);
    cpu_buffer_push(&buf, snap);
    int rc = cpu_buffer_push(&buf, snap);
    ASSERT_EQ(-1, rc);
    ASSERT_EQ(2, buf.count);
}

TEST(buffer_get_valid) {
    cpu_buffer_t buf;
    cpu_buffer_init(&buf, 8);
    cpu_snapshot_t snap = {72.3f, 65.0f, 2400, 4};
    cpu_buffer_push(&buf, snap);
    cpu_snapshot_t *result = cpu_buffer_get(&buf, 0);
    ASSERT_NOT_NULL(result);
    ASSERT(result->cpu_freq_mhz == 2400);
    ASSERT(result->core_count == 4);
}

TEST(buffer_get_out_of_bounds) {
    cpu_buffer_t buf;
    cpu_buffer_init(&buf, 8);
    cpu_snapshot_t *result = cpu_buffer_get(&buf, 0);
    ASSERT(result == NULL);
    result = cpu_buffer_get(&buf, -1);
    ASSERT(result == NULL);
}

TEST(buffer_capacity_clamped) {
    cpu_buffer_t buf;
    cpu_buffer_init(&buf, 1000);
    ASSERT_EQ(64, buf.capacity);
}

int main(void) {
    printf("=== CPU Buffer Unit Tests ===\n\n");
    RUN_TEST(buffer_init);
    RUN_TEST(buffer_push);
    RUN_TEST(buffer_push_overflow);
    RUN_TEST(buffer_get_valid);
    RUN_TEST(buffer_get_out_of_bounds);
    RUN_TEST(buffer_capacity_clamped);
    TEST_REPORT();
    return test_failures;
}

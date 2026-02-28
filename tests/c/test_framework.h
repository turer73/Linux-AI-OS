/**
 * test_framework.h - Minimal C test framework for Linux-AI
 *
 * Usage:
 *   TEST(test_name) {
 *       ASSERT(condition);
 *       ASSERT_EQ(expected, actual);
 *       ASSERT_STR_EQ(expected, actual);
 *   }
 *
 *   int main(void) {
 *       RUN_TEST(test_name);
 *       TEST_REPORT();
 *       return test_failures;
 *   }
 */

#ifndef AI_TEST_FRAMEWORK_H
#define AI_TEST_FRAMEWORK_H

#include <stdio.h>
#include <string.h>

static int test_count = 0;
static int test_failures = 0;
static int test_current_failed = 0;

#define TEST(name) static void test_##name(void)

#define RUN_TEST(name) do { \
    test_count++; \
    test_current_failed = 0; \
    printf("  [RUN ] %s ...", #name); \
    test_##name(); \
    if (test_current_failed) { \
        printf(" FAIL\n"); \
    } else { \
        printf(" OK\n"); \
    } \
} while(0)

#define ASSERT(cond) do { \
    if (!(cond)) { \
        printf("\n    ASSERT FAILED: %s (line %d)\n", #cond, __LINE__); \
        test_failures++; \
        test_current_failed = 1; \
        return; \
    } \
} while(0)

#define ASSERT_EQ(expected, actual) do { \
    long long _e = (long long)(expected); \
    long long _a = (long long)(actual); \
    if (_e != _a) { \
        printf("\n    ASSERT_EQ FAILED: expected %lld, got %lld (line %d)\n", _e, _a, __LINE__); \
        test_failures++; \
        test_current_failed = 1; \
        return; \
    } \
} while(0)

#define ASSERT_NEQ(val1, val2) do { \
    long long _v1 = (long long)(val1); \
    long long _v2 = (long long)(val2); \
    if (_v1 == _v2) { \
        printf("\n    ASSERT_NEQ FAILED: both are %lld (line %d)\n", _v1, __LINE__); \
        test_failures++; \
        test_current_failed = 1; \
        return; \
    } \
} while(0)

#define ASSERT_STR_EQ(expected, actual) do { \
    if (strcmp((expected), (actual)) != 0) { \
        printf("\n    ASSERT_STR_EQ FAILED: expected \"%s\", got \"%s\" (line %d)\n", \
               (expected), (actual), __LINE__); \
        test_failures++; \
        test_current_failed = 1; \
        return; \
    } \
} while(0)

#define ASSERT_NOT_NULL(ptr) do { \
    if ((ptr) == NULL) { \
        printf("\n    ASSERT_NOT_NULL FAILED: got NULL (line %d)\n", __LINE__); \
        test_failures++; \
        test_current_failed = 1; \
        return; \
    } \
} while(0)

#define TEST_REPORT() do { \
    printf("\n========================================\n"); \
    printf("  Tests: %d | Passed: %d | Failed: %d\n", \
           test_count, test_count - test_failures, test_failures); \
    printf("========================================\n"); \
} while(0)

#endif /* AI_TEST_FRAMEWORK_H */

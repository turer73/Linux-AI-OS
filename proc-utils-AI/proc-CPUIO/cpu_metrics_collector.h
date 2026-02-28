#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdint.h>

#define MAX_BUF 256

typedef struct {
    float cpu_using;
    int cpu_freq_mhz;
    int cpu_temp_celsius;
    char policy[64];
    int turbo_enabled;
} cpu_metrics_t;

/*
 * Compact binary CPU metrics (8 bytes vs ~150 bytes JSON = 18x compression)
 */
typedef struct __attribute__((packed)) {
    uint8_t  cpu_percent;     /* 0-100 */
    uint16_t cpu_freq_mhz;   /* 0-65535 */
    uint8_t  cpu_temp;        /* 0-255 */
    uint8_t  gov_turbo;       /* governor:3 | turbo:1 | reserved:4 */
    uint8_t  reserved[3];
} cpu_compact_t;

static int compact_cpu_mode = 0;

static int policy_to_id(const char *p) {
    if (strcmp(p, "performance") == 0)   return 1;
    if (strcmp(p, "powersave") == 0)     return 2;
    if (strcmp(p, "schedutil") == 0)     return 3;
    if (strcmp(p, "ondemand") == 0)      return 4;
    if (strcmp(p, "conservative") == 0)  return 5;
    return 0;
}

static void print_compact_metrics(cpu_metrics_t *m) {
    cpu_compact_t c;
    memset(&c, 0, sizeof(c));
    c.cpu_percent  = (uint8_t)(m->cpu_using > 100 ? 100 : (m->cpu_using < 0 ? 0 : (int)m->cpu_using));
    c.cpu_freq_mhz = (uint16_t)(m->cpu_freq_mhz > 65535 ? 65535 : m->cpu_freq_mhz);
    c.cpu_temp     = (uint8_t)(m->cpu_temp_celsius > 255 ? 255 : (m->cpu_temp_celsius < 0 ? 0 : m->cpu_temp_celsius));
    c.gov_turbo    = (uint8_t)((policy_to_id(m->policy) & 0x7) | ((m->turbo_enabled ? 1 : 0) << 3));
    fwrite(&c, sizeof(c), 1, stdout);
    fflush(stdout);
}

float get_cpu_using() {
    FILE* fp;
    char buf[MAX_BUF];
    unsigned long long int user, nice, system, idle;
    static unsigned long long int prev_total = 0, prev_idle = 0;
    unsigned long long int total, diff_idle, diff_total;

    fp = fopen("/proc/stat", "r");
    if (!fp) return -1;

    fgets(buf, MAX_BUF, fp);
    sscanf(buf, "cpu %llu %llu %llu %llu", &user, &nice, &system, &idle);
    fclose(fp);

    total = user + nice + system + idle;
    diff_idle = idle - prev_idle;
    diff_total = total - prev_total;

    prev_total = total;
    prev_idle = idle;

    if (diff_total == 0) return 0.0;
    return 100.0 * (1.0 - ((float)diff_idle / diff_total));
}

int get_cpu_freq() {
    FILE* fp;
    char buf[MAX_BUF];
    int freq = 0;

    fp = fopen("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", "r");
    if (fp) {
        fgets(buf, MAX_BUF, fp);
        freq = atoi(buf) / 1000; // kHz to MHz
        fclose(fp);
    }

    return freq;
}

int get_cpu_temp() {
    FILE* fp;
    char path[MAX_BUF];
    char buf[MAX_BUF];
    int temp = -1;

    // Genelde thermal_zone0 temp dosyası olur
    snprintf(path, MAX_BUF, "/sys/class/thermal/thermal_zone0/temp");
    fp = fopen(path, "r");
    if (fp) {
        fgets(buf, MAX_BUF, fp);
        temp = atoi(buf) / 1000;
        fclose(fp);
    }

    return temp;
}

void get_current_policy(char* policy_out) {
    FILE* fp;
    char buf[MAX_BUF];

    fp = fopen("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "r");
    if (fp) {
        fgets(buf, MAX_BUF, fp);
        buf[strcspn(buf, "\n")] = 0; // remove newline
        strcpy(policy_out, buf);
        fclose(fp);
    } else {
        strcpy(policy_out, "unknown");
    }
}

int is_turbo_enabled() {
    FILE* fp;
    char buf[MAX_BUF];

    fp = fopen("/sys/devices/system/cpu/intel_pstate/no_turbo", "r");
    if (!fp) return -1;

    fgets(buf, MAX_BUF, fp);
    fclose(fp);

    return atoi(buf) == 0; // 0 means turbo is ON
}

void print_metrics(cpu_metrics_t* metrics) {
    printf("{\n");
    printf("  \"cpu_usage\": %.2f,\n", metrics->cpu_using);
    printf("  \"cpu_freq_mhz\": %d,\n", metrics->cpu_freq_mhz);
    printf("  \"cpu_temp_celsius\": %d,\n", metrics->cpu_temp_celsius);
    printf("  \"policy\": \"%s\",\n", metrics->policy);
    printf("  \"turbo_enabled\": %s\n", metrics->turbo_enabled ? "true" : "false");
    printf("}\n");
}

int init_cpu_metrics_collector(void){
    cpu_metrics_t metrics;

    sleep(1); /* ilk olcum oncesi stabilite icin */
    metrics.cpu_using = get_cpu_using();
    metrics.cpu_freq_mhz = get_cpu_freq();
    metrics.cpu_temp_celsius = get_cpu_temp();
    get_current_policy(metrics.policy);
    metrics.turbo_enabled = is_turbo_enabled();

    if (compact_cpu_mode) {
        print_compact_metrics(&metrics);  /* 8 bytes binary */
    } else {
        print_metrics(&metrics);          /* JSON text */
    }

    return 0;
}

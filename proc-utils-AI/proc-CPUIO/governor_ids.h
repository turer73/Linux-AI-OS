/*
 * governor_ids.h - Single source of truth for governor ID mapping
 *
 * IDs: 0=unknown, 1=performance, 2=powersave, 3=schedutil,
 *      4=ondemand, 5=conservative, 6=userspace, 7=ai-adaptive
 *
 * Used by: compressed_buffer.h, cpu_metrics_collector.h
 */

#ifndef GOVERNOR_IDS_H
#define GOVERNOR_IDS_H

#include <string.h>

static inline int governor_to_id(const char *gov) {
    if (!gov) return 0;
    if (strcmp(gov, "performance") == 0)   return 1;
    if (strcmp(gov, "powersave") == 0)     return 2;
    if (strcmp(gov, "schedutil") == 0)     return 3;
    if (strcmp(gov, "ondemand") == 0)      return 4;
    if (strcmp(gov, "conservative") == 0)  return 5;
    if (strcmp(gov, "userspace") == 0)     return 6;
    if (strcmp(gov, "ai-adaptive") == 0)   return 7;
    return 0;
}

static inline const char* id_to_governor(int id) {
    switch (id) {
        case 1: return "performance";
        case 2: return "powersave";
        case 3: return "schedutil";
        case 4: return "ondemand";
        case 5: return "conservative";
        case 6: return "userspace";
        case 7: return "ai-adaptive";
        default: return "unknown";
    }
}

#endif /* GOVERNOR_IDS_H */

// SPDX-License-Identifier: GPL-2.0-only
/*
 * ai_sysfs.c - /sys/ai interface for Linux-AI
 *
 * Creates a kobject under /sys/ai/ with attributes:
 *   /sys/ai/state       - Module state (read/write)
 *   /sys/ai/governor    - Governor mode (read/write)
 *   /sys/ai/version     - Module version (read-only)
 *   /sys/ai/cpu_count   - Online CPU count (read-only)
 *   /sys/ai/services    - Active service count (read-only)
 *
 * Copyright (C) 2026 Zaman Huseyinli
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/kobject.h>
#include <linux/sysfs.h>
#include <linux/string.h>
#include <linux/mutex.h>

#include "../include/ai_common.h"

/* External references to core module */
extern struct ai_system_status *ai_get_status(void);
extern struct mutex *ai_get_mutex(void);
extern int ai_get_debug(void);
extern int ai_check_permission(unsigned int required);

static struct kobject *ai_kobj;

static const char *governor_str[] = {
    "performance", "powersave", "ondemand", "conservative", "ai-adaptive"
};

static const char *state_str[] = {
    "stopped", "running", "training", "error"
};

/*
 * /sys/ai/version (read-only)
 */
static ssize_t version_show(struct kobject *kobj, struct kobj_attribute *attr,
                             char *buf)
{
    return sysfs_emit(buf, "%s\n", AI_MODULE_VERSION);
}
static struct kobj_attribute version_attr = __ATTR_RO(version);

/*
 * /sys/ai/state (read/write)
 */
static ssize_t state_show(struct kobject *kobj, struct kobj_attribute *attr,
                           char *buf)
{
    struct ai_system_status *st = ai_get_status();
    struct mutex *mtx = ai_get_mutex();
    ssize_t len;

    mutex_lock(mtx);
    if (st->state <= AI_STATE_ERROR)
        len = sysfs_emit(buf, "%s\n", state_str[st->state]);
    else
        len = sysfs_emit(buf, "unknown\n");
    mutex_unlock(mtx);

    return len;
}

static ssize_t state_store(struct kobject *kobj, struct kobj_attribute *attr,
                            const char *buf, size_t count)
{
    struct ai_system_status *st = ai_get_status();
    struct mutex *mtx = ai_get_mutex();
    int i;

    if (ai_check_permission(AI_PERM_ADMIN))
        return -EPERM;

    for (i = 0; i <= AI_STATE_ERROR; i++) {
        if (sysfs_streq(buf, state_str[i])) {
            mutex_lock(mtx);
            st->state = i;
            mutex_unlock(mtx);
            return count;
        }
    }

    return -EINVAL;
}
static struct kobj_attribute state_attr = __ATTR_RW(state);

/*
 * /sys/ai/governor (read/write)
 */
static ssize_t governor_show(struct kobject *kobj, struct kobj_attribute *attr,
                              char *buf)
{
    struct ai_system_status *st = ai_get_status();
    struct mutex *mtx = ai_get_mutex();
    ssize_t len;

    mutex_lock(mtx);
    if (st->governor <= AI_GOV_AI_ADAPTIVE)
        len = sysfs_emit(buf, "%s\n", governor_str[st->governor]);
    else
        len = sysfs_emit(buf, "unknown\n");
    mutex_unlock(mtx);

    return len;
}

static ssize_t governor_store(struct kobject *kobj, struct kobj_attribute *attr,
                               const char *buf, size_t count)
{
    struct ai_system_status *st = ai_get_status();
    struct mutex *mtx = ai_get_mutex();
    int i;

    if (ai_check_permission(AI_PERM_ADMIN))
        return -EPERM;

    for (i = 0; i <= AI_GOV_AI_ADAPTIVE; i++) {
        if (sysfs_streq(buf, governor_str[i])) {
            mutex_lock(mtx);
            st->governor = i;
            mutex_unlock(mtx);

            if (ai_get_debug())
                pr_info("linux_ai: governor set to '%s' via sysfs\n",
                        governor_str[i]);
            return count;
        }
    }

    return -EINVAL;
}
static struct kobj_attribute governor_attr = __ATTR_RW(governor);

/*
 * /sys/ai/cpu_count (read-only)
 */
static ssize_t cpu_count_show(struct kobject *kobj, struct kobj_attribute *attr,
                               char *buf)
{
    struct ai_system_status *st = ai_get_status();

    return sysfs_emit(buf, "%u\n", st->cpu_count);
}
static struct kobj_attribute cpu_count_attr = __ATTR_RO(cpu_count);

/*
 * /sys/ai/services (read-only)
 */
static ssize_t services_show(struct kobject *kobj, struct kobj_attribute *attr,
                              char *buf)
{
    struct ai_system_status *st = ai_get_status();
    struct mutex *mtx = ai_get_mutex();
    ssize_t len;

    mutex_lock(mtx);
    len = sysfs_emit(buf, "%u\n", st->active_services);
    mutex_unlock(mtx);

    return len;
}
static struct kobj_attribute services_attr = __ATTR_RO(services);

/*
 * Attribute group
 */
static struct attribute *ai_attrs[] = {
    &version_attr.attr,
    &state_attr.attr,
    &governor_attr.attr,
    &cpu_count_attr.attr,
    &services_attr.attr,
    NULL,
};

static struct attribute_group ai_attr_group = {
    .attrs = ai_attrs,
};

/*
 * Init/Exit
 */
int ai_sysfs_init(void)
{
    int ret;

    ai_kobj = kobject_create_and_add("ai", NULL);
    if (!ai_kobj)
        return -ENOMEM;

    ret = sysfs_create_group(ai_kobj, &ai_attr_group);
    if (ret) {
        kobject_put(ai_kobj);
        return ret;
    }

    pr_info("linux_ai: sysfs entries created at /sys/ai/\n");
    return 0;
}

void ai_sysfs_exit(void)
{
    sysfs_remove_group(ai_kobj, &ai_attr_group);
    kobject_put(ai_kobj);
    pr_info("linux_ai: sysfs entries removed\n");
}

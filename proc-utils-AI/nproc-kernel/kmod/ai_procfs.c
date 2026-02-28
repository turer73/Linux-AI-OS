// SPDX-License-Identifier: GPL-2.0-only
/*
 * ai_procfs.c - /proc interface for Linux-AI
 *
 * Creates:
 *   /proc/ai_status - Read-only system status (human-readable)
 *   /proc/ai_config - Read/write configuration interface
 *
 * Copyright (C) 2026 Zaman Huseyinli
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/proc_fs.h>
#include <linux/seq_file.h>
#include <linux/uaccess.h>
#include <linux/mutex.h>
#include <linux/sched.h>
#include <linux/cpufreq.h>

#include "../include/ai_common.h"
#include "../include/ai_ioctl.h"

/* External references to core module */
extern struct ai_system_status *ai_get_status(void);
extern struct mutex *ai_get_mutex(void);
extern int ai_get_debug(void);
extern int ai_check_permission(unsigned int required);

static struct proc_dir_entry *proc_ai_status;
static struct proc_dir_entry *proc_ai_config;

/*
 * /proc/ai_status - Read-only system status
 */

static const char *governor_names[] = {
    [AI_GOV_PERFORMANCE]  = "performance",
    [AI_GOV_POWERSAVE]    = "powersave",
    [AI_GOV_ONDEMAND]     = "ondemand",
    [AI_GOV_CONSERVATIVE] = "conservative",
    [AI_GOV_AI_ADAPTIVE]  = "ai-adaptive",
};

static const char *state_names[] = {
    [AI_STATE_STOPPED]  = "stopped",
    [AI_STATE_RUNNING]  = "running",
    [AI_STATE_TRAINING] = "training",
    [AI_STATE_ERROR]    = "error",
};

static int ai_status_show(struct seq_file *m, void *v)
{
    struct ai_system_status *st = ai_get_status();
    struct mutex *mtx = ai_get_mutex();
    int cpu;

    mutex_lock(mtx);

    seq_printf(m, "=== Linux-AI Status ===\n");
    seq_printf(m, "Version      : %s\n", st->version);
    seq_printf(m, "State        : %s\n",
               st->state <= AI_STATE_ERROR ? state_names[st->state] : "unknown");
    seq_printf(m, "Governor     : %s\n",
               st->governor <= AI_GOV_AI_ADAPTIVE ? governor_names[st->governor] : "unknown");
    seq_printf(m, "Online CPUs  : %u\n", st->cpu_count);
    seq_printf(m, "Services     : %u\n", st->active_services);
    seq_printf(m, "Perm Level   : 0x%02x\n", st->perm_level);
    seq_printf(m, "\n");

    /* Per-CPU info from kernel */
    seq_printf(m, "=== CPU Frequencies ===\n");
    for_each_online_cpu(cpu) {
        unsigned int freq = cpufreq_quick_get(cpu);
        seq_printf(m, "CPU%-3d : %u MHz\n", cpu, freq / 1000);
    }

    mutex_unlock(mtx);
    return 0;
}

static int ai_status_open(struct inode *inode, struct file *file)
{
    return single_open(file, ai_status_show, NULL);
}

static const struct proc_ops ai_status_ops = {
    .proc_open    = ai_status_open,
    .proc_read    = seq_read,
    .proc_lseek   = seq_lseek,
    .proc_release = single_release,
};

/*
 * /proc/ai_config - Read/write configuration
 *
 * Read:  Outputs current configuration values
 * Write: Accepts "key=value" pairs to modify config
 *        Supported keys: governor, debug, state
 */

static int ai_config_show(struct seq_file *m, void *v)
{
    struct ai_system_status *st = ai_get_status();
    struct mutex *mtx = ai_get_mutex();

    mutex_lock(mtx);
    seq_printf(m, "governor=%s\n",
               st->governor <= AI_GOV_AI_ADAPTIVE ? governor_names[st->governor] : "unknown");
    seq_printf(m, "state=%s\n",
               st->state <= AI_STATE_ERROR ? state_names[st->state] : "unknown");
    seq_printf(m, "debug=%d\n", ai_get_debug());
    seq_printf(m, "cpu_count=%u\n", st->cpu_count);
    seq_printf(m, "services=%u\n", st->active_services);
    mutex_unlock(mtx);

    return 0;
}

static int ai_config_open(struct inode *inode, struct file *file)
{
    return single_open(file, ai_config_show, NULL);
}

static ssize_t ai_config_write(struct file *file, const char __user *ubuf,
                                size_t count, loff_t *ppos)
{
    struct ai_system_status *st = ai_get_status();
    struct mutex *mtx = ai_get_mutex();
    char buf[AI_CMD_MAX_LEN];
    int ret;

    /* Only admin can write config */
    ret = ai_check_permission(AI_PERM_ADMIN);
    if (ret)
        return -EPERM;

    if (count >= sizeof(buf))
        return -EINVAL;

    if (copy_from_user(buf, ubuf, count))
        return -EFAULT;

    buf[count] = '\0';

    /* Strip trailing newline */
    if (count > 0 && buf[count - 1] == '\n')
        buf[count - 1] = '\0';

    mutex_lock(mtx);

    if (strncmp(buf, "governor=", 9) == 0) {
        const char *val = buf + 9;
        int i;

        for (i = 0; i <= AI_GOV_AI_ADAPTIVE; i++) {
            if (strcmp(val, governor_names[i]) == 0) {
                st->governor = i;
                if (ai_get_debug())
                    pr_info("linux_ai: governor set to '%s' via procfs\n", val);
                goto done;
            }
        }
        mutex_unlock(mtx);
        return -EINVAL;

    } else if (strncmp(buf, "state=", 6) == 0) {
        const char *val = buf + 6;

        if (strcmp(val, "running") == 0)
            st->state = AI_STATE_RUNNING;
        else if (strcmp(val, "stopped") == 0)
            st->state = AI_STATE_STOPPED;
        else if (strcmp(val, "training") == 0)
            st->state = AI_STATE_TRAINING;
        else {
            mutex_unlock(mtx);
            return -EINVAL;
        }
    } else {
        mutex_unlock(mtx);
        return -EINVAL;
    }

done:
    mutex_unlock(mtx);
    return count;
}

static const struct proc_ops ai_config_ops = {
    .proc_open    = ai_config_open,
    .proc_read    = seq_read,
    .proc_write   = ai_config_write,
    .proc_lseek   = seq_lseek,
    .proc_release = single_release,
};

/*
 * Init/Exit
 */
int ai_procfs_init(void)
{
    proc_ai_status = proc_create("ai_status", 0444, NULL, &ai_status_ops);
    if (!proc_ai_status)
        return -ENOMEM;

    proc_ai_config = proc_create("ai_config", 0644, NULL, &ai_config_ops);
    if (!proc_ai_config) {
        proc_remove(proc_ai_status);
        return -ENOMEM;
    }

    pr_info("linux_ai: procfs entries created\n");
    return 0;
}

void ai_procfs_exit(void)
{
    proc_remove(proc_ai_config);
    proc_remove(proc_ai_status);
    pr_info("linux_ai: procfs entries removed\n");
}

// SPDX-License-Identifier: GPL-2.0-only
/*
 * ai_core.c - Linux-AI kernel module core
 *
 * Main entry point for the Linux-AI kernel module.
 * Registers a character device (/dev/ai_ctl), initializes procfs/sysfs
 * interfaces, and provides ioctl-based control for AI subsystems.
 *
 * Copyright (C) 2026 Zaman Huseyinli
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/fs.h>
#include <linux/cdev.h>
#include <linux/device.h>
#include <linux/uaccess.h>
#include <linux/mutex.h>
#include <linux/slab.h>

#include "../include/ai_common.h"
#include "../include/ai_ioctl.h"

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Zaman Huseyinli");
MODULE_DESCRIPTION("Linux-AI: AI-powered system management kernel module");
MODULE_VERSION(AI_MODULE_VERSION);

/* Module parameters */
static int ai_debug = 0;
module_param(ai_debug, int, 0644);
MODULE_PARM_DESC(ai_debug, "Enable debug logging (0=off, 1=on)");

/* Forward declarations for procfs/sysfs (implemented in ai_procfs.c and ai_sysfs.c) */
extern int ai_procfs_init(void);
extern void ai_procfs_exit(void);
extern int ai_sysfs_init(void);
extern void ai_sysfs_exit(void);

/* Global state */
static struct ai_system_status ai_status;
static DEFINE_MUTEX(ai_mutex);

/* Character device variables */
static dev_t ai_devno;
static struct cdev ai_cdev;
static struct class *ai_class;

/* Accessor for global status - used by procfs/sysfs */
struct ai_system_status *ai_get_status(void)
{
    return &ai_status;
}
EXPORT_SYMBOL_GPL(ai_get_status);

struct mutex *ai_get_mutex(void)
{
    return &ai_mutex;
}
EXPORT_SYMBOL_GPL(ai_get_mutex);

int ai_get_debug(void)
{
    return ai_debug;
}
EXPORT_SYMBOL_GPL(ai_get_debug);

/* Permission check for current process */
int ai_check_permission(unsigned int required)
{
    /* Root always has full access */
    if (capable(CAP_SYS_ADMIN))
        return AI_STATUS_OK;

    /* Check if user has basic access for read operations */
    if ((required & AI_PERM_ADMIN) && !capable(CAP_SYS_ADMIN))
        return AI_STATUS_ERR_PERM;

    return AI_STATUS_OK;
}
EXPORT_SYMBOL_GPL(ai_check_permission);

int ai_is_admin(void)
{
    return capable(CAP_SYS_ADMIN) ? 1 : 0;
}
EXPORT_SYMBOL_GPL(ai_is_admin);

/*
 * ioctl handler
 */
static long ai_ioctl(struct file *filp, unsigned int cmd, unsigned long arg)
{
    int ret = 0;

    if (_IOC_TYPE(cmd) != AI_IOC_MAGIC)
        return -ENOTTY;

    switch (cmd) {
    case AI_IOC_GET_STATUS: {
        struct ai_system_status st;

        mutex_lock(&ai_mutex);
        memcpy(&st, &ai_status, sizeof(st));
        mutex_unlock(&ai_mutex);

        if (copy_to_user((void __user *)arg, &st, sizeof(st)))
            return -EFAULT;
        break;
    }

    case AI_IOC_RESET:
        ret = ai_check_permission(AI_PERM_ADMIN);
        if (ret)
            return -EPERM;

        mutex_lock(&ai_mutex);
        ai_status.state = AI_STATE_STOPPED;
        ai_status.governor = AI_GOV_ONDEMAND;
        ai_status.active_services = 0;
        mutex_unlock(&ai_mutex);

        pr_info("linux_ai: module reset by pid %d\n", current->pid);
        break;

    case AI_IOC_SET_GOVERNOR: {
        struct ai_ioc_governor gov;

        ret = ai_check_permission(AI_PERM_ADMIN);
        if (ret)
            return -EPERM;

        if (copy_from_user(&gov, (void __user *)arg, sizeof(gov)))
            return -EFAULT;

        if (gov.mode > AI_GOV_AI_ADAPTIVE)
            return -EINVAL;

        mutex_lock(&ai_mutex);
        ai_status.governor = gov.mode;
        mutex_unlock(&ai_mutex);

        if (ai_debug)
            pr_info("linux_ai: governor set to %d by pid %d\n",
                    gov.mode, current->pid);
        break;
    }

    case AI_IOC_GET_GOVERNOR: {
        struct ai_ioc_governor gov;

        mutex_lock(&ai_mutex);
        gov.mode = ai_status.governor;
        gov.cpu_mask = 0;
        mutex_unlock(&ai_mutex);

        if (copy_to_user((void __user *)arg, &gov, sizeof(gov)))
            return -EFAULT;
        break;
    }

    case AI_IOC_REQUEST_PERM: {
        struct ai_ioc_permission perm;

        if (copy_from_user(&perm, (void __user *)arg, sizeof(perm)))
            return -EFAULT;

        perm.uid = from_kuid_munged(current_user_ns(), current_euid());
        perm.gid = from_kgid_munged(current_user_ns(), current_egid());

        if (perm.perm_flags & AI_PERM_ADMIN) {
            perm.result = ai_check_permission(AI_PERM_ADMIN);
        } else {
            perm.result = AI_STATUS_OK;
        }

        if (copy_to_user((void __user *)arg, &perm, sizeof(perm)))
            return -EFAULT;
        break;
    }

    case AI_IOC_REGISTER_SVC: {
        struct ai_ioc_service svc;

        ret = ai_check_permission(AI_PERM_WRITE);
        if (ret)
            return -EPERM;

        if (copy_from_user(&svc, (void __user *)arg, sizeof(svc)))
            return -EFAULT;

        svc.name[AI_NAME_MAX_LEN - 1] = '\0';

        mutex_lock(&ai_mutex);
        ai_status.active_services++;
        svc.result = AI_STATUS_OK;
        mutex_unlock(&ai_mutex);

        if (ai_debug)
            pr_info("linux_ai: service '%s' registered (pid %d)\n",
                    svc.name, svc.pid);

        if (copy_to_user((void __user *)arg, &svc, sizeof(svc)))
            return -EFAULT;
        break;
    }

    case AI_IOC_UNREGISTER_SVC: {
        struct ai_ioc_service svc;

        if (copy_from_user(&svc, (void __user *)arg, sizeof(svc)))
            return -EFAULT;

        mutex_lock(&ai_mutex);
        if (ai_status.active_services > 0)
            ai_status.active_services--;
        mutex_unlock(&ai_mutex);
        break;
    }

    /* Reserved ioctl commands (defined in ai_ioctl.h but not yet implemented) */
    case AI_IOC_GET_FREQ:
    case AI_IOC_SET_FREQ:
        return -ENOTTY;

    default:
        return -ENOTTY;
    }

    return ret;
}

/*
 * File operations
 */
static int ai_open(struct inode *inode, struct file *filp)
{
    if (ai_debug)
        pr_info("linux_ai: device opened by pid %d\n", current->pid);
    return 0;
}

static int ai_release(struct inode *inode, struct file *filp)
{
    return 0;
}

static ssize_t ai_read(struct file *filp, char __user *buf,
                        size_t count, loff_t *ppos)
{
    char status_buf[96];  /* max ~80 chars for status line */
    int len;

    mutex_lock(&ai_mutex);
    len = snprintf(status_buf, sizeof(status_buf),
                   "state=%d governor=%d cpus=%u services=%u perm=%u version=%s\n",
                   ai_status.state, ai_status.governor,
                   ai_status.cpu_count, ai_status.active_services,
                   ai_status.perm_level, ai_status.version);
    mutex_unlock(&ai_mutex);

    return simple_read_from_buffer(buf, count, ppos, status_buf, len);
}

static const struct file_operations ai_fops = {
    .owner          = THIS_MODULE,
    .open           = ai_open,
    .release        = ai_release,
    .read           = ai_read,
    .unlocked_ioctl = ai_ioctl,
    .compat_ioctl   = compat_ptr_ioctl,
};

/*
 * Module init/exit
 */
static int __init ai_module_init(void)
{
    int ret;

    pr_info("linux_ai: initializing v%s\n", AI_MODULE_VERSION);

    /* Initialize status */
    memset(&ai_status, 0, sizeof(ai_status));
    ai_status.state = AI_STATE_RUNNING;
    ai_status.governor = AI_GOV_ONDEMAND;
    ai_status.cpu_count = num_online_cpus();
    strncpy(ai_status.version, AI_MODULE_VERSION, sizeof(ai_status.version) - 1);

    /* Allocate char device region */
    ret = alloc_chrdev_region(&ai_devno, 0, 1, AI_MODULE_NAME);
    if (ret < 0) {
        pr_err("linux_ai: failed to allocate chrdev region\n");
        return ret;
    }

    /* Initialize cdev */
    cdev_init(&ai_cdev, &ai_fops);
    ai_cdev.owner = THIS_MODULE;
    ret = cdev_add(&ai_cdev, ai_devno, 1);
    if (ret < 0) {
        pr_err("linux_ai: failed to add cdev\n");
        goto err_cdev;
    }

    /* Create device class and device node */
    ai_class = class_create(AI_MODULE_NAME);
    if (IS_ERR(ai_class)) {
        ret = PTR_ERR(ai_class);
        pr_err("linux_ai: failed to create class\n");
        goto err_class;
    }

    if (IS_ERR(device_create(ai_class, NULL, ai_devno, NULL, "ai_ctl"))) {
        ret = -ENOMEM;
        pr_err("linux_ai: failed to create device\n");
        goto err_device;
    }

    /* Initialize procfs entries */
    ret = ai_procfs_init();
    if (ret < 0) {
        pr_err("linux_ai: failed to initialize procfs\n");
        goto err_procfs;
    }

    /* Initialize sysfs entries */
    ret = ai_sysfs_init();
    if (ret < 0) {
        pr_err("linux_ai: failed to initialize sysfs\n");
        goto err_sysfs;
    }

    pr_info("linux_ai: module loaded (major=%d, cpus=%u)\n",
            MAJOR(ai_devno), ai_status.cpu_count);

    return 0;

err_sysfs:
    ai_procfs_exit();
err_procfs:
    device_destroy(ai_class, ai_devno);
err_device:
    class_destroy(ai_class);
err_class:
    cdev_del(&ai_cdev);
err_cdev:
    unregister_chrdev_region(ai_devno, 1);
    return ret;
}

static void __exit ai_module_exit(void)
{
    ai_sysfs_exit();
    ai_procfs_exit();
    device_destroy(ai_class, ai_devno);
    class_destroy(ai_class);
    cdev_del(&ai_cdev);
    unregister_chrdev_region(ai_devno, 1);

    pr_info("linux_ai: module unloaded\n");
}

module_init(ai_module_init);
module_exit(ai_module_exit);

/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * ai_permissions.h - Permission management API for Linux-AI
 *
 * Provides permission checking and management for both kernel
 * and userspace components. Integrates with Linux group-based
 * access control (ai-admin, ai-user groups).
 *
 * Copyright (C) 2026 Zaman Huseyinli
 */

#ifndef AI_PERMISSIONS_H
#define AI_PERMISSIONS_H

#include "ai_common.h"

#ifdef __KERNEL__

#include <linux/cred.h>
#include <linux/uidgid.h>

/*
 * Kernel-space permission helpers
 * These check the current task's credentials against ai-admin/ai-user groups.
 */

/**
 * ai_check_permission - Check if current process has required permission level
 * @required: AI_PERM_* flags indicating required permissions
 *
 * Returns AI_STATUS_OK if permitted, AI_STATUS_ERR_PERM otherwise.
 * Root (uid 0) always has full permissions.
 */
int ai_check_permission(unsigned int required);

/**
 * ai_is_admin - Check if current process has admin rights
 *
 * Returns 1 if the current user is root or in the ai-admin group.
 */
int ai_is_admin(void);

#else /* Userspace */

#include <unistd.h>
#include <grp.h>
#include <string.h>

/**
 * ai_user_check_group - Check if current user belongs to a group
 * @group_name: name of the group to check (e.g., "ai-admin")
 *
 * Returns 1 if user is in the group, 0 otherwise.
 */
static inline int ai_user_check_group(const char *group_name)
{
    struct group *grp = getgrnam(group_name);
    if (!grp)
        return 0;

    gid_t gid = grp->gr_gid;

    /* Check primary group */
    if (getegid() == gid)
        return 1;

    /* Check supplementary groups */
    int ngroups = getgroups(0, NULL);
    if (ngroups <= 0)
        return 0;

    gid_t *groups = (gid_t *)malloc(ngroups * sizeof(gid_t));
    if (!groups)
        return 0;

    if (getgroups(ngroups, groups) < 0) {
        free(groups);
        return 0;
    }

    for (int i = 0; i < ngroups; i++) {
        if (groups[i] == gid) {
            free(groups);
            return 1;
        }
    }

    free(groups);
    return 0;
}

/**
 * ai_user_is_admin - Check if current user has admin privileges
 *
 * Returns 1 if user is root or in ai-admin group.
 */
static inline int ai_user_is_admin(void)
{
    if (geteuid() == 0)
        return 1;
    return ai_user_check_group(AI_GROUP_ADMIN);
}

/**
 * ai_user_has_access - Check if current user has basic AI access
 *
 * Returns 1 if user is root, in ai-admin, or in ai-user group.
 */
static inline int ai_user_has_access(void)
{
    if (geteuid() == 0)
        return 1;
    if (ai_user_check_group(AI_GROUP_ADMIN))
        return 1;
    return ai_user_check_group(AI_GROUP_USER);
}

#endif /* __KERNEL__ */

#endif /* AI_PERMISSIONS_H */

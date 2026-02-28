/*
 * ai_permissions.c - Linux-AI permission management tool
 *
 * Manages user/group permissions for the Linux-AI subsystem.
 * Works with standard Linux groups (ai-admin, ai-user) and provides
 * a friendly interface for checking and configuring access.
 *
 * Usage:
 *   ai_permissions check           - Check current user's permissions
 *   ai_permissions setup           - Create ai-admin/ai-user groups (root)
 *   ai_permissions grant <user>    - Add user to ai-user group (root)
 *   ai_permissions admin <user>    - Add user to ai-admin group (root)
 *   ai_permissions revoke <user>   - Remove user from ai groups (root)
 *
 * Copyright (C) 2026 Zaman Huseyinli
 * License: GPL-2.0-only
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <grp.h>
#include <pwd.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/wait.h>

#include "../include/ai_common.h"
#include "../include/ai_permissions.h"

static int run_cmd(const char *cmd)
{
    int status = system(cmd);
    if (status == -1) {
        perror("system");
        return -1;
    }
    return WEXITSTATUS(status);
}

static int cmd_check(void)
{
    struct passwd *pw = getpwuid(getuid());
    const char *username = pw ? pw->pw_name : "unknown";

    printf("=== Linux-AI Permission Check ===\n");
    printf("User         : %s (uid=%u)\n", username, getuid());
    printf("Effective UID: %u\n", geteuid());
    printf("Root         : %s\n", geteuid() == 0 ? "yes" : "no");
    printf("ai-admin     : %s\n", ai_user_is_admin() ? "yes" : "no");
    printf("ai-user      : %s\n", ai_user_check_group(AI_GROUP_USER) ? "yes" : "no");
    printf("Has access   : %s\n", ai_user_has_access() ? "yes" : "no");

    if (!ai_user_has_access()) {
        printf("\nTo grant access, run as root:\n");
        printf("  ai_permissions grant %s\n", username);
    }

    return 0;
}

static int cmd_setup(void)
{
    if (geteuid() != 0) {
        fprintf(stderr, "Error: root privileges required for setup.\n");
        return 1;
    }

    printf("Creating Linux-AI groups...\n");

    /* Create ai-admin group if it doesn't exist */
    if (getgrnam(AI_GROUP_ADMIN) == NULL) {
        char cmd[256];
        snprintf(cmd, sizeof(cmd), "groupadd %s", AI_GROUP_ADMIN);
        if (run_cmd(cmd) == 0)
            printf("  [+] Group '%s' created\n", AI_GROUP_ADMIN);
        else
            printf("  [!] Failed to create group '%s'\n", AI_GROUP_ADMIN);
    } else {
        printf("  [=] Group '%s' already exists\n", AI_GROUP_ADMIN);
    }

    /* Create ai-user group if it doesn't exist */
    if (getgrnam(AI_GROUP_USER) == NULL) {
        char cmd[256];
        snprintf(cmd, sizeof(cmd), "groupadd %s", AI_GROUP_USER);
        if (run_cmd(cmd) == 0)
            printf("  [+] Group '%s' created\n", AI_GROUP_USER);
        else
            printf("  [!] Failed to create group '%s'\n", AI_GROUP_USER);
    } else {
        printf("  [=] Group '%s' already exists\n", AI_GROUP_USER);
    }

    /* Set device permissions */
    printf("\nSetting device permissions...\n");
    run_cmd("chown root:" AI_GROUP_USER " " AI_DEV_PATH " 2>/dev/null");
    run_cmd("chmod 0660 " AI_DEV_PATH " 2>/dev/null");

    printf("\nSetup complete. Use 'ai_permissions grant <user>' to add users.\n");
    return 0;
}

static int cmd_grant(const char *username)
{
    if (geteuid() != 0) {
        fprintf(stderr, "Error: root privileges required.\n");
        return 1;
    }

    /* Verify user exists */
    if (getpwnam(username) == NULL) {
        fprintf(stderr, "Error: user '%s' not found.\n", username);
        return 1;
    }

    char cmd[256];
    snprintf(cmd, sizeof(cmd), "usermod -aG %s %s", AI_GROUP_USER, username);
    if (run_cmd(cmd) != 0) {
        fprintf(stderr, "Failed to add user '%s' to '%s' group.\n",
                username, AI_GROUP_USER);
        return 1;
    }

    printf("User '%s' added to '%s' group.\n", username, AI_GROUP_USER);
    printf("User needs to log out and back in for changes to take effect.\n");
    return 0;
}

static int cmd_admin(const char *username)
{
    if (geteuid() != 0) {
        fprintf(stderr, "Error: root privileges required.\n");
        return 1;
    }

    if (getpwnam(username) == NULL) {
        fprintf(stderr, "Error: user '%s' not found.\n", username);
        return 1;
    }

    char cmd[256];
    snprintf(cmd, sizeof(cmd), "usermod -aG %s,%s %s",
             AI_GROUP_ADMIN, AI_GROUP_USER, username);
    if (run_cmd(cmd) != 0) {
        fprintf(stderr, "Failed to add user '%s' to admin groups.\n", username);
        return 1;
    }

    printf("User '%s' added to '%s' and '%s' groups.\n",
           username, AI_GROUP_ADMIN, AI_GROUP_USER);
    printf("User needs to log out and back in for changes to take effect.\n");
    return 0;
}

static int cmd_revoke(const char *username)
{
    if (geteuid() != 0) {
        fprintf(stderr, "Error: root privileges required.\n");
        return 1;
    }

    if (getpwnam(username) == NULL) {
        fprintf(stderr, "Error: user '%s' not found.\n", username);
        return 1;
    }

    char cmd[256];
    snprintf(cmd, sizeof(cmd), "gpasswd -d %s %s 2>/dev/null", username, AI_GROUP_ADMIN);
    run_cmd(cmd);
    snprintf(cmd, sizeof(cmd), "gpasswd -d %s %s 2>/dev/null", username, AI_GROUP_USER);
    run_cmd(cmd);

    printf("User '%s' removed from Linux-AI groups.\n", username);
    return 0;
}

static void usage(const char *progname)
{
    fprintf(stderr, "Linux-AI Permission Manager v%s\n\n", AI_MODULE_VERSION);
    fprintf(stderr, "Usage: %s <command> [args]\n\n", progname);
    fprintf(stderr, "Commands:\n");
    fprintf(stderr, "  check              Check current user's permissions\n");
    fprintf(stderr, "  setup              Create ai-admin/ai-user groups (root)\n");
    fprintf(stderr, "  grant <username>   Add user to ai-user group (root)\n");
    fprintf(stderr, "  admin <username>   Add user to ai-admin group (root)\n");
    fprintf(stderr, "  revoke <username>  Remove user from ai groups (root)\n");
}

int main(int argc, char *argv[])
{
    if (argc < 2) {
        usage(argv[0]);
        return 1;
    }

    if (strcmp(argv[1], "check") == 0)
        return cmd_check();

    if (strcmp(argv[1], "setup") == 0)
        return cmd_setup();

    if (strcmp(argv[1], "grant") == 0) {
        if (argc < 3) {
            fprintf(stderr, "Usage: %s grant <username>\n", argv[0]);
            return 1;
        }
        return cmd_grant(argv[2]);
    }

    if (strcmp(argv[1], "admin") == 0) {
        if (argc < 3) {
            fprintf(stderr, "Usage: %s admin <username>\n", argv[0]);
            return 1;
        }
        return cmd_admin(argv[2]);
    }

    if (strcmp(argv[1], "revoke") == 0) {
        if (argc < 3) {
            fprintf(stderr, "Usage: %s revoke <username>\n", argv[0]);
            return 1;
        }
        return cmd_revoke(argv[2]);
    }

    fprintf(stderr, "Unknown command: %s\n", argv[1]);
    usage(argv[0]);
    return 1;
}

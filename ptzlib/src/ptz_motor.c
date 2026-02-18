#define _POSIX_C_SOURCE 200809L
#include "ptz_internal.h"

#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

static pid_t find_pid_by_name(const char *name) {
    DIR *d = opendir("/proc");
    if (!d) return -1;

    struct dirent *de;
    while ((de = readdir(d))) {
        if (!isdigit((unsigned char)de->d_name[0])) continue;

        pid_t pid = (pid_t)atoi(de->d_name);

        char comm_path[256];
        snprintf(comm_path, sizeof(comm_path), "/proc/%d/comm", (int)pid);

        FILE *f = fopen(comm_path, "r");
        if (!f) continue;

        char comm[128];
        if (!fgets(comm, sizeof(comm), f)) {
            fclose(f);
            continue;
        }
        fclose(f);

        comm[strcspn(comm, "\r\n")] = '\0';
        if (strcmp(comm, name) == 0) {
            closedir(d);
            return pid;
        }
    }

    closedir(d);
    return -1;
}

static int read_motor_fd(pid_t pid, unsigned long addr) {
    char mem_path[256];
    snprintf(mem_path, sizeof(mem_path), "/proc/%d/mem", (int)pid);

    int memfd = open(mem_path, O_RDONLY);
    if (memfd < 0) return -1;

    uint32_t mfd = 0;
    ssize_t n = pread(memfd, &mfd, sizeof(mfd), (off_t)addr);
    close(memfd);

    if (n != (ssize_t)sizeof(mfd)) return -1;
    return (int)mfd;
}

static const char *axis_dev_path(const ptz_config_t *cfg, ptz_axis_t axis) {
    if (!cfg) return NULL;
    if (axis == PTZ_AXIS_PAN) return (cfg->pan_dev[0] ? cfg->pan_dev : "/dev/motor0");
    return (cfg->tilt_dev[0] ? cfg->tilt_dev : "/dev/motor1");
}

static int devnode_exists(const char *p) {
    if (!p || !*p) return 0;
    return access(p, F_OK) == 0;
}

/* Resolve the motor device FD using either:
     - /dev/motorX (preferred on firmwares with ak_motor.ko), or
     - legacy /proc/PID/fd indirection.

   Returns an open FD on success (caller must close), or -1.
*/
static int open_motor_fd(const ptz_config_t *cfg, ptz_axis_t axis, unsigned long fd_addr, char *dbg, size_t dbg_sz) {
    if (dbg && dbg_sz) dbg[0] = '\0';

    const char *dev = axis_dev_path(cfg, axis);
    int backend = cfg ? cfg->motor_backend : 0;

    /* Decide backend.
       AUTO: if /dev node exists use it; otherwise fall back to procfd if we have an addr.
    */
    int try_dev = (backend == 0 || backend == 1);
    int try_proc = (backend == 0 || backend == 2);

    if (try_dev && devnode_exists(dev)) {
        int fd = open(dev, O_RDWR);
        if (fd >= 0) {
            if (dbg && dbg_sz) snprintf(dbg, dbg_sz, "dev:%s", dev);
            return fd;
        }
    }

    if (!try_proc) return -1;
    if (!cfg) return -1;
    if (fd_addr == 0) return -1;

    pid_t pid = (cfg->anyka_pid > 1) ? (pid_t)cfg->anyka_pid : find_pid_by_name(cfg->anyka_proc);
    if (pid < 0) return -1;

    int mfd = read_motor_fd(pid, fd_addr);
    if (mfd <= 0) return -1;

    char fd_path[256];
    snprintf(fd_path, sizeof(fd_path), "/proc/%d/fd/%d", (int)pid, mfd);

    int devfd = open(fd_path, O_RDWR);
    if (devfd < 0) return -1;

    if (dbg && dbg_sz) snprintf(dbg, dbg_sz, "proc:%s (pid=%d mfd=%d)", fd_path, (int)pid, mfd);
    return devfd;
}

int ptz_issue_motor(const ptz_config_t *cfg,
                    ptz_axis_t axis,
                    const char *dir,
                    int step,
                    int rep,
                    unsigned long cmd,
                    bool do_log) {
    unsigned long fd_addr = ptz_axis_fd_addr(cfg, axis);

    char dbg[512];
    int devfd = open_motor_fd(cfg, axis, fd_addr, dbg, sizeof(dbg));
    if (devfd < 0) {
        ptz_log_line(cfg,
                     "ERROR open motor failed axis=%s backend=%d dev=%s fd_addr=0x%lx errno=%d",
                     ptz_axis_name(axis), cfg ? cfg->motor_backend : -1,
                     axis_dev_path(cfg, axis) ? axis_dev_path(cfg, axis) : "",
                     fd_addr, errno);
        return -1;
    }

    if (rep < 1) rep = 1;

    int rc = 0;
    int32_t step32 = (int32_t)step;
    errno = 0;
    for (int i = 0; i < rep; i++) {
        rc = ioctl(devfd, cmd, &step32);
        if (rc) break;
        ptz_sleep_us(10000);
    }

    if (do_log) {
        ptz_log_line(cfg,
                     "motor axis=%s via=%s dir=%s step=%d rep=%d cmd=0x%lx fd_addr=0x%lx rc=%d errno=%d",
                     ptz_axis_name(axis), dbg,
                     dir ? dir : "", step, rep, cmd, fd_addr, rc, errno);
    }

    close(devfd);
    return rc;
}

int ptz_motor_turn_middle(const ptz_config_t *cfg, ptz_axis_t axis, bool do_log) {
    if (!cfg) return -1;
    if (cfg->ioctl_turn_middle == 0) return -1;

    unsigned long fd_addr = ptz_axis_fd_addr(cfg, axis);
    char dbg[512];
    int devfd = open_motor_fd(cfg, axis, fd_addr, dbg, sizeof(dbg));
    if (devfd < 0) {
        ptz_log_line(cfg,
                     "ERROR open motor failed (turn_middle) axis=%s backend=%d dev=%s fd_addr=0x%lx errno=%d",
                     ptz_axis_name(axis), cfg->motor_backend,
                     axis_dev_path(cfg, axis) ? axis_dev_path(cfg, axis) : "",
                     fd_addr, errno);
        return -1;
    }

    /* anyka_ipc passes an 8-byte user buffer for this ioctl on the observed firmware.
       We do the same to stay ABI-compatible and ignore returned data. */
    uint64_t buf = 0;
    errno = 0;
    int rc = ioctl(devfd, cfg->ioctl_turn_middle, &buf);

    if (do_log) {
        ptz_log_line(cfg,
                     "motor axis=%s via=%s turn_middle cmd=0x%lx fd_addr=0x%lx rc=%d errno=%d out=0x%llx",
                     ptz_axis_name(axis), dbg, cfg->ioctl_turn_middle, fd_addr,
                     rc, errno, (unsigned long long)buf);
    }

    close(devfd);
    return rc;
}

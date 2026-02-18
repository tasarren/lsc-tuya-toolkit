#define _POSIX_C_SOURCE 200809L
#include "ptz_internal.h"

#include <stdio.h>
#include <string.h>

static long interval_us_from_cfg(const ptz_config_t *cfg) {
    int ms = cfg ? cfg->worker_interval_ms : 0;
    if (ms < 5) ms = 5;        /* don't spin */
    if (ms > 1000) ms = 1000;  /* avoid ridiculous delays */
    return (long)ms * 1000L;
}

int ptz_continuous_arm(ptz_ctx_t *ctx, ptz_axis_t a, const char *dir, int step, int rep) {
    if (!ctx) return -1;
    if (a != PTZ_AXIS_PAN && a != PTZ_AXIS_TILT) return -1;

    if (!dir) dir = "";
    if (rep < 1) rep = 1;

    ctx->cont[a].active = true;
    ctx->cont[a].step = step;
    ctx->cont[a].rep = rep;
    ctx->cont[a].fd_addr = ptz_axis_fd_addr(&ctx->cfg, a);

    memset(ctx->cont[a].dir, 0, sizeof(ctx->cont[a].dir));
    snprintf(ctx->cont[a].dir, sizeof(ctx->cont[a].dir), "%s", dir);

    struct timespec now;
    if (ptz_now_monotonic(&now) != 0) {
        now.tv_sec = 0;
        now.tv_nsec = 0;
    }
    ctx->cont[a].next_due = now; /* due immediately */

    return 0;
}

void ptz_continuous_disarm(ptz_ctx_t *ctx, ptz_axis_t a) {
    if (!ctx) return;
    if (a != PTZ_AXIS_PAN && a != PTZ_AXIS_TILT) return;
    ctx->cont[a].active = false;
}

int ptz_continuous_tick(ptz_ctx_t *ctx) {
    if (!ctx) return -1;

    struct timespec now;
    if (ptz_now_monotonic(&now) != 0) return -1;

    long interval_us = interval_us_from_cfg(&ctx->cfg);

    int did = 0;
    for (int a = 0; a < 2; a++) {
        if (!ctx->cont[a].active) continue;
        if (!ptz_timespec_ge(&now, &ctx->cont[a].next_due)) continue;

        int rc = ptz_issue_motor(&ctx->cfg,
                                (ptz_axis_t)a,
                                ctx->cont[a].dir,
                                ctx->cont[a].step,
                                ctx->cont[a].rep,
                                ctx->cfg.ioctl_move,
                                true);
        if (rc != 0) return -1;

        ctx->cont[a].next_due = ptz_timespec_add_us(ctx->cont[a].next_due, interval_us);
        /* If we were paused for a while, don't try to catch up with a burst. */
        if (ptz_timespec_ge(&now, &ctx->cont[a].next_due)) {
            ctx->cont[a].next_due = ptz_timespec_add_us(now, interval_us);
        }

        did = 1;
    }

    return did;
}

#define _POSIX_C_SOURCE 200809L
#include "ptz_internal.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

/* ONVIF speed is typically 0..1. We treat it as a velocity factor. */
static double parse_speed_factor(const char *s) {
    double v = 0.5;
    if (s && *s) v = atof(s);
    if (v < 0) v = -v;

    if (v > 1.0) v = 1.0;
    if (v < 0.01) v = 0.01;
    return v;
}

/* This is still used to decide how many degrees/steps each command should represent. */
static int speed_to_deg(const char *s) {
    double v = 0.5;
    if (s && *s) v = atof(s);
    if (v < 0) v = -v;
    return ptz_clampi((int)(v * 20.0) + 2, 1, 25);
}

static int deg_to_steps(int deg, int total_steps, int max_deg) {
    if (max_deg <= 0) return 1;
    int s = (deg * total_steps) / max_deg;
    return (s < 1) ? 1 : s;
}

static int clamp_abs_step(int step, int abs_max) {
    if (abs_max <= 0) return step;
    int a = (step < 0) ? -step : step;
    if (a <= abs_max) return step;
    return (step < 0) ? -abs_max : abs_max;
}

static int apply_dir_polarity(const ptz_config_t *cfg, const char *dir, int step) {
    bool pan = (strcmp(dir, "left") == 0 || strcmp(dir, "right") == 0);
    bool tilt = (strcmp(dir, "up") == 0 || strcmp(dir, "down") == 0);

    if (pan && cfg->pan_invert) step = -step;
    if (tilt && cfg->tilt_invert) step = -step;

    return step;
}

typedef struct { const char *dir; ptz_axis_t axis; int sign; } dirspec_t;
static const dirspec_t DIRS[] = {
    { "left",  PTZ_AXIS_PAN,  -1 },
    { "right", PTZ_AXIS_PAN,   1 },
    { "up",    PTZ_AXIS_TILT,  1 },
    { "down",  PTZ_AXIS_TILT, -1 },
};

static const dirspec_t *find_dir(const char *dir) {
    for (size_t i = 0; i < sizeof(DIRS) / sizeof(DIRS[0]); i++) {
        if (strcmp(dir, DIRS[i].dir) == 0) return &DIRS[i];
    }
    return NULL;
}

static void pick_mult_rep(const ptz_config_t *c, const char *dir, int *mult, int *rep) {
    if (strcmp(dir, "left") == 0 || strcmp(dir, "right") == 0) {
        *mult = (c->pan_step_mult > 0) ? c->pan_step_mult : c->step_mult;
        *rep  = (c->pan_step_repeat > 0) ? c->pan_step_repeat : c->step_repeat;
        return;
    }

    int m = (c->tilt_step_mult > 0) ? c->tilt_step_mult : c->step_mult;
    int r = (c->tilt_step_repeat > 0) ? c->tilt_step_repeat : c->step_repeat;

    if (strcmp(dir, "up") == 0) {
        if (c->tilt_up_step_mult > 0) m = c->tilt_up_step_mult;
        if (c->tilt_up_step_repeat > 0) r = c->tilt_up_step_repeat;
    } else if (strcmp(dir, "down") == 0) {
        if (c->tilt_down_step_mult > 0) m = c->tilt_down_step_mult;
        if (c->tilt_down_step_repeat > 0) r = c->tilt_down_step_repeat;
    }

    *mult = m;
    *rep = r;
}

/* Set driver velocity using IOCTL_SET_SPEED, scaling per requested ONVIF speed factor. */
static int set_speed_if_needed(const ptz_config_t *c, ptz_axis_t a, const char *dir, double factor) {
    if (!c->set_speed_each_move) return 0;

    int base = ptz_axis_speed_step(c, a);
    if (base <= 0) return 0;

    double d = (double)base * factor;
    int speed_step = (int)(d + 0.5);
    if (speed_step < 1) speed_step = 1;
    if (speed_step > base) speed_step = base;

    return ptz_issue_motor(c, a, dir, speed_step, 1, c->ioctl_set_speed, true);
}

static int run_axis_delta(const ptz_config_t *cfg,
                          ptz_axis_t axis,
                          const char *dir,
                          int delta_deg,
                          int total_steps,
                          int max_deg) {
    if (!delta_deg) return 0;

    int rem = deg_to_steps(abs(delta_deg), total_steps, max_deg);
    int sign = (delta_deg < 0) ? -1 : 1;

    int chunk = cfg->absrel_chunk_steps;
    if (chunk < 1) chunk = 1;

    int interval_ms = cfg->absrel_interval_ms;
    if (interval_ms < 0) interval_ms = 0;

    unsigned long fd_addr = ptz_axis_fd_addr(cfg, axis);

    if (cfg->set_speed_each_move) {
        /* abs/rel moves have no explicit speed argument; use configured full speed. */
        if (set_speed_if_needed(cfg, axis, dir, 1.0) != 0) {
            ptz_log_line(cfg, "absrel speed set failed dir=%s speed_step=%d addr=0x%lx",
                         dir, ptz_axis_speed_step(cfg, axis), fd_addr);
        }
    }

    while (rem > 0) {
        int one = (rem > chunk) ? chunk : rem;
        int step = apply_dir_polarity(cfg, dir, sign * one);

        if (ptz_issue_motor(cfg, axis, dir, step, 1, cfg->ioctl_move, false) != 0) {
            ptz_log_line(cfg, "absrel move failed dir=%s step=%d addr=0x%lx", dir, step, fd_addr);
            return 1;
        }

        rem -= one;
        if (interval_ms) ptz_sleep_us((long)interval_ms * 1000);
    }

    return 0;
}

int ptz_ctx_init(ptz_ctx_t *ctx, const ptz_config_t *cfg) {
    if (!ctx || !cfg) return -1;
    ctx->cfg = *cfg;
    for (int i = 0; i < 2; i++) {
        ctx->cont[i].active = false;
        ctx->cont[i].dir[0] = '\0';
        ctx->cont[i].step = 0;
        ctx->cont[i].rep = 1;
        ctx->cont[i].fd_addr = 0;
        ctx->cont[i].next_due.tv_sec = 0;
        ctx->cont[i].next_due.tv_nsec = 0;
    }
    ptz_ensure_state_dir(&ctx->cfg);
    return 0;
}

int ptz_move_dir(ptz_ctx_t *ctx, const char *dir, const char *speed) {
    if (!ctx || !dir || !*dir) return -1;

    int deg = speed_to_deg(speed);
    double speed_factor = parse_speed_factor(speed);
    int x, y, z;

    if (strcmp(dir, "in") == 0 || strcmp(dir, "out") == 0) {
        (void)ptz_get_position(ctx, &x, &y, &z);

        if (ctx->cfg.zoom_supported) {
            z += (strcmp(dir, "in") == 0) ? deg : -deg;
            z = ptz_clampi(z, 0, 100);
            (void)ptz_set_position(ctx, x, y, z);
        }

        ptz_log_line(&ctx->cfg,
                     "move dir=%s speed=%s deg=%d base_step=0 step=0 mult=%d rep=%d invert=%d/%d pos=%d,%d,%d",
                     dir, speed ? speed : "", deg,
                     ctx->cfg.step_mult, ctx->cfg.step_repeat,
                     ctx->cfg.pan_invert, ctx->cfg.tilt_invert,
                     x, y, z);
        return 0;
    }

    const dirspec_t *ds = find_dir(dir);
    if (!ds) return -1;

    int total_steps = (ds->axis == PTZ_AXIS_PAN) ? ctx->cfg.pan_total_steps : ctx->cfg.tilt_total_steps;
    int max_deg     = (ds->axis == PTZ_AXIS_PAN) ? ctx->cfg.pan_max_deg : ctx->cfg.tilt_max_deg;

    int base_step = deg_to_steps(deg, total_steps, max_deg);

    int mult = 1, rep = 1;
    pick_mult_rep(&ctx->cfg, dir, &mult, &rep);

    int step = ds->sign * base_step;
    if (mult > 1) step *= mult;

    step = apply_dir_polarity(&ctx->cfg, dir, step);

    if (ds->axis == PTZ_AXIS_TILT) {
        step = clamp_abs_step(step, ctx->cfg.tilt_step_abs_max);
        if (strcmp(dir, "up") == 0) step = clamp_abs_step(step, ctx->cfg.tilt_up_step_abs_max);
        if (strcmp(dir, "down") == 0) step = clamp_abs_step(step, ctx->cfg.tilt_down_step_abs_max);
    }

    unsigned long fd_addr = ptz_axis_fd_addr(&ctx->cfg, ds->axis);

    if (set_speed_if_needed(&ctx->cfg, ds->axis, dir, speed_factor) != 0) {
        ptz_log_line(&ctx->cfg, "speed set failed dir=%s speed_step=%d factor=%g addr=0x%lx",
                     dir, ptz_axis_speed_step(&ctx->cfg, ds->axis), speed_factor, fd_addr);
    }

    if (ctx->cfg.continuous_mode) {
        int div = ctx->cfg.continuous_step_div;
        if (div < 1) div = 1;

        int run_step = step / div;
        if (!run_step) run_step = (step < 0) ? -1 : 1;

        int run_rep = ctx->cfg.continuous_rep;
        if (run_rep < 1) run_rep = 1;

        if (ptz_continuous_arm(ctx, ds->axis, dir, run_step, run_rep) != 0) {
            ptz_log_line(&ctx->cfg, "move failed continuous_arm dir=%s step=%d addr=0x%lx", dir, step, fd_addr);
            return 1;
        }
    } else {
        if (ptz_issue_motor(&ctx->cfg, ds->axis, dir, step, rep, ctx->cfg.ioctl_move, true) != 0) {
            ptz_log_line(&ctx->cfg, "move failed dir=%s step=%d addr=0x%lx", dir, step, fd_addr);
            return 1;
        }
    }

    (void)ptz_get_position(ctx, &x, &y, &z);
    if (ds->axis == PTZ_AXIS_PAN) x += ds->sign * deg;
    else y += ds->sign * deg;

    x = ptz_clampi(x, 0, ctx->cfg.pan_max_deg);
    y = ptz_clampi(y, 0, ctx->cfg.tilt_max_deg);
    z = ptz_clampi(z, 0, 100);

    (void)ptz_set_position(ctx, x, y, z);

    ptz_log_line(&ctx->cfg,
                 "move dir=%s speed=%s factor=%g deg=%d base_step=%d step=%d mult=%d rep=%d invert=%d/%d pos=%d,%d,%d",
                 dir, speed ? speed : "", speed_factor, deg, base_step, step, mult, rep,
                 ctx->cfg.pan_invert, ctx->cfg.tilt_invert, x, y, z);

    return 0;
}

int ptz_stop(ptz_ctx_t *ctx) {
    if (!ctx) return -1;
    ptz_continuous_disarm(ctx, PTZ_AXIS_PAN);
    ptz_continuous_disarm(ctx, PTZ_AXIS_TILT);

    /* Best-effort motor stop. Some firmwares ignore this and only stop when commands stop arriving. */
    (void)ptz_issue_motor(&ctx->cfg, PTZ_AXIS_PAN,  "", 0, 1, ctx->cfg.ioctl_stop, true);
    (void)ptz_issue_motor(&ctx->cfg, PTZ_AXIS_TILT, "", 0, 1, ctx->cfg.ioctl_stop, true);
    ptz_log_line(&ctx->cfg, "move stop");
    return 0;
}

int ptz_home(ptz_ctx_t *ctx) {
    if (!ctx) return -1;

    /* Stop any continuous movement first. */
    (void)ptz_stop(ctx);

    int rc_pan = -1;
    int rc_tilt = -1;

    /* Prefer driver-supported homing/centering when available. */
    if (ctx->cfg.ioctl_turn_middle) {
        rc_pan = ptz_motor_turn_middle(&ctx->cfg, PTZ_AXIS_PAN, true);
        rc_tilt = ptz_motor_turn_middle(&ctx->cfg, PTZ_AXIS_TILT, true);
    }

    /* Persist expected centered position even if driver doesn't report back.
       If the ioctl fails on both axes, we still keep the old behavior (state-only home).
       Caller can treat negative return as a hint that hardware centering did not run. */
    int x = ctx->cfg.pan_max_deg / 2;
    int y = ctx->cfg.tilt_max_deg / 2;
    (void)ptz_set_position(ctx, x, y, 0);

    ptz_log_line(&ctx->cfg, "move home rc_pan=%d rc_tilt=%d", rc_pan, rc_tilt);
    if (rc_pan < 0 && rc_tilt < 0) return -1;
    return 0;
}

int ptz_move_abs(ptz_ctx_t *ctx, double x, double y, double z) {
    if (!ctx) return -1;

    int px = ptz_clampi((int)((x + 1.0) * (ctx->cfg.pan_max_deg / 2.0)), 0, ctx->cfg.pan_max_deg);
    int py = ptz_clampi((int)((y + 1.0) * (ctx->cfg.tilt_max_deg / 2.0)), 0, ctx->cfg.tilt_max_deg);
    int pz = ptz_clampi((int)((z + 1.0) * 50.0), 0, 100);

    int cx, cy, cz;
    (void)ptz_get_position(ctx, &cx, &cy, &cz);
    (void)cz;

    int dx = px - cx;
    int dy = py - cy;

    if (dx && run_axis_delta(&ctx->cfg, PTZ_AXIS_PAN, (dx > 0) ? "right" : "left",
                             dx, ctx->cfg.pan_total_steps, ctx->cfg.pan_max_deg))
        return 1;

    if (dy && run_axis_delta(&ctx->cfg, PTZ_AXIS_TILT, (dy > 0) ? "up" : "down",
                             dy, ctx->cfg.tilt_total_steps, ctx->cfg.tilt_max_deg))
        return 1;

    (void)ptz_set_position(ctx, px, py, pz);
    ptz_log_line(&ctx->cfg, "move abs -> pos=%d,%d,%d (norm=%g,%g,%g)", px, py, pz, x, y, z);
    return 0;
}

int ptz_move_rel(ptz_ctx_t *ctx, double dx, double dy, double dz) {
    if (!ctx) return -1;

    int x, y, z;
    (void)ptz_get_position(ctx, &x, &y, &z);

    int mdx = (int)(dx * (ctx->cfg.pan_max_deg / 2.0));
    int mdy = (int)(dy * (ctx->cfg.tilt_max_deg / 2.0));

    if (mdx && run_axis_delta(&ctx->cfg, PTZ_AXIS_PAN, (mdx > 0) ? "right" : "left",
                              mdx, ctx->cfg.pan_total_steps, ctx->cfg.pan_max_deg))
        return 1;

    if (mdy && run_axis_delta(&ctx->cfg, PTZ_AXIS_TILT, (mdy > 0) ? "up" : "down",
                              mdy, ctx->cfg.tilt_total_steps, ctx->cfg.tilt_max_deg))
        return 1;

    x = ptz_clampi(x + mdx, 0, ctx->cfg.pan_max_deg);
    y = ptz_clampi(y + mdy, 0, ctx->cfg.tilt_max_deg);
    z = ptz_clampi(z + (int)(dz * 10.0), 0, 100);

    (void)ptz_set_position(ctx, x, y, z);
    ptz_log_line(&ctx->cfg, "move rel -> pos=%d,%d,%d (delta=%g,%g,%g)", x, y, z, dx, dy, dz);
    return 0;
}

int ptz_tick(ptz_ctx_t *ctx) {
    return ptz_continuous_tick(ctx);
}

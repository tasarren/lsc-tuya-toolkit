#define _POSIX_C_SOURCE 200809L
#include "ptz_internal.h"

#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>

const char *ptz_axis_name(ptz_axis_t a) { return (a == PTZ_AXIS_PAN) ? "pan" : "tilt"; }
unsigned long ptz_axis_fd_addr(const ptz_config_t *c, ptz_axis_t a) { return (a == PTZ_AXIS_PAN) ? c->pan_fd_addr : c->tilt_fd_addr; }
int ptz_axis_speed_step(const ptz_config_t *c, ptz_axis_t a) { return (a == PTZ_AXIS_PAN) ? c->pan_speed_step : c->tilt_speed_step; }

void ptz_state_path(const ptz_config_t *cfg, const char *name, char *out, size_t out_sz) {
    snprintf(out, out_sz, "%s/%s", cfg->state_dir, name);
}

void ptz_ensure_state_dir(const ptz_config_t *cfg) {
    /* best-effort; keep behavior permissive */
    ptz_mkdir_p_for_file(cfg->state_dir);
    (void)mkdir(cfg->state_dir, 0755);
}

void ptz_log_line(const ptz_config_t *cfg, const char *fmt, ...) {
    if (!cfg || !cfg->debug_log) return;

    ptz_mkdir_p_for_file(cfg->log_file);
    FILE *f = fopen(cfg->log_file, "a");
    if (!f) return;

    time_t now = time(NULL);
    struct tm tm_now;
    localtime_r(&now, &tm_now);

    char ts[64];
    strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%S", &tm_now);
    fprintf(f, "[%s] ", ts);

    va_list ap;
    va_start(ap, fmt);
    vfprintf(f, fmt, ap);
    va_end(ap);

    fputc('\n', f);
    fclose(f);
}

#ifndef PTZ_INTERNAL_H
#define PTZ_INTERNAL_H

#include "ptzctl.h"
#include "ptz_util.h"

#include <stdarg.h>
#include <stddef.h>

typedef enum { PTZ_AXIS_PAN = 0, PTZ_AXIS_TILT = 1 } ptz_axis_t;

const char *ptz_axis_name(ptz_axis_t a);
unsigned long ptz_axis_fd_addr(const ptz_config_t *c, ptz_axis_t a);
int ptz_axis_speed_step(const ptz_config_t *c, ptz_axis_t a);

void ptz_state_path(const ptz_config_t *cfg, const char *name, char *out, size_t out_sz);
void ptz_ensure_state_dir(const ptz_config_t *cfg);

void ptz_log_line(const ptz_config_t *cfg, const char *fmt, ...);

/* Motor + continuous internals */
int ptz_issue_motor(const ptz_config_t *cfg,
                    ptz_axis_t axis,
                    const char *dir,
                    int step,
                    int rep,
                    unsigned long cmd,
                    bool do_log);

/* Firmware extras (ak_motor.ko). */
int ptz_motor_turn_middle(const ptz_config_t *cfg, ptz_axis_t axis, bool do_log);

int ptz_continuous_arm(ptz_ctx_t *ctx, ptz_axis_t a, const char *dir, int step, int rep);
void ptz_continuous_disarm(ptz_ctx_t *ctx, ptz_axis_t a);
int ptz_continuous_tick(ptz_ctx_t *ctx);

#endif /* PTZ_INTERNAL_H */

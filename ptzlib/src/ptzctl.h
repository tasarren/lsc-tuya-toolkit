#ifndef PTZCTL_H
#define PTZCTL_H

#include <stdbool.h>
#include <stddef.h>
#include <time.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Public configuration. Keep this stable so other binaries can reuse it. */
typedef struct ptz_config {
    char anyka_proc[64];
    int anyka_pid; /* optional override; if >0, use this PID instead of scanning by name */
    char state_dir[256];
    char log_file[256];

    unsigned long pan_fd_addr;
    unsigned long tilt_fd_addr;
    unsigned long ioctl_move;
    unsigned long ioctl_stop;
    unsigned long ioctl_set_speed;

    /* Firmware/driver extras (Anyka ak_motor.ko).
       These fields are optional; defaults match the observed ABI.

       motor_backend:
         0 = auto (prefer /dev/motorX if present, else legacy /proc/PID/fd)
         1 = /dev/motorX only
         2 = legacy /proc/PID/fd only
    */
    char pan_dev[64];
    char tilt_dev[64];
    int motor_backend;
    unsigned long ioctl_get_state;
    unsigned long ioctl_turn_middle;

    int pan_max_deg;
    int pan_total_steps;
    int tilt_max_deg;
    int tilt_total_steps;

    int pan_invert;
    int tilt_invert;

    int step_mult;
    int step_repeat;
    int pan_step_mult;
    int pan_step_repeat;

    int tilt_step_mult;
    int tilt_step_repeat;
    int tilt_step_abs_max;

    int tilt_up_step_mult;
    int tilt_up_step_repeat;
    int tilt_up_step_abs_max;

    int tilt_down_step_mult;
    int tilt_down_step_repeat;
    int tilt_down_step_abs_max;

    int pan_speed_step;
    int tilt_speed_step;
    int set_speed_each_move;

    int continuous_mode;
    int worker_interval_ms;
    int continuous_step_div;
    int continuous_rep;

    int absrel_chunk_steps;
    int absrel_interval_ms;

    int zoom_supported;
    int debug_log;
} ptz_config_t;

typedef struct ptz_ctx {
    ptz_config_t cfg;

    /* Runtime state for "continuous" moves.
       Pure library: no fork()/threads. The caller must call ptz_tick() periodically.
       When continuous_mode is enabled, ptz_move_dir() arms a movement and returns.
       The movement runs only while this process keeps calling ptz_tick(). */
    struct {
        bool active;
        char dir[8];
        int step;
        int rep;
        unsigned long fd_addr;
        struct timespec next_due;
    } cont[2];
} ptz_ctx_t;

/* Defaults + config loading */
void ptz_config_init_defaults(ptz_config_t *cfg);
/* Load KEY=VALUE overrides (same keys as the old file). Returns 0 on success, -1 on open/read error. */
int ptz_config_load_file(ptz_config_t *cfg, const char *path);

/* Context */
int ptz_ctx_init(ptz_ctx_t *ctx, const ptz_config_t *cfg);

/* Position state */
int ptz_get_position(const ptz_ctx_t *ctx, int *pan_deg, int *tilt_deg, int *zoom);
int ptz_set_position(const ptz_ctx_t *ctx, int pan_deg, int tilt_deg, int zoom);

/* Movements */
int ptz_move_dir(ptz_ctx_t *ctx, const char *dir, const char *speed);
int ptz_stop(ptz_ctx_t *ctx);
int ptz_home(ptz_ctx_t *ctx);

/* Normalized coordinates in [-1,1] (as used by -j/-J in the original CLI). */
int ptz_move_abs(ptz_ctx_t *ctx, double x, double y, double z);
int ptz_move_rel(ptz_ctx_t *ctx, double dx, double dy, double dz);

/* Presets */
int ptz_move_preset(ptz_ctx_t *ctx, const char *preset_id);

/* Event-loop hook.
   Call this periodically (e.g. every 5-20ms) to execute any armed continuous movement.
   Returns 1 if it issued at least one motor command, 0 if nothing was due, -1 on error. */
int ptz_tick(ptz_ctx_t *ctx);

#ifdef __cplusplus
}
#endif

#endif /* PTZCTL_H */

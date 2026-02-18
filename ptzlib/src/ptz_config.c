#define _POSIX_C_SOURCE 200809L
#include "ptzctl.h"
#include "ptz_util.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define CFG_STR(X) \
    X("ANYKA_PROC", anyka_proc, "anyka_ipc") \
    X("STATE_DIR",  state_dir,  "/tmp/sd/custom/state") \
    X("LOG_FILE",   log_file,   "/tmp/sd/logs/ptz.log") \
    X("PAN_DEV",    pan_dev,    "/dev/motor0") \
    X("TILT_DEV",   tilt_dev,   "/dev/motor1")

#define CFG_HEX(X) \
    X("PAN_FD_ADDR",       pan_fd_addr,       0x537760UL) \
    X("TILT_FD_ADDR",      tilt_fd_addr,      0x5377d0UL) \
    X("IOCTL_MOVE",        ioctl_move,        0x40046d40UL) \
    X("IOCTL_STOP",        ioctl_stop,        0x40046d42UL) \
    X("IOCTL_SET_SPEED",   ioctl_set_speed,   0x40046d20UL) \
    X("IOCTL_GET_STATE",   ioctl_get_state,   0x40046d43UL) \
    X("IOCTL_TURN_MIDDLE", ioctl_turn_middle, 0x40046d60UL)

#define CFG_INT(X) \
    X("ANYKA_PID",              anyka_pid,              0) \
    X("MOTOR_BACKEND",          motor_backend,          0) \
    X("PAN_MAX_DEG",            pan_max_deg,            360) \
    X("PAN_TOTAL_STEPS",        pan_total_steps,        4096) \
    X("TILT_MAX_DEG",           tilt_max_deg,           196) \
    X("TILT_TOTAL_STEPS",       tilt_total_steps,       2230) \
    X("PAN_INVERT",             pan_invert,             0) \
    X("TILT_INVERT",            tilt_invert,            0) \
    X("STEP_MULT",              step_mult,              4) \
    X("STEP_REPEAT",            step_repeat,            8) \
    X("PAN_STEP_MULT",          pan_step_mult,          -1) \
    X("PAN_STEP_REPEAT",        pan_step_repeat,        -1) \
    X("TILT_STEP_MULT",         tilt_step_mult,         -1) \
    X("TILT_STEP_REPEAT",       tilt_step_repeat,       -1) \
    X("TILT_STEP_ABS_MAX",      tilt_step_abs_max,      0) \
    X("TILT_UP_STEP_MULT",      tilt_up_step_mult,      -1) \
    X("TILT_UP_STEP_REPEAT",    tilt_up_step_repeat,    -1) \
    X("TILT_UP_STEP_ABS_MAX",   tilt_up_step_abs_max,   0) \
    X("TILT_DOWN_STEP_MULT",    tilt_down_step_mult,    -1) \
    X("TILT_DOWN_STEP_REPEAT",  tilt_down_step_repeat,  -1) \
    X("TILT_DOWN_STEP_ABS_MAX", tilt_down_step_abs_max, 0) \
    X("PAN_SPEED_STEP",         pan_speed_step,         800) \
    X("TILT_SPEED_STEP",        tilt_speed_step,        600) \
    X("SET_SPEED_EACH_MOVE",    set_speed_each_move,    0) \
    X("CONTINUOUS_MODE",        continuous_mode,        1) \
    X("WORKER_INTERVAL_MS",     worker_interval_ms,     80) \
    X("CONTINUOUS_STEP_DIV",    continuous_step_div,    8) \
    X("CONTINUOUS_REP",         continuous_rep,         1) \
    X("ABSREL_CHUNK_STEPS",     absrel_chunk_steps,     64) \
    X("ABSREL_INTERVAL_MS",     absrel_interval_ms,     30) \
    X("ZOOM_SUPPORTED",         zoom_supported,         0) \
    X("DEBUG_LOG",              debug_log,              1)

void ptz_config_init_defaults(ptz_config_t *cfg) {
    memset(cfg, 0, sizeof(*cfg));

#define SET_STR(k, field, def) snprintf(cfg->field, sizeof(cfg->field), "%s", (def));
#define SET_HEX(k, field, def) cfg->field = (def);
#define SET_INT(k, field, def) cfg->field = (def);

    CFG_STR(SET_STR)
    CFG_HEX(SET_HEX)
    CFG_INT(SET_INT)

#undef SET_STR
#undef SET_HEX
#undef SET_INT
}

typedef enum { T_INT, T_HEX, T_STR } cfg_type_t;
typedef struct { const char *key; cfg_type_t t; size_t off; size_t sz; } cfg_entry_t;

#define OFFSETOF(type, field) ((size_t)&(((type*)0)->field))
#define E_INT(k, field) { (k), T_INT, OFFSETOF(ptz_config_t, field), 0 }
#define E_HEX(k, field) { (k), T_HEX, OFFSETOF(ptz_config_t, field), 0 }
#define E_STR(k, field) { (k), T_STR, OFFSETOF(ptz_config_t, field), sizeof(((ptz_config_t*)0)->field) }

static const cfg_entry_t CFG_MAP[] = {
#define MAP_STR(k, field, def) E_STR(k, field),
#define MAP_HEX(k, field, def) E_HEX(k, field),
#define MAP_INT(k, field, def) E_INT(k, field),

    CFG_STR(MAP_STR)
    CFG_HEX(MAP_HEX)
    CFG_INT(MAP_INT)

#undef MAP_STR
#undef MAP_HEX
#undef MAP_INT
};

static void apply_kv(ptz_config_t *cfg, const char *k, const char *v) {
    for (size_t i = 0; i < sizeof(CFG_MAP) / sizeof(CFG_MAP[0]); i++) {
        const cfg_entry_t *e = &CFG_MAP[i];
        if (strcmp(k, e->key) != 0) continue;

        uint8_t *base = (uint8_t*)cfg + e->off;
        if (e->t == T_INT) {
            int *p = (int*)base;
            *p = ptz_parse_int(v, *p);
        } else if (e->t == T_HEX) {
            unsigned long *p = (unsigned long*)base;
            *p = ptz_parse_hex(v, *p);
        } else {
            char *p = (char*)base;
            snprintf(p, e->sz, "%s", v ? v : "");
        }
        return;
    }
}

int ptz_config_load_file(ptz_config_t *cfg, const char *path) {
    if (!path || !*path) return -1;
    FILE *f = fopen(path, "r");
    if (!f) return -1;

    char line[512];
    while (fgets(line, sizeof(line), f)) {
        char *p = ptz_trim(line);
        if (!*p || *p == '#') continue;
        char *eq = strchr(p, '=');
        if (!eq) continue;
        *eq = '\0';
        apply_kv(cfg, ptz_trim(p), ptz_trim(eq + 1));
    }

    fclose(f);
    return 0;
}

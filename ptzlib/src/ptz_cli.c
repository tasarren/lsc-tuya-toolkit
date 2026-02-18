#define _POSIX_C_SOURCE 200809L
#include "ptzctl.h"
#include "ptz_util.h"

#include <stdio.h>
#include <string.h>
#include <signal.h>

static volatile sig_atomic_t g_stop = 0;
static void on_stop(int sig) { (void)sig; g_stop = 1; }

static void parse_triple(const char *triple, double *x, double *y, double *z) {
    *x = *y = *z = 0.0;
    if (!triple) return;
    (void)sscanf(triple, "%lf,%lf,%lf", x, y, z);
}

int main(int argc, char *argv[]) {
    ptz_config_t cfg;
    ptz_config_init_defaults(&cfg);

    const char *conf_path = "/tmp/sd/custom/configs/ptz.conf";
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-c") == 0 && i + 1 < argc) {
            conf_path = argv[++i];
        }
    }

    /* Best-effort: if missing, keep defaults. */
    (void)ptz_config_load_file(&cfg, conf_path);

    ptz_ctx_t ctx;
    if (ptz_ctx_init(&ctx, &cfg) != 0) return 1;

    if (argc >= 2 && strcmp(argv[1], "--get-position") == 0) {
        int x, y, z;
        (void)ptz_get_position(&ctx, &x, &y, &z);
        printf("%d,%d,%d\n", x, y, z);
        return 0;
    }

    if (argc >= 2 && strcmp(argv[1], "--is-moving") == 0) {
        puts("0");
        return 0;
    }

    const char *mode = "";
    const char *speed = "0.5";
    const char *triple = NULL;
    const char *preset = NULL;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-m") == 0 && i + 1 < argc) mode = argv[++i];
        else if (strcmp(argv[i], "-s") == 0 && i + 1 < argc) speed = argv[++i];
        else if (strcmp(argv[i], "-p") == 0 && i + 1 < argc) preset = argv[++i];
        else if (strcmp(argv[i], "-j") == 0 && i + 1 < argc) { mode = "abs"; triple = argv[++i]; }
        else if (strcmp(argv[i], "-J") == 0 && i + 1 < argc) { mode = "rel"; triple = argv[++i]; }
        else if (strcmp(argv[i], "-h") == 0) mode = "home";
    }

    if (strcmp(mode, "left") == 0 || strcmp(mode, "right") == 0 ||
        strcmp(mode, "up") == 0   || strcmp(mode, "down") == 0  ||
        strcmp(mode, "in") == 0   || strcmp(mode, "out") == 0) {
        int rc = ptz_move_dir(&ctx, mode, speed);
        if (rc != 0) return rc;

        /* With the pure library, continuous movement only exists while this process runs.
           If continuous_mode is enabled, stay in the foreground issuing periodic ticks until interrupted. */
        if (cfg.continuous_mode) {
            signal(SIGINT, on_stop);
            signal(SIGTERM, on_stop);
            while (!g_stop) {
                int t = ptz_tick(&ctx);
                if (t < 0) break;
                ptz_sleep_us(5000);
            }
            (void)ptz_stop(&ctx);
        }
        return 0;
    }

    if (strcmp(mode, "stop") == 0) return ptz_stop(&ctx);
    if (strcmp(mode, "home") == 0) return ptz_home(&ctx);

    if (strcmp(mode, "abs") == 0) {
        double x, y, z;
        parse_triple(triple, &x, &y, &z);
        return ptz_move_abs(&ctx, x, y, z);
    }

    if (strcmp(mode, "rel") == 0) {
        double dx, dy, dz;
        parse_triple(triple, &dx, &dy, &dz);
        return ptz_move_rel(&ctx, dx, dy, dz);
    }

    if (preset && *preset) return ptz_move_preset(&ctx, preset);

    return 0;
}

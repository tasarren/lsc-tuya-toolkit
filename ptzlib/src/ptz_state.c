#define _POSIX_C_SOURCE 200809L
#include "ptz_internal.h"

#include <stdio.h>
#include <stdlib.h>

int ptz_get_position(const ptz_ctx_t *ctx, int *pan_deg, int *tilt_deg, int *zoom) {
    if (!ctx || !pan_deg || !tilt_deg || !zoom) return -1;

    int x = 180, y = 98, z = 0;

    char path[512];
    ptz_state_path(&ctx->cfg, "ptz_position", path, sizeof(path));

    FILE *f = fopen(path, "r");
    if (f) {
        if (fscanf(f, "%d,%d,%d", &x, &y, &z) != 3) {
            x = 180; y = 98; z = 0;
        }
        fclose(f);
    }

    *pan_deg = x;
    *tilt_deg = y;
    *zoom = z;
    return 0;
}

int ptz_set_position(const ptz_ctx_t *ctx, int pan_deg, int tilt_deg, int zoom) {
    if (!ctx) return -1;

    char path[512];
    ptz_state_path(&ctx->cfg, "ptz_position", path, sizeof(path));

    ptz_ensure_state_dir(&ctx->cfg);

    FILE *f = fopen(path, "w");
    if (!f) return -1;
    fprintf(f, "%d,%d,%d\n", pan_deg, tilt_deg, zoom);
    fclose(f);
    return 0;
}

int ptz_move_preset(ptz_ctx_t *ctx, const char *preset_id) {
    if (!ctx || !preset_id || !*preset_id) return -1;

    char ppath[512];
    ptz_state_path(&ctx->cfg, "ptz_presets.db", ppath, sizeof(ppath));

    FILE *f = fopen(ppath, "r");
    if (!f) {
        ptz_log_line(&ctx->cfg, "preset %s not found", preset_id);
        return 1;
    }

    int wanted = atoi(preset_id);

    char line[256];
    while (fgets(line, sizeof(line), f)) {
        int id, px, py, pz;
        char name[128];

        if (sscanf(line, "%d,%127[^,],%d,%d,%d", &id, name, &px, &py, &pz) == 5 && id == wanted) {
            fclose(f);
            (void)ptz_set_position(ctx, px, py, pz);
            ptz_log_line(&ctx->cfg, "move preset=%d -> pos=%d,%d,%d", id, px, py, pz);
            return 0;
        }
    }

    fclose(f);
    ptz_log_line(&ctx->cfg, "preset %s not found", preset_id);
    return 1;
}

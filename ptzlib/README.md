ptzlib (libptzctl)
================

An attempt to control Anyka / Tuya / LSC Securty PTZ Cameras

Build
-----
    make

Outputs:
- `libptzctl.a`
- `ptzctl`

Clean:
    make clean

Library API (high-level)
------------------------
Initialize defaults, load config overrides, create a context:

    ptz_config_t cfg;
    ptz_config_init_defaults(&cfg);
    ptz_config_load_file(&cfg, "/tmp/sd/custom/configs/ptz.conf");

    ptz_ctx_t ctx;
    ptz_ctx_init(&ctx, &cfg);

Then call movement APIs:

- `ptz_move_dir(&ctx, "left|right|up|down|in|out", "0.5")`
- `ptz_stop(&ctx)`
- `ptz_home(&ctx)` (see note below)
- `ptz_move_abs(&ctx, x, y, z)` where x/y/z are in [-1,1]
- `ptz_move_rel(&ctx, dx, dy, dz)` where dx/dy/dz are normalized deltas
- `ptz_move_preset(&ctx, "1")`

Continuous mode
---------------
This library is "pure": it does not `fork()` or start background workers.

If `CONTINUOUS_MODE=1`, `ptz_move_dir()` only arms the movement. You must call `ptz_tick(&ctx)` periodically
(e.g. every 5–20ms) to keep the movement running. The supplied `ptzctl` CLI stays in the foreground and calls
`ptz_tick()` until SIGINT/SIGTERM, then sends a best-effort stop.

Config keys
-----------
The config file is `KEY=VALUE` lines.

Motor backends
--------------
This library supports two ways to talk to the motor driver:

1) Direct device nodes (recommended on firmwares that load `ak_motor.ko`):
   - `PAN_DEV=/dev/motor0`
   - `TILT_DEV=/dev/motor1`
   - `MOTOR_BACKEND=1` (or `0` for auto)

2) Legacy indirection via an existing process that already opened the device:
   - `PAN_FD_ADDR=...` and `TILT_FD_ADDR=...` (addresses inside the target process)
   - `ANYKA_PROC=anyka_ipc` or `ANYKA_PID=...`
   - `MOTOR_BACKEND=2` (or `0` for auto)

In AUTO mode (`MOTOR_BACKEND=0`), it will use `/dev/motorX` if present, otherwise fall back to `/proc/PID/fd`.

Keys
----
ANYKA_PROC, ANYKA_PID, STATE_DIR, LOG_FILE,
PAN_DEV, TILT_DEV, MOTOR_BACKEND,
PAN_FD_ADDR, TILT_FD_ADDR,
IOCTL_MOVE, IOCTL_STOP, IOCTL_SET_SPEED, IOCTL_GET_STATE, IOCTL_TURN_MIDDLE,
PAN_MAX_DEG, PAN_TOTAL_STEPS, TILT_MAX_DEG, TILT_TOTAL_STEPS,
PAN_INVERT, TILT_INVERT,
STEP_MULT, STEP_REPEAT, PAN_STEP_MULT, PAN_STEP_REPEAT,
TILT_STEP_MULT, TILT_STEP_REPEAT, TILT_STEP_ABS_MAX,
TILT_UP_STEP_MULT, TILT_UP_STEP_REPEAT, TILT_UP_STEP_ABS_MAX,
TILT_DOWN_STEP_MULT, TILT_DOWN_STEP_REPEAT, TILT_DOWN_STEP_ABS_MAX,
PAN_SPEED_STEP, TILT_SPEED_STEP, SET_SPEED_EACH_MOVE,
CONTINUOUS_MODE, WORKER_INTERVAL_MS, CONTINUOUS_STEP_DIV, CONTINUOUS_REP,
ABSREL_CHUNK_STEPS, ABSREL_INTERVAL_MS,
ZOOM_SUPPORTED, DEBUG_LOG

Homing / centering
------------------
If `IOCTL_TURN_MIDDLE` is configured (default: `0x40046d60` on the observed ak_motor.ko ABI), `ptz_home()` will call
that ioctl on both axes to ask the driver to center the motors. It always updates the saved position to the midpoint.

Return value:
- `0` if at least one axis accepted the ioctl
- `-1` if both ioctls failed (hardware centering likely did not run)

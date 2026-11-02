# SD card payload

The camera does not run TuyHA. It runs stock `anyka_ipc`. The SD card exists to bind-mount a hacked database over the factory one before that process starts, then get out of the way.

Repo layout root: [sd_card/](../sd_card).

From the repository root, `tuyha create` writes generated DBs, identity INI and manifest directly to `sd_card/custom/state/`; all TLS files go under `state/mqtt/`. It replaces only its generated outputs and preserves other state. Copy the contents of `sd_card/` to the card root. See [CLI behavior](cli.md) before regenerating an existing deployment.

See the [SD boot diagram](diagrams/sd-boot.md) and [entrypoint and helper diagrams](diagrams/sd-helpers.md) for script branches and security limits.

## Why the hijack exists

Firmware `service.sh` sees `_ht_ap_mode.conf` on the card, copies `/mnt/hostapd` to `/tmp/hostapd`, and executes it **before** the normal daemon. [sd_card/hostapd](../sd_card/hostapd) mounts the card at `/tmp/sd`, runs `hack_stage_1.sh`, drops the factory AP address on `wlan0`, deletes the `/tmp` copies of the AP marker, and lets `anyka_ipc` start.

Keep `_ht_ap_mode.conf` on the SD card. Only the `/tmp` copies are removed after the hijack. Without the marker, the next boot does not run the payload.

`_ak39_factory.ini` is a different boot. An empty file on the SD root selects factory test mode and RTSP on `:554/main_ch`. TuyHA's local MQTT path does **not** use factory mode. Ship the marker disabled (`.disabled`) unless you want that mode.

## Stage 1: capture this camera once

[hack_stage_1.sh](../sd_card/custom/scripts/hack_stage_1.sh) runs only until `custom/state/.stage1` exists. It copies flash files into `custom/state/`:

- `/usr/local/_ht_hw_settings.ini` — encoder, sensor, motor. **Per camera.** Not in git.
- `/etc/config/_ht_sw_settings.ini` — software flags. The repo ships a portable copy.
- `/usr/local/etc/onvif_simple_server.conf` and `lighttpd.conf` — overwritten by the copies we ship, then tuned at boot.
- Factory `tuya_user.db` / `tuya_enckey.db` as `*.original.db`.

If `.stage1` already exists, stage 1 does nothing. Moving the card to another camera without deleting `.stage1` and `_ht_hw_settings.ini` bind-mounts the old camera's encoder settings onto the new one.

## Stage 2: what actually changes the running system

[hack_stage_2.sh](../sd_card/custom/scripts/hack_stage_2.sh) bind-mounts SD files over flash:

| SD path | Mounted over | Why |
|---|---|---|
| `custom/state/tuya_user.hacked.db` | `/etc/config/tuya_user.db` | Local broker, Wi-Fi, P2P seed. If this file is missing, stage 2 attempts to mount `tuya_user.original.db`; the camera may reconnect to the factory cloud. |
| `custom/state/tuya_enckey.hacked.db` | `/etc/config/tuya_enckey.db` | Key for that user DB. The pair must match. |
| `custom/state/_ht_uuid.ini` | `/etc/config/_ht_uuid.ini` | Identity the binary reads beside the DB. latin-1, `encrypt = 0`. |
| `custom/state/_ht_sw_settings.ini` | `/etc/config/_ht_sw_settings.ini` | Stage 2 forces `bool_has_bind_service`, `bool_has_config_wifi`, and `bool_onvif_switch` to `1` before the mount. |
| `custom/state/_ht_hw_settings.ini` | `/usr/local/_ht_hw_settings.ini` | This camera's encoder. Copied from flash when missing. |
| `custom/state/onvif_simple_server.conf` | `/usr/local/etc/onvif_simple_server.conf` | Profile width, height, and type rewritten from the hw INI immediately before the mount. |

`bool_onvif_switch=1` is what starts non-factory RTSP (`:88` / `:89`) after media init. It is not the same switch as `ONVIF=` in `hack.conf`. That flag only starts the lighttpd ONVIF helper on `:8080`.

`bool_has_bind_service=1` skips the Anyka QR bind screen. `bool_has_config_wifi=1` lets `main()` treat Wi-Fi as already configured. Neither flag writes `wpa_supplicant` config. Station join comes from the DB. See [boot to RTSP](./LOCAL_RTSP.md).

Stage 2 also bind-mounts [anyka_ipc.sh](../sd_card/custom/scripts/anyka_ipc.sh) over `/usr/sbin/anyka_ipc.sh`. Every later `start` and `restart` goes through that script, not through stage 2.

## The on-camera MQTT latch

The firmware waits for MQTT before it starts media and RTSP. The payload answers that gate on the camera itself:

| SD path | Role |
|---|---|
| `custom/bin/mqtt_latch` | Static ARM binary. Listens on `0.0.0.0:8883`, accepts one TCP connection without client authentication, presents `custom/state/mqtt/server.crt`, and answers CONNECT, SUBSCRIBE, PUBLISH, and PING. It exits when its loopback probe detects `:88` listening, or earlier on connection failure or disconnect. |
| `custom/bin/libnobind.so` | `LD_PRELOAD` for `anyka_ipc`. Ignores `SO_BINDTODEVICE`. The firmware pins its MQTT socket to `wlan0`, which makes `127.0.0.1` unreachable; with the preload the connection reaches the latch. |
| `custom/state/mqtt/server.crt`, `server.key` | Generated in place with the matching DB pair. Gitignored. |

`anyka_ipc.sh` `start()` launches the latch when its prerequisites exist, waits at most 15 seconds for any `:8883` listener, then starts `anyka_ipc` with the preload when available. It starts firmware even if the port check fails; the check does not prove listener ownership. `stop()` kills both. `entrypoint.sh` is launched after the camera process, so it cannot own the latch.

If `custom/state/mqtt/` is missing, `start()` skips the latch. Use that when a database points at an external broker instead.

Both binaries are included, so normal setup does not need a compiler. Rebuild from the repository root when changing [mqtt_latch.c](../latch/mqtt_latch.c) or [nobind.c](../latch/nobind.c):

```bash
./latch/build.sh
```

The script uses an available ARM cross-compiler or a Docker build image, and writes to the repository's `sd_card/custom/bin/` by default. Downloads and compiler dependencies need network access on an uncached build. `LATCH_OUTPUT_DIR` and `LATCH_CACHE_DIR` select separate output and cache directories; `LATCH_CC` chooses a compiler. The build checks the latch's ARM32 ELF/static linkage, not camera behavior. See the [build diagram](diagrams/generation.md#optional-latch-rebuild).

## Wi-Fi overlay

[wifi_apply.sh](../sd_card/custom/scripts/wifi_apply.sh) defaults to `MODE=none` and reads [hack.conf](../sd_card/custom/configs/hack.conf). The checked-in `hack.conf` does not override that default. [wifi.conf](../sd_card/custom/configs/wifi.conf) also says `MODE=none`, but the helper does not read it; changing that file alone has no effect on the helper.

With `MODE=none`, the helper may stop the factory AP DHCP server and clear the factory AP address (`172.16.10.1`), but it does not kill `wpa_supplicant`. Do not set `MODE=sta` in `hack.conf` for the firmware-managed path. That debug mode can kill `wpa_supplicant` and race the firmware join.

## What not to ship between cameras

- `custom/state/_ht_hw_settings.ini` — gitignored. First boot on a new camera recreates it from flash.
- `tuya_user.hacked.db` / `tuya_enckey.hacked.db` — generate per deployment. Gitignored.
- `_ht_uuid.ini` — generated with the DBs. Gitignored.
- `custom/state/mqtt/` — latch certificate and key from that generation. Gitignored.
- A used `.stage1` marker — delete it together with the hw INI when the card moves.

Do not delete runtime INIs with `rsync --delete` when refreshing DBs.

## Logs

`custom/env.sh` writes `/tmp/sd/logs/<script>.<timestamp>.log`. Stage 2 can log `Hack Stage 2 done.` even if a mount failed. Check the database mount attempts and any `mount failed` messages. If the hacked DB is missing, the camera may use the original cloud DB.

Look for the wrapper's `anyka_ipc.sh script starting` message in `anyka_ipc.<timestamp>.log`. A later `mqtt_latch listening` message means its port check observed some listener on `:8883`, not that the latch owns it. The wrapper silently skips latch startup if the binary, certificate or key is missing.

An inode-replacing update on a running camera can leave the old bind-mounted file active. Prefer a complete card update with the camera off, followed by a power-cycle, rather than editing active DBs or INIs in place.

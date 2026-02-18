# LSC Camera  Root Toolkit

This file documents the current firmware findings and a practical SD-card flow to boot custom scripts and keep local
services.

This findings belongs to version `6.2863.123` but it should work on any version, as long as you teak the config files.

If this project was useful to you, please consider supporting me.

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/tasarren)

## Key boot findings from the dump

- Boot chain: `init -> /etc/init.d/rcS -> /etc/init.d/rc.local -> /usr/sbin/main.sh`.
- `main.sh` launches `/tmp/service.sh start` (copied from `/usr/sbin/service.sh`).
- `service.sh` mounts TF card and checks marker files under `/mnt`.
- If `_ht_ap_mode.conf` exists, firmware copies `/mnt/hostapd` to `/tmp/hostapd` and wifi scripts execute it.
This is where we hijack the system. Because this is run before really starting the daemon/anyka_ipc, we can
modify the system, and then allow normal startup with poisoned scripts.
- If `_ht_get_log.conf` exists, firmware won't unmount our SD card from `/mnt` and will also dump debug logs into
  `/ht_log` folder 
- If `_ht_av_mode.conf` exists, an Audio/Video test will begin, booting up a FTP server to unknown purposes.
- If `ak39_factory.ini` exists, the system will boot in factory testing mode
 
This is the startup hijack point we keep using.

## SD payload layout

Use `sd_card/` as the SD card root content:

- `_ht_ap_mode.conf` - required marker to trigger custom `hostapd` execution.
- `_ak39_factory.ini` - required marker to trigger factory test mode.
- `hostapd` - launcher (executed by firmware; runs `hack.sh`).
- `hack.sh` - tiny bootstrap called by `hostapd`.
- `logs/` - persistent logs written to SD.
- `custom/` - all custom scripts/configs/binaries.

## Factory Testing Mode

On this firmware, an empty factory marker file enables a Factory Testing Mode 
with a ready to use RTSP server.

This is really all what you need if you only want a RTSP camera, without PTZ, just video.

- Create an empty `_ak39_factory.ini` on the SD root (this repo includes an empty
  `sd_card/_ak39_factory.ini`).
- Reboot.
- RTSP listens on port `554`.
- The working URL on this device is:

```
rtsp://CAMERA_IP:554/main_ch
```

> If you get `RTSP/1.0 454 Session Not Found` on `/videoMain`, try `/main_ch`.

Factory mode also plays loud startup prompt audio by default.
In this SD payload you can disable it with:

- `MUTE_FACTORY_PROMPT=1` in `sd_card/root_system/custom/configs/hack.conf`

### What `_ak39_factory.ini` actually is

From Ghidra analysis of `anyka_ipc`:

- Factory mode is detected by `access("/tmp/_ak39_factory.ini", 0)`.
- The file is parsed using `iniparser_load("/tmp/_ak39_factory.ini")`.
- The code looks up keys in the `section:key` form (iniparser style), e.g.:
    - `wifi_station:ssid`
    - `wifi_station:passphrase`
    - `wifi_station:ip`
    - `wifi_station:netmask`
    - `wifi_station:gateway`
    - `aging_test:aging_value`

Note: boot `service.sh` copies only the first 1024 bytes from SD (`dd ... bs=1024 count=1`), so keep this file small.

## ONVIF

This firmware includes an ONVIF mini stack:

- `/usr/local/bin/mini_onvif_service.sh` starts `lighttpd`, `wsd_simple_server`, and `onvif_notify_server`.
- In the SD payload, set `ONVIF=1` in `sd_card/custom/configs/hack.conf` to start it.

Notes:

- ONVIF uses port `8080` on this firmware (lighttpd).
  ``- When `ONVIF=1`, the scripts write `logs/onvif_status.txt` on the SD card with process/port probes.
  ``

> You can also enable ONVIF with the stock Tuya APP by setting `bool_onvif_switch = 1` in `_ht_sw_settings.ini`

### Configuring ONVIF profiles

The ONVIF service uses `/usr/local/etc/onvif_simple_server.conf`.
In this SD payload we can override it (non-flash) via a bind mount:

- SD file: `sd_card/custom/configs/onvif_simple_server.conf`
- Mounted to: `/usr/local/etc/onvif_simple_server.conf`

### ONVIF PTZ helpers (SD-based)

Some firmware builds advertise PTZ via ONVIF but do not ship the expected helper commands in `/usr/local/bin`.

This payload provides replacements from SD:

- `/tmp/sd/custom/scripts/ptz_move`
- `/tmp/sd/custom/scripts/get_position`
- `/tmp/sd/custom/scripts/is_moving`
- `/tmp/sd/custom/scripts/ptz_presets.sh`

The PTZ wrappers call:

- `/tmp/sd/custom/bin/ptzctl`

`ptzctl` reads PTZ settings directly from:

- `sd_card/custom/configs/ptz.conf`

Key tuning fields in `ptz.conf`:

- `PAN_FD_ADDR`, `TILT_FD_ADDR`, `IOCTL_MOVE`
- `PAN_INVERT`, `TILT_INVERT`,
- `STEP_MULT`, `STEP_REPEAT`
- `DEBUG_LOG` (set `1` to write `ptz.log`, `0` to disable PTZ logging)

The ONVIF config points directly to these SD scripts when:

- `ONVIF=1`
- `ONVIF_PTZ=1`

If PTZ actions fail in clients (for example Home Assistant), check:

- `logs/ptz.log`

### Building `ptzctl`:

- `./build_ptzctl.sh`

Docker-based isolated ARM build (recommended):

- `./docker/build_binaries.sh`

This uses a containerized ARM GCC toolchain and copies built artifacts back with `docker cp`.

Default output path:

- `sd_card/custom/bin/ptzctl`

## Configuration-driven behavior

All custom behavior is controlled by `custom/configs/hack.conf` (strict shell `KEY=value`).

Important toggles:

- `DUMP_FORCE=1` forces dump to run again even if done flag exists.

## How to use (quick steps)

1. Format SD card as FAT32.
2. Tweak the config files in `sd_card/custom/configs/` folder.
3. Copy everything from `sd_card/` to SD root.
4. Boot camera with SD inserted.
5. Enjoy

### What does it do
1. Dumps the entire filesystem from your device into `sd_card/dumps` as a backup
2. Injects some payloads to prevent regular boot.
3. Creates `/etc/shadow` with an user `root` with password `telnet`
> You can create your own password replacing `sd_card/shadow` file
  
For normal behavior:

- Do not use the SD Card :)

## Wi-Fi setup from SD
You should use `sd_card/_ak39_factory.ini` to setup your Wi-Fi settings to allow Anyka IPC to set it up for you.
> You can leave ip, netmask and gateway blank to use DHCP

If you do not want to use this (whatever), ensure `_ak39_factory.ini` is empty and edit `sd_card/custom/configs/wifi.conf`.

This will start wpa_supplicant with the settings provided in `wifi.conf`

Notes:
- `WIFI_MODE=none` leaves networking unchanged (stock firmware manages it).
- The scripts use `wpa_supplicant` + `wpa_cli` via `/usr/sbin/station_connect.sh`.

## Logs

All custom logs are written to the SD card under `SD_DIR/logs/` (where `SD_DIR` is `/tmp/sd` on-device).
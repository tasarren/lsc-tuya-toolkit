# SD entrypoint and helpers

These diagrams describe the checked-in scripts and configuration, not proof that they ran on a camera. The wrapper starts `entrypoint.sh` in the background after launching `anyka_ipc`. The sandbox path can also run the entrypoint directly. See [SD deployment and boot](sd-boot.md).

## Entrypoint sequencing

```mermaid
flowchart TD
  A["Entrypoint starts asynchronously from wrapper, or directly in sandbox"] --> B{"SAVE_SYSLOG is 1, log exists, not yet saved?"}
  B -- "yes" --> C["Attempt to save syslog tail once per boot"]
  B -- "no" --> D{"Sandbox mode?"}
  C --> D
  D -- "no" --> E["Wait for anyka_ipc process, then sleep 30 seconds"]
  D -- "yes" --> F["Start Wi-Fi, remote, offline and ONVIF helpers in background"]
  E --> F
  F --> G{"Sandbox mode?"}
  G -- "no" --> H["Poll listed listening ports for up to 30 seconds"]
  G -- "yes" --> I["Log entrypoint done"]
  H --> I
```

*The entrypoint launches helpers concurrently; it does not wait for them to complete before its port check.*

Sources: [entrypoint.sh](../../sd_card/custom/scripts/entrypoint.sh), [wrapper](../../sd_card/custom/scripts/anyka_ipc.sh), and [hostapd](../../sd_card/hostapd). The syslog copy is attempted, not confirmed. The port check includes ports other than RTSP and can match a listener without process identification; it does not establish RTSP or decoded video.

## Helper configuration branches

```mermaid
flowchart TD
  W["wifi_apply: load default config"] --> X{"MODE"}
  X -- "none or empty" --> Y["Stop AP DHCP; clear address only if factory AP address is present"]
  X -- "sta with SSID" --> Z["Stop Wi-Fi stack; start station connector; optionally DHCP"]
  X -- "sta without SSID or unknown mode" --> Q["Return error"]

  R["remote: start telnet and FTP helper scripts"] --> T{"TELNET is 1?"}
  T -- "yes" --> U["Monitor and attempt to restart unauthenticated shell"]
  T -- "no" --> V["Do not start telnet"]
  R --> S{"FTP is 1?"}
  S -- "yes" --> N["Attempt anonymous writable FTP rooted at /"]
  S -- "no" --> O["Do not start FTP"]

  F["offline helper"] --> G{"OFFLINE is 1, hosts file exists, no hosts mount?"}
  G -- "yes" --> H["Attempt bind mount over /etc/hosts"]
  G -- "no" --> I["Skip mount"]

  J["ONVIF helper"] --> K{"ONVIF is 1?"}
  K -- "yes" --> L["Attempt helper service if not already running"]
  K -- "no" --> M["Do not start optional helper"]
```

*Each helper reads configuration independently; the branches can run concurrently.*

Sources: [wifi_apply.sh](../../sd_card/custom/scripts/wifi_apply.sh), [remote.sh](../../sd_card/custom/scripts/remote.sh), [telnet.sh](../../sd_card/custom/scripts/telnet.sh), [ftp.sh](../../sd_card/custom/scripts/ftp.sh), [offline.sh](../../sd_card/custom/scripts/offline.sh), [onvif.sh](../../sd_card/custom/scripts/onvif.sh), and [hack.conf](../../sd_card/custom/configs/hack.conf). With the checked-in `hack.conf`, `TELNET=1` and port `24`, `FTP=0`, `OFFLINE=1`, `ONVIF=0`, and `SAVE_SYSLOG=0`. Telnet, if started, gives an unauthenticated shell; isolate the camera from untrusted networks or disable it. If enabled, the FTP helper attempts to start anonymous writable FTP rooted at `/`. A hosts bind is not proof that all cloud traffic is blocked; check the mount and network policy.

The Wi-Fi helper calls `load_cfg` with no filename, so it reads `hack.conf`, not `wifi.conf`. Its default `MODE=none` applies when `hack.conf` does not override it. The checked-in `wifi.conf` also says `MODE=none`, but changing that file alone does not change this helper's mode. `MODE=sta` is a debug path and may race the firmware join. The optional SD `ONVIF` helper is distinct from the firmware `bool_onvif_switch` set by stage 2. A log message after an attempted mount or service start does not prove success.

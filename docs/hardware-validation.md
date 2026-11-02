# Validate a camera deployment

Prove that the intended scratch artifacts were mounted, passed the local MQTT gate and produced both UDP video streams. Offline `PASS`, open ports and MQTT online alone are insufficient.

The project reports one successful LSC scratch deployment. Record fresh evidence for another camera, firmware, SD revision or changed artifact set. See [evidence scope](research/index.md#evidence-and-scope) and the [decision diagram](diagrams/validation.md).

## Prepare

- Use a FAT32 card carrying the contents of `sd_card/` at its root.
- Use a trusted, isolated LAN. The latch listens on all interfaces without client authentication and accepts one TCP connection.
- Use serial or carefully isolated telnet (`TELNET=1`, port `24`) for diagnostics. Telnet exposes an unauthenticated shell; disable it when finished.
- Have `mpv` or `ffmpeg` on the same LAN.
- Keep artifacts and raw evidence private. Logs, mounts, paths and manifests can contain identifying or secret values.

## 1. Create and check offline

> CLI passwords can appear in shell history and process listings. Never record real arguments in shared evidence.

```bash
tuyha create --wifi-ssid "<WIFI_SSID>" --wifi-password "<WIFI_PASSWORD>"
tuyha verify --file sd_card/custom/state/tuya_user.hacked.db --scratch
```

The defaults target `127.0.0.1:8883`. Record only redacted command arguments and safe verification output. Inspect `manifest.json` privately for source kind and trust metadata. No external broker is needed.

## 2. Deploy one matched set

Creation writes the ready-to-copy state tree by default. Copy the contents of `sd_card/` to the card root, including generated `custom/state/` and its `mqtt/` directory. No separate artifact-copy step is needed.

Confirm the card also carries `custom/bin/mqtt_latch`, `custom/bin/libnobind.so` and the wrapper `custom/scripts/anyka_ipc.sh`. Preserve this camera's hardware INI and first-boot state; do not synchronize a used state folder between cameras.

> If the hacked user DB is missing, stage 2 attempts factory-DB fallback. If any bind mount fails, factory state can remain active. Either case can reconnect the camera to the Tuya cloud. Check active mounts after boot; presence of generated files is not sufficient.

## 3. Boot and confirm selection

1. Insert the card and power-cycle the camera.
2. Inspect `/tmp/sd/logs/stage2.<timestamp>.log` for DB/INI mount attempts and failures.
3. Confirm active mounts for `/etc/config/tuya_user.db`, `/etc/config/tuya_enckey.db` and `/etc/config/_ht_uuid.ini` select the intended SD files. Record the outcome privately. `Hack Stage 2 done.` is not proof.
4. Confirm real station association and IP address. `WSS_CONNECTING` alone is not a join.
5. Confirm the preload on the camera:

   ```bash
   grep nobind /proc/$(pidof anyka_ipc)/maps
   ```

The preload removes socket binding to `wlan0` for the loopback path. It does not force the firmware MQTT status to online.

## 4. Check boot progression

Inspect `/tmp/sd/logs/anyka_ipc.<timestamp>.log` and firmware logs for these checkpoints:

| Checkpoint | Meaning and limit |
|---|---|
| `mqtt_latch listening` | Listener started; does not prove the camera owns its sole connection. |
| `wait mqtt online.` followed by `tuya mqtt online.` | Initial MQTT gate passed. Not media/RTSP proof. |
| `media init complete.` | Media initialization returned on this path. |
| `rtsp start.` and listeners on `:88`, `:89` | Continue to actual decode checks. |

The wrapper waits at most 15 seconds for any `:8883` listener and starts firmware even if that check fails. The latch can exit on TLS/connection failure or disconnect, not only its loopback `:88` probe. Do not infer success from its exit.

## 5. Decode both streams

```bash
mpv --rtsp-transport=udp --no-cache rtsp://CAMERA_IP:88/videoMain
mpv --rtsp-transport=udp --no-cache rtsp://CAMERA_IP:89/videoSub
```

Play each for at least six seconds. Initial undecodable NALU/POC messages can last until a keyframe, around two seconds in the reported setup. Continued errors or a TCP-only connection are not a pass.

After the latch exits, check both streams again. Record whether playback continues, not merely whether ports answer. Port `:8080` belongs to the optional ONVIF helper and is not required (`ONVIF=0` by default).

## Record the outcome

Keep a private run record with firmware version, SD/source revision, redacted creation inputs, manifest reference, active mounts, preload mapping, boot checkpoints, and decoded main/substream observations before and after latch exit.

- **Pass:** intended scratch files selected; local MQTT and media checkpoints reached; both UDP streams decode and remain usable after latch exit.
- **Fail:** a measured checkpoint failed. Record its evidence and use [troubleshooting](troubleshooting.md). A symptom does not establish a unique cause.
- **Blocked:** camera access or required observations unavailable. Do not replace missing evidence with another deployment's logs or a generated summary.

Review and redact all evidence before sharing. Never include DBs, full JSON dumps, identity values or private key bodies in a public report.

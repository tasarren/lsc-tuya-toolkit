# Troubleshooting

Start with [offline checks](cli.md#verify-an-existing-database), then [hardware validation](hardware-validation.md). Do not change identity or network settings based on one log line alone.

## CLI errors

| Problem | Check |
|---|---|
| Arguments rejected | Use `tuyha create`, `tuyha dump` or `tuyha verify`. Read that command's `--help`. Old top-level generation and profile commands no longer exist. |
| Output rejected | `create` accepts an existing state directory and replaces only its generated files, but rejects symlink targets/wrong file types. `dump` never overwrites an existing file. |
| Custom DB name | Add `--enckey PATH`. Names starting with `tuya_user.` and ending with `.db` infer the matching `tuya_enckey.` sibling, including bare `tuya_user.db`. |
| Cannot read or write | Check the input files, matching enckey, parent path and permissions. `server.key` cannot decode a database. |
| Invalid JSON input | Use a full `tuyha-db-v1` dump from `dump`. Preserve `format`, record envelopes and encodings. JSONC and old profile files are not accepted. |
| `verify` returns `FAIL` | Correct the named record or format issue. General verification accepts inactive data; add `--scratch` only when checking the generated local-boot shape. |
| Generic invalid-input message | Check DB/key pairing, override lengths and JSON encodings. Error details intentionally omit input values to avoid leaking secrets. |
| Publication recovery failed | Preserve the reported private recovery directory. Do not boot from a potentially mixed set; recover or regenerate one complete set before SD copy. |

Exit `0` means command success, `1` means record checks failed, and `2` means argument, input or I/O failure. A `PASS` is offline evidence only.

## Camera does not join or boot

1. Confirm that both generated databases and `_ht_uuid.ini` came from the same run.
2. Check `<card>/logs/stage2.<timestamp>.log`, or `/tmp/sd/logs/stage2.<timestamp>.log` on the camera, for mount attempts and errors.
3. Confirm the active mounts for `/etc/config/tuya_user.db`, `/etc/config/tuya_enckey.db` and `/etc/config/_ht_uuid.ini`.
4. Check Wi-Fi association and IP address before diagnosing MQTT.

> Missing hacked user DB triggers an attempted factory-DB fallback. Failed bind mounts can also leave factory state active. The camera may reconnect to the Tuya cloud. `Hack Stage 2 done.` and file presence do not prove the generated files were selected.

The Wi-Fi helper defaults to `MODE=none` and reads `hack.conf`, not `wifi.conf`. Do not enable debug `MODE=sta` for firmware-managed Wi-Fi; it can kill `wpa_supplicant` during the firmware join.

## Interpret boot checkpoints

These are leads for the examined firmware, not unique diagnoses:

| Observation | Next check |
|---|---|
| `WSS_CONNECTING` | Check real station association and IP. Polling status is not proof of a join. |
| `wifi do not config.` | This concerns Anyka's saved SSID buffer. Check `gw_wsm` and whether the station worker ran. |
| `Start AP SSID:SmartLife-` | Inspect configuration type and schema record. Confirm the intended DB was mounted. |
| Repeated `wait mqtt online.` | Check listener ownership, latch log, preload mapping and TLS. Another client can occupy the latch's sole connection. |
| Loopback connect failure before MQTT online | Confirm `libnobind.so` is loaded and the wrapper is active. A failure code alone does not establish the cause. |
| TLS rejection | Recopy the DB pair, INI and server certificate/key from one run. Check name, trust and expiry; do not disable verification. |
| `tuya mqtt online.` then repeated `get p2p auth failed` | Check the seeded `p2p_type` and `p2p_auth_info` bytes. MQTT alone does not complete media init. |
| `media init complete.` but no RTSP | Check `bool_onvif_switch` in the active software INI and later boot logs. The optional `ONVIF` helper flag is separate. |
| Latch disappears | Check why it exited. It can exit on failure or disconnect as well as a loopback `:88` probe; absence proves neither RTSP nor decoded video. |

The wrapper waits at most 15 seconds for any listener on `:8883`, then starts firmware regardless. Neither this check nor the latch's `:88` probe identifies the intended server or proves playback.

## Video and camera-specific settings

- Use RTSP over UDP. The examined server can stall on interleaved TCP with `CSeq 5 expected, 0 received`.
- Initial NALU/POC errors can last until the next keyframe, about two seconds in the reported setup. Persistent errors need capture and codec checks.
- Wrong ONVIF resolution can indicate hardware settings from another camera. With the camera powered off, preserve private backups, then remove only `custom/state/_ht_hw_settings.ini` and `custom/state/.stage1` on the card so first-boot capture runs again.
- Apply a new artifact set with a power-cycle. Editing a mounted INI does not update the running firmware's parsed state.

See [SD behavior](SD_CARD.md), [boot to RTSP](LOCAL_RTSP.md) and [validation diagram](diagrams/validation.md).

## Safe support evidence

Do not share raw dumps, DB pairs, identity INIs, private keys or unreviewed logs/manifests. Redact Wi-Fi credentials, camera IDs and authentication values. Include command names without secret arguments, safe error text, firmware/payload revision, mount outcomes and whether both UDP streams decoded. External brokers, if used, remain user-managed and need their own validation.

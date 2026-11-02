# How local RTSP starts

The documented scratch path uses stock `anyka_ipc`, not factory-test mode. It needs station connectivity, an initial MQTT connection, returning media initialization and the firmware ONVIF/RTSP switch. MQTT online alone is insufficient.

This explanation combines [tracked payload behavior](SD_CARD.md), [firmware analysis](research/index.md) and a reported single-LSC result. It is not a universal camera specification. See [firmware diagrams](research/diagrams/boot-media.md) for the checked branches.

## Boot gates

| Gate | How the current path addresses it |
|---|---|
| Configuration selected | Stage 2 attempts DB, identity and settings mounts. Active mounts must be checked. |
| Identity accepted | The INI and DB carry matching generated identity. Length checks alone are not full SDK acceptance. |
| Wi-Fi station join | Scratch `gw_wsm` uses `nc_tp=9`, `stat=2`, base64 credentials and no AP cache. The helper stays at `MODE=none`. |
| MQTT online | The wrapper starts the TLS latch and preloads `libnobind.so`. The SDK connects to loopback, and the service polls its public MQTT status. |
| Media initialization returns | Seeded P2P configuration avoids an examined service-fetch retry. Other initialization failures remain possible. |
| Normal RTSP service starts | Stage 2 sets `bool_onvif_switch=1`; the examined service reaches the ONVIF setter after media initialization. |

`libnobind.so` suppresses socket binding to `wlan0`; it does not falsify MQTT status. The latch handles a narrow connection, not application commands or a full broker. It listens on all interfaces without client authentication. Its exit or an open port is not proof of video.

## Why seed P2P records?

The examined `tuya_ipc_check_p2p_auth_update()` checks nonempty auth data and a canonical decimal type. ASCII `4` skips its configuration fetch; the named string `mqtt_p2p` does not pass the later decimal comparison. Scratch creation writes:

- `p2p_type`: ASCII `4` plus NUL.
- `p2p_auth_info`: `{"p2pId":"","type":4}` plus NUL.
- `p2p_pwd`: eight-character placeholder plus NUL, used by a separate password getter.

These values avoid specific fetch branches; they do not enable real P2P. The password getter's position in a particular boot/callback path is not fully established. See [media research](research/media-rtsp.md).

## Other build-specific choices

| Choice | Evidence or interpretation |
|---|---|
| No `ap_info_v3` in scratch | The examined fast-connect adapter returns success without joining; its caller can suppress the normal station worker. |
| Schema ID record `[]` | Current generation includes it to avoid the examined activated-state reset path. |
| NUL-terminated `tls_ca0` | Historical certificate-manager code reads string data; current generation matches its terminator convention. |
| Certificates start in 1999 | Accommodates the reported early boot clock. |
| IP broker also gets DNS SAN | Accommodates the examined mbedTLS name check. |

See [Wi-Fi](research/boot-wifi.md), [DB](research/database.md) and [TLS research](research/mqtt-tls-rcs.md). Revalidate each choice on another firmware.

## Streams and settings

```text
rtsp://CAMERA_IP:88/videoMain
rtsp://CAMERA_IP:89/videoSub
```

The camera's `_ht_hw_settings.ini` supplies encoder settings. Stage 2 rewrites ONVIF profile dimensions and codec from `main_*` and `sub_*` values; it must not reuse another camera's hardware INI. The optional SD helper on `:8080` is separate from the firmware switch. Factory RTSP on `:554/main_ch` is a different path.

## Playback

```bash
mpv --rtsp-transport=udp --no-cache rtsp://CAMERA_IP:88/videoMain
mpv --rtsp-transport=udp --no-cache rtsp://CAMERA_IP:89/videoSub
```

The reported firmware stalls on interleaved RTP-over-TCP. UDP clients can join mid-GOP and initially report undecodable NALU/POC errors. In the reported setup a keyframe arrives about every two seconds. Continued errors are not a success condition.

Decode both streams for several seconds, then repeat after latch exit. Use the [hardware runbook](hardware-validation.md) to distinguish playback proof from logs or liveness. There is no supported local HTTP/app-control service in this path.

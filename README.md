# TuyHA

Use a supported Anyka-based Tuya camera on your local network, without the Tuya cloud. TuyHA creates the configuration files; the SD card payload starts the camera's existing firmware with them. No external MQTT broker is needed for the default setup.

The project reports this working on one LSC camera. Other models and firmware versions need separate validation. This is local RTSP video, not Tuya app control or real P2P support.

## Before you start

- Python 3.10 or newer on your computer.
- A FAT32 microSD card and a way to copy files onto it.
- The Wi-Fi name and password the camera will use.
- A player that supports RTSP over UDP, such as `mpv`.

> Keep the camera on a trusted, isolated network. The SD payload enables an unauthenticated shell on port 24 by default. Its temporary MQTT listener also accepts unauthenticated clients on all interfaces. Do not expose these ports to the internet.

## 1. Install

Run these commands from the repository folder:

```bash
python -m venv .venv
source .venv/bin/activate
pip install .
tuyha --help
```

## 2. Create camera files

Run from the repository folder. Replace the Wi-Fi placeholders:

> The command-line password can appear in shell history and process listings. Generated files contain recoverable credentials and private keys. Keep the whole output folder private. Do not commit or share it.

```bash
tuyha create --wifi-ssid "<WIFI_SSID>" \
  --wifi-password "<WIFI_PASSWORD>"
tuyha verify --file sd_card/custom/state/tuya_user.hacked.db --scratch
```

`create` puts everything under `sd_card/custom/state/`, with certificates in `mqtt/`. It replaces its generated files but keeps unrelated camera state. `verify` checks files offline; it does not prove the camera will boot or play video.

## 3. Prepare the SD card

> If the generated user database is missing, the SD payload attempts to use the factory database. The camera may reconnect to the Tuya cloud. Failed mounts can also leave factory state active. Check the copied set before booting. If startup fails, use the [deployment and mount checks](docs/hardware-validation.md), not file presence alone.

1. Copy the contents of `sd_card/` to the card's root, including `custom/state/`. No separate artifact-copy step is needed.
2. On the card, set `TELNET=0` in `custom/configs/hack.conf` unless you need shell access for diagnosis. Leave the Wi-Fi helper at its default `MODE=none`; the generated database supplies Wi-Fi settings.
3. Confirm `custom/state/` contains both generated DBs and `_ht_uuid.ini`, and `custom/state/mqtt/` contains `server.crt` and `server.key` from that run.
4. Eject the card, insert it into the camera, and power on.

Use a fresh card state for each camera. A used card carries that camera's hardware settings and private factory backups. See [moving a card](docs/SD_CARD.md#what-not-to-ship-between-cameras).

## 4. Play video

Find the camera's IP address in your router or access point. Replace `CAMERA_IP`:

```bash
mpv --rtsp-transport=udp --no-cache rtsp://CAMERA_IP:88/videoMain
mpv --rtsp-transport=udp --no-cache rtsp://CAMERA_IP:89/videoSub
```

Use UDP: RTP-over-TCP stalls on the examined firmware. The first picture may take about two seconds while the player waits for a keyframe. If errors continue, use the [troubleshooting guide](docs/troubleshooting.md).

## Change Wi-Fi or renew certificates

For a fresh setup, repeat `create` and copy the updated `sd_card/` contents again. This replaces generated files and creates a new identity. Certificates expire 365 days after creation by default.

To keep an existing identity, use [dump and recreate](docs/cli.md#edit-and-recreate-an-existing-database). JSON dumps contain full, unredacted credentials. Recreating refreshes certificates and the database encryption key; deploy the databases, identity INI and server certificate/key together.

## More information

- [CLI reference and editing existing databases](docs/cli.md)
- [SD card behavior](docs/SD_CARD.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Developer documentation](docs/index.md)
- [Firmware research](docs/research/index.md)

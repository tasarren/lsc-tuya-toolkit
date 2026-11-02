# TuyHA Agent Guidance

## Role & Context
TuyHA is currently a **CLI-only artifact materializer** for offline Tuya camera management.
Humans start at `README.md`. Agents use this file for implementation constraints.

## Core Rules
- **Structure:** Keep files small and focused; justify any source file that grows beyond the plan line-count budget.
- **Secrets:** Never log, commit, or share Wi-Fi/MQTT passwords, camera IDs, secrets, private keys, or unredacted dumps. User-requested artifact generation and JSON dumps may persist these values in private, user-selected files. Keep sensitive development outputs in private, Git-ignored locations, verify ignore rules before writing, and never add them to Git.
- **Creation sources:** `create` builds the primary scratch path. `create --from DUMP.json` rebuilds a tagged full dump, preserving imported records/nonempty identity except explicit overrides and fresh trust material. Do not reintroduce compatibility/profile aliases.
- **Refactoring:** Do not overengineer. Prefer small, reusable, typed files. Keep nesting low.
- **Boundaries:** `kvtool/` and checked-in SD scripts/configs remain read-only evidence/reference surfaces. User-requested creation may replace only generated artifacts in `sd_card/custom/state/`; requested latch builds may write `mqtt_latch` and `libnobind.so` in `sd_card/custom/bin/`. Preserve unrelated runtime state and factory backups.

## Architecture
- `src/tuyha/`: Main package root.
- `src/tuyha/cli/`: `create`, `dump`, `verify` argument parsing, request assembly and file inspection.
- `src/tuyha/materializer/`: Staged artifact publication, scratch/import transformations, identity and manifest.
- `src/tuyha/anyka/`: DB, crypto, RCS and tagged JSON codecs; general and scratch verification.
- `src/tuyha/tls/`: TLS material generation (server keys/certs).
- `src/tuyha/contracts/`: Shared input/output data structures.

## Development & Validation
- **Testing:** Use `pytest` from the repository root.
- **Documentation:** Product docs live in `docs/`.
- **Audience:** `README.md` serves camera owners; `docs/` serves developers/operators; `docs/research/` preserves source-backed firmware findings. Product diagrams belong in `docs/diagrams/`, firmware diagrams in `docs/research/diagrams/`.
- **Evidence:** Preserve original research evidence. Published documentation must contain the findings, not depend on local-only files. Remove superseded claims from active guidance. Keep temporary development outputs private and Git-ignored.
- **Verification:** General DB checks accept inactive state; `verify --scratch` adds generator invariants. Neither proves active mounts, camera boot, TLS or decoded video. Dump JSON is full and unredacted, not a support report.
- **Output Targets:** Generated artifacts are intended for `sd_card/custom/state/` on the target camera.
- **SD-ready layout:** `create` defaults to cwd-relative `sd_card/custom/state`, with TLS files under `mqtt/`. An explicit output root uses the same layout. Stage/check the complete set, then publish owned files with ordinary-error rollback; do not claim whole-set atomicity or interruption safety. `./latch/build.sh` defaults to the repository's `sd_card/custom/bin/`.

## Prohibited Scope
- Do NOT implement FastAPI or broad runtime services.
- Do NOT add BLE, P2P/PTZ, or sidecar bridge code without new evidence-backed tasks.
- Do NOT claim production broker ownership; the user owns any external broker.

## Project Status
Validated on an LSC camera: scratch identity, MQTTS to `127.0.0.1:8883` answered by `sd_card/custom/bin/mqtt_latch`,
then `rtsp://CAMERA:88/videoMain` and `:89/videoSub`.


On the LSC / Anyka path we validated (`tuya mqtt online.`, `media init complete.`, `rtsp start.`):

- Scratch generation of `tuya_user.hacked.db`, `tuya_enckey.hacked.db`, `_ht_uuid.ini`, and a local CA/server certificate.
- Camera STA join to a host hotspot from `gw_wsm` (`nc_tp=9`, `stat=2`). The Wi-Fi helper defaults to `MODE=none` and reads `hack.conf`, not `wifi.conf`; the checked-in `hack.conf` does not override it. `wifi.conf` also says `MODE=none`.
- MQTTS to `127.0.0.1:8883` on the camera itself. `mqtt_latch` answers that session; `libnobind.so` suppresses `SO_BINDTODEVICE` so firmware can reach loopback. The latch listens on all interfaces, accepts one unauthenticated client, and can exit on failure/disconnect or its `:88` probe. Exit is not playback proof. No external broker is required.
- Non-factory RTSP after the seeded P2P KV lets `TUYA_APP_Media_Init()` return:
  - `rtsp://CAMERA:88/videoMain`
  - `rtsp://CAMERA:89/videoSub`
- ONVIF profile size and codec rewritten each boot from that camera's `_ht_hw_settings.ini`.

App control and real P2P are not in this stage.

This is a reported single-camera result, not validation of every firmware or the current CLI revision. The published result does not include a raw successful-run capture. Research must distinguish tracked implementation, firmware analysis and reported hardware.

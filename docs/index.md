# Developer documentation

Camera setup starts in the [README](../README.md). These pages describe the current CLI and SD payload; firmware interpretations live separately under [research](research/index.md).

## Workflows and contracts

| Page | Use |
|---|---|
| [CLI reference](cli.md) | Create, inspect, edit and verify DBs; JSON and permissions contract. |
| [Artifact creation](artifact-flow.md) | Scratch versus JSON input, trust refresh, staged publication and output consumers. |
| [SD payload](SD_CARD.md) | Mount selection, first-boot state, latch, helper settings and logs. |
| [Boot to RTSP](LOCAL_RTSP.md) | Firmware gates and playback limits for the examined path. |
| [Hardware validation](hardware-validation.md) | Prove selected artifacts and decoded streams, not merely liveness. |
| [Troubleshooting](troubleshooting.md) | Offline errors, deployment failures and safe support evidence. |

## Workflow diagrams

| Diagram | Coverage |
|---|---|
| [Creation](diagrams/generation.md) | CLI dispatch, scratch/JSON creation, private publication and TLS. |
| [Inspection](diagrams/inspection.md) | DB/key selection, lossless dump envelopes and verification modes. |
| [SD boot](diagrams/sd-boot.md) | Stage 1/2, fallback, wrapper and latch lifecycle. |
| [SD helpers](diagrams/sd-helpers.md) | Entrypoint timing, Wi-Fi, remote shell, FTP, hosts and ONVIF helper. |
| [Validation](diagrams/validation.md) | Hardware checkpoints and failure investigation. |

[Firmware diagrams](research/index.md#workflow-diagrams) cover the examined boot, Wi-Fi, media, DB, MQTT/RCS and HTTP branches. They are not additional supported product workflows.

## Source map

| Owner | Responsibility |
|---|---|
| `src/tuyha/cli/` | Parse `create`, `dump`, `verify`; assemble requests and map errors to safe output. |
| `src/tuyha/materializer/` | Scratch/import records, identity resolution, private staged artifact publication and manifest. |
| `src/tuyha/anyka/` | DB/crypto/RCS/tagged JSON codecs; general and scratch checks. |
| `src/tuyha/tls/` | CA and server certificates. |
| `src/tuyha/contracts/` | Shared request and artifact shapes. |
| `latch/` | On-camera MQTT latch and socket-binding preload source. |
| `sd_card/` | Scripts/configs are reference-only. Requested creation/builds write generated state and binaries at the documented targets. |

## Development checks

Install test dependencies and run from the repository root:

```bash
pip install '.[test]'
pytest
PYTHONPATH=src python -m tuyha.cli --help
```

Tests can create private artifacts and dumps. Use a unique, previously nonexistent `--basetemp` in a private, Git-ignored location, with cache/output paths there too. The `private_root` fixture unconditionally skips private-evidence tests to prevent secret disclosure. Synthetic tests cover supported code paths, not hardware acceptance. Do not copy real fixtures into tracked tests or treat the safety skip as a pass.

Keep changes scoped. SD scripts/configs, `kvtool/` and original research evidence are not cleanup targets. User-requested artifact creation and latch builds may update their specific SD targets; preserve all other state. See [agent guidance](../AGENTS.md) for boundaries and secret-handling rules.

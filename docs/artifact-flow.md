# Artifact creation

TuyHA runs on the computer, not the camera. It writes a DB pair, identity INI and TLS files. The SD payload mounts the configuration before stock `anyka_ipc` starts. The on-camera latch answers the initial MQTT session.

See [creation diagrams](diagrams/generation.md), [dump and verification diagrams](diagrams/inspection.md), and the [CLI reference](cli.md).

## Two creation sources

| Source | Records and identity | Encryption and trust |
|---|---|---|
| `create` | Builds the scratch set. Generates identity unless overridden. Wi-Fi name and password are required. | Fresh 16-byte enckey and CA/server certificate. |
| `create --from DUMP.json` | Reads a full `tuyha-db-v1` dump. Keeps imported records and nonempty identity fields, applies explicit overrides, and fills missing/empty identity fields. | Fresh enckey unless overridden. Replaces trust records with the new certificates. |

JSON creation does not reopen the original DB or require its old enckey. It is not a byte-for-byte clone: the DB is rebuilt with sorted records and write count `1`. Unknown record values remain intact unless a named transformation applies. See [import changes](cli.md#what-json-creation-changes).

## Publication and failure handling

[workflow.py](../src/tuyha/materializer/workflow.py) defaults to the cwd-relative `sd_card/custom/state` directory. It validates input, generates in a private sibling staging directory, checks the resulting records, then publishes its owned files individually. Existing generated files are backed up for rollback on ordinary publication errors. Other state is untouched. Generated files have mode `0600`; newly created state and `mqtt/` directories use `0700`. Existing directory permissions are not changed.

State, `mqtt/` and generated-file symlink targets are rejected, as are wrong file types. The manifest is published last. Run one creation at a time per state directory. Failed staging is cleaned up. Failed recovery retains private recovery files and reports their location. Publication is not atomic across the set and does not guarantee recovery after interruption or power loss. Copying mismatched generations to the card can still break startup.

## Scratch records

[records.py](../src/tuyha/materializer/records.py) builds the following set. This describes current generation, not a minimum specification for every Tuya firmware.

| Record | Generated value or role |
|---|---|
| `gw_wsm` | Base64 SSID/password, `wfb64=1`, `nc_tp=9`, `stat=2`; no `ap_info_v3`. |
| `gw_ai` | LAN keys, broker/HTTP endpoint fields and optional `caArr`. Default MQTT endpoint: `127.0.0.1:8883`. |
| `gw_bi`, `gw_di` | UUID, authentication, device/product/schema and LAN-related identity. |
| Schema ID as key | JSON bytes `[]`. Supports the examined activated boot path. |
| `rcs.active` | Region and register-center hosts, with optional server certificate. |
| `tuya_seed` | 64 bytes. |
| `tls_ca_cnt`, `tls_ca0` | NUL-terminated count and base64 DER CA certificate. |
| `wf_start_md` | ASCII `2` plus NUL. |
| `p2p_type` | ASCII `4` plus NUL. |
| `p2p_auth_info` | `{"p2pId":"","type":4}` plus NUL. |
| `p2p_pwd` | Eight-character dummy plus NUL. Avoids a separate password fetch on the examined path. |

The [DB codec](../src/tuyha/anyka/db.py) uses CRC32 and AES-128-ECB with a key derived from the enckey. Neither encryption nor CRC32 makes these artifacts safe to share. [_ht_uuid.ini](../src/tuyha/materializer/uuid_ini.py) separately stores recoverable identity bytes using bitwise NOT and Latin-1.

## TLS and output consumers

Both certificates start at 1999-01-01 to accommodate the camera's early boot clock. The CLI default expiry is creation time plus 365 days. An IP broker gets both DNS and IP SAN entries because of the examined mbedTLS name check.

| Output | Destination or use |
|---|---|
| `tuya_user.hacked.db`, `tuya_enckey.hacked.db`, `_ht_uuid.ini` | Card `custom/state/`. |
| `mqtt/server.crt`, `mqtt/server.key` | Already under the state root's `mqtt/`; the latch reads these after SD copy. |
| `mqtt/ca.crt`, `mqtt/ca.der`, `mqtt/tls_ca0.b64` | Public CA in PEM, DER and base64 DER forms. Keep with the private artifact set. |
| `manifest.json` | Source kind (`scratch` or `json`), paths, record names, identity lengths and trust metadata. |

The CA signing key exists only during generation; no `ca.key` is emitted. `server.key` is a TLS private key, not the key needed to decode a DB. Record names in the manifest may reveal a schema ID. Review before sharing.

Default creation prepares the tracked SD tree's runtime state, so users copy the contents of `sd_card/` to the card root without a separate artifact-copy step. An explicit output directory has the same state layout but must be copied to the card's `custom/state/`.

## Evidence limits

Offline verification checks DB structure and known record rules. It does not test certificate-name matching on the camera, active SD mounts, MQTT connection or decoded video. Follow the [hardware runbook](hardware-validation.md) for a new deployment and the [research scope](research/index.md#evidence-and-scope) for the reported single-camera result.

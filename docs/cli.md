# CLI reference

TuyHA has three commands: `create`, `dump` and `verify`. All operate on local files. None contacts or controls a camera.

```bash
tuyha create --help
tuyha dump --help
tuyha verify --help
```

## Create a fresh set

> Passwords and identity overrides passed as arguments can appear in shell history and process listings. Keep output private. Never paste real values into reports or commit generated files.

```bash
tuyha create --wifi-ssid "<WIFI_SSID>" --wifi-password "<WIFI_PASSWORD>"
tuyha verify --file sd_card/custom/state/tuya_user.hacked.db --scratch
```

Without `--from`, creation builds scratch records and a fresh identity. Wi-Fi SSID and password are required. Region defaults to `EU`; MQTT defaults to `127.0.0.1:8883` for the on-camera latch.

The default state directory is `sd_card/custom/state`, relative to the working directory. Run from the repository root for the ready-to-copy SD tree. `--output-dir PATH` selects another state root with the same layout: DB pair, `_ht_uuid.ini` and manifest at its root; all TLS files under `mqtt/`.

Creation replaces only its generated files. Existing hardware INIs, factory backups and unrelated state remain. Selected output directories and generated-file targets cannot be symlinks. Newly created state and `mqtt/` directories use mode `0700`; generated files use `0600`. Existing directory permissions are not hardened. FAT32 cards do not provide the same protection.

The complete set is staged and checked first, then published per file with backups for rollback on ordinary errors; the manifest is published last. Run only one creation at a time per directory. This is not an atomic whole-directory update or a power-loss-safe transaction. If recovery fails, the error identifies a retained private recovery directory. Preserve it until recovery is complete.

## Dump an existing database

> A dump contains full, unredacted credentials and identity data. Write it only to a private location and review ignore rules before using a repository path.

```bash
tuyha dump --file sd_card/custom/state/tuya_user.hacked.db --output ./private-dump.json
```

For filenames starting with `tuya_user.` and ending with `.db`, the CLI replaces that prefix with `tuya_enckey.` in the same folder. Examples: `tuya_user.hacked.db` uses `tuya_enckey.hacked.db`; `tuya_user.db` uses `tuya_enckey.db`. Custom names need an explicit key:

```bash
tuyha dump --file ./private/camera.db --enckey ./private/camera.enckey --output ./private/dump.json
```

The key file must contain the matching 16 raw enckey bytes, not hex text and not `server.key`. Dumping needs neither TLS certificates nor a running broker.

`dump` writes full, unredacted JSON with mode `0600`. It refuses existing output, including symlinks. A newly created immediate parent requests mode `0700`; existing parents and intermediate ancestors are not hardened. Choose a private parent folder.

## Edit and recreate an existing database

1. Dump the DB using its matching enckey.
2. Edit the JSON privately. Preserve the format tag and each record's encoding envelope.
3. Recreate the SD-ready set, then verify:

   ```bash
   tuyha create --from ./private-dump.json
   tuyha verify --file sd_card/custom/state/tuya_user.hacked.db
   ```

4. Copy the updated `sd_card/` contents to the card. Keep the matching DB pair, INI and `mqtt/server.crt` / `mqtt/server.key` together. See [deployment](../README.md#3-prepare-the-sd-card).

To change Wi-Fi without editing its record manually:

```bash
tuyha create --from ./private-dump.json \
  --wifi-ssid "<NEW_WIFI_SSID>" --wifi-password "<NEW_WIFI_PASSWORD>"
```

### What JSON creation changes

| Area | Behavior |
|---|---|
| Imported records | Retained unless an override or transformation below changes them. No original DB path is stored or needed. |
| Identity and seed | Nonempty identity strings remain; missing, null or empty identity fields get generated defaults. An imported seed must be 64 bytes; a missing seed is generated. Explicit overrides win. |
| Enckey and DB header | Fresh enckey unless `--enckey-hex` is supplied. DB rebuilt with write count `1`; old header/layout is not preserved. |
| TLS trust | Always generates a new CA and server key/certificate. Replaces `tls_ca_cnt` and numbered `tls_caN` records. Refreshes `gw_ai.caArr` and certificates in decodable active/manufacturing RCS records, subject to the opt-out flags. |
| Wi-Fi | Preserved unless explicitly overridden. A credential override re-encodes both fields with `wfb64=1`. `--region` changes `gw_wsm.region`. |
| MQTT endpoint | Uses imported `gw_ai.mqs_url` for TLS generation, or loopback when missing, null or empty. Existing null/empty endpoint fields stay unchanged unless overridden. Explicit host/port updates the three MQTT endpoint fields. Explicit host also updates the known HTTP endpoint fields. |
| RCS host | Existing RCS hosts stay unchanged unless `--rcs-host` is supplied. A broker-host override alone does not retarget imported RCS. |
| Schema | Ensures a record exists for the resolved schema ID; does not replace an existing schema value. |

Import does not turn an inactive factory dump into the scratch boot set. Existing activation state, cached AP records and P2P configuration remain unless changed. General verification may pass such a DB while `--scratch` fails. Use fresh creation for the documented scratch path.

A missing, null or empty imported region uses `EU` for creation settings. The original `gw_wsm.region` remains unchanged unless `--region` is supplied.

The JSON input must not resolve to a generated output file. Creation rejects that collision before reading or replacing the input.

## JSON format

```json
{
  "format": "tuyha-db-v1",
  "records": {
    "example": {"encoding": "text", "value": "example only"}
  }
}
```

This illustrates the envelope, not a complete camera configuration. Input must be JSON, not JSONC. Duplicate fields and unsupported envelopes are rejected.

| `encoding` | `value` |
|---|---|
| `json` | JSON value serialized compactly. |
| `wifi` | Gateway Wi-Fi object. When `wfb64=1`, readable SSID/password become base64 in the DB. |
| `rcs` | `code`, `url0`, `url1`, `source`, `pub`, `cert_b64`, or `null` for inactive RCS. |
| `log-level` | Object with integer `level` (`0`–`5`) and unsigned 32-bit `expires_at`. No automatic expiry default. |
| `text` | UTF-8 string; JSON escapes preserve embedded NUL bytes. |
| `base64` | Base64 representation of arbitrary bytes. |

For `json` and `wifi`, optional `nul` appends that many NUL bytes.

Readable encodings are emitted only when re-encoding reproduces the exact decoded record bytes. Otherwise the dumper falls back to text or base64. Consequently, noncanonical JSON may appear as text rather than an object. Preserve that envelope to keep its bytes.

This exactness applies to decoded record values in the dump codec, not the entire DB file or `create --from` output. Creation deliberately refreshes identity gaps, trust and other listed fields.

## Verify an existing database

```bash
tuyha verify --file sd_card/custom/state/tuya_user.hacked.db
tuyha verify --file sd_card/custom/state/tuya_user.hacked.db --scratch
```

`--enckey` follows the same rules as `dump`. Both commands load the DB through structural checks: header and record CRCs, ranges, block lengths, duplicate names, overlap and decryption/padding.

General verification checks known records when present: gateway types and lengths, Wi-Fi base64, identity shape, RCS, certificate records, P2P numeric/JSON fields, log-level layout and stored key checksum. Null gateway endpoints, Wi-Fi credentials and identity fields are accepted as unset factory state. Missing activation records and inactive factory state are not scratch failures unless `--scratch` is selected.

`--scratch` adds the generator's required records, activated Wi-Fi state, identity/schema link, seed size, consistent endpoints, CA consistency/NUL requirements, P2P seeds and absent AP cache. These checks describe current TuyHA generation, not all valid firmware DBs.

Neither mode proves DB authenticity, certificate/key pairing with files outside the DB, live TLS, mounted artifact selection or RTSP. See [hardware validation](hardware-validation.md).

## Creation options

| Options | Purpose |
|---|---|
| `--from`, `--output-dir` | Full dump input and state root. Default output: `sd_card/custom/state` relative to the working directory. Existing generated files are replaced. |
| `--wifi-ssid`, `--wifi-password`, `--region` | Scratch network inputs or explicit imported Wi-Fi overrides. |
| `--broker-host`, `--broker-port`, `--rcs-host` | MQTT target and separate register-center override. External broker setup remains user-owned. |
| `--tls-common-name`, `--tls-dns-name`, `--tls-ip-address` | Certificate names; DNS/IP options can be repeated. Loopback is an initial IP SAN. |
| `--tls-validity-days` | Positive lifetime from creation time; CLI default `365`. Both certificates start in 1999. |
| `--no-rcs-cert-b64`, `--no-gw-ai-ca-arr` | Omit the generated certificate from RCS, or CA array from `gw_ai`. Does not disable TLS or remove `tls_ca0`. |
| `--uuid`, `--auth-key`, `--device-id`, `--psk-key`, `--product-key`, `--schema-id`, `--lan-key`, `--lan-local-key` | Explicit identity overrides. Leave unset for normal scratch creation. |
| `--tuya-seed-b64`, `--enckey-hex` | Overrides decoding to 64-byte seed and 16-byte enckey. Not file paths. |

Exit codes: `0` success, `1` failed record checks, `2` argument/input/I/O error. Error text omits secret values. See [inspection diagrams](diagrams/inspection.md) for command flow.

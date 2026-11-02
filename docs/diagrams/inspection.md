# Dump and verification workflows

These are offline file operations. A successful dump or verification does not prove camera acceptance. See [CLI reference](../cli.md) and [hardware validation](../hardware-validation.md).

## Resolve and load a DB pair

```mermaid
flowchart TD
  A["dump or verify: --file DB"] --> B{"Explicit --enckey?"}
  B -- "yes" --> C["Use selected raw key file"]
  B -- "no" --> D{"Name starts tuya_user. and ends .db?"}
  D -- "no" --> X["Require explicit key; exit 2"]
  D -- "yes, including bare tuya_user.db" --> E["Replace tuya_user. prefix with tuya_enckey."]
  C --> F["Read DB and 16-byte enckey"]
  E --> F
  F --> G["Validate header, ranges, CRCs, record names and overlap"]
  G --> H["Decrypt values; check firmware-style padding"]
  H --> I["Decoded records"]
  F -. "input failure" .-> Y["Safe error; exit 2"]
  G -. "structural failure" .-> Y
  H -. "decode failure" .-> Y
```

*DB inspection needs the matching raw enckey, never a TLS private key or broker.*

Sources: [inspection adapter](../../src/tuyha/cli/inspect.py), [DB codec](../../src/tuyha/anyka/db.py). CRC32 and weak padding are not authentication.

## Exact dump envelopes

```mermaid
flowchart TD
  A["Decoded record bytes"] --> B["Try readable JSON, Wi-Fi, RCS or log-level envelope"]
  B --> C{"Re-encoding equals original bytes?"}
  C -- "yes" --> D["Keep readable envelope"]
  C -- "no or unsupported" --> E{"Valid UTF-8?"}
  E -- "yes" --> F["Use text envelope, including escaped NULs"]
  E -- "no" --> G["Use base64 envelope"]
  D --> H["Write full tuyha-db-v1 JSON to new 0600 file"]
  F --> H
  G --> H
  H -. "existing output or write error" .-> X["Reject; no overwrite"]
```

*Readable records never replace byte preservation; the fallback retains arbitrary decoded values.*

Sources: [json_dump.py](../../src/tuyha/anyka/json_dump.py), [exclusive output creation](../../src/tuyha/cli/inspect.py). Dump contents are unredacted. Recreating from this JSON intentionally transforms trust and other listed fields, so it is not a whole-DB clone.

## General versus scratch checks

```mermaid
flowchart TD
  A["Loaded records"] --> B["Check known records when present"]
  B --> C{"--scratch?"}
  C -- "no" --> D["Allow absent activation records and inactive state"]
  C -- "yes" --> E["Check required scratch set, activation, identity/schema, trust and P2P"]
  E --> F["Reject AP cache and inconsistent scratch fields"]
  D --> G{"Findings?"}
  F --> G
  G -- "yes" --> H["Print safe FAIL descriptions; exit 1"]
  G -- "no" --> I["Offline PASS; exit 0"]
  I --> J["Live boot, TLS and video remain untested"]
```

*General checks inspect known data; scratch checks enforce the generator's additional contract.*

Sources: [general verifier](../../src/tuyha/anyka/verify.py), [scratch verifier](../../src/tuyha/anyka/scratch_verify.py), [CLI result handling](../../src/tuyha/cli/main.py). Unknown record semantics are not validated. Reports contain field names, not values.

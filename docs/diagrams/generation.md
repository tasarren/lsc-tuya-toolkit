# Creation workflows

These diagrams describe tracked host-side code. For record contents, see [artifact creation](../artifact-flow.md); for commands, see [CLI reference](../cli.md).

## Command dispatch

```mermaid
flowchart TD
  A["Parse command and arguments"] --> B{"Command"}
  B -- "create" --> C["Assemble request; stage and publish artifact set"]
  B -- "dump" --> D["Load DB pair; write new private JSON"]
  B -- "verify" --> E["Load DB pair; check known records and optional scratch rules"]
  C --> F["Print manifest path; exit 0"]
  D --> G["Print dump path; exit 0"]
  E --> H{"Record findings?"}
  H -- "yes" --> I["Print safe FAIL descriptions; exit 1"]
  H -- "no" --> J["Print offline PASS and limits; exit 0"]
  A -. "invalid arguments" .-> K["Safe argument error; exit 2"]
  C -. "handled input or I/O error" .-> L["Safe error message; exit 2"]
  D -. "handled input or I/O error" .-> L
  E -. "handled input or I/O error" .-> L
```

*Three subcommands share safe error handling; verification findings are distinct from input failures.*

Sources: [main.py](../../src/tuyha/cli/main.py), [args.py](../../src/tuyha/cli/args.py), and [inspection workflows](inspection.md). Help exits through the argument parser. None of these paths contacts a camera.

## Scratch or JSON creation

```mermaid
flowchart TD
  A{"--from supplied?"} -- "no" --> B["Require Wi-Fi; use loopback MQTT defaults"]
  A -- "yes" --> C["Read tagged full dump; decode record envelopes"]
  C --> D["Keep imported records; apply explicit network overrides"]
  D --> E["Import nonempty identity; fill gaps; explicit overrides win"]
  B --> F["Resolve identity; fresh enckey unless overridden"]
  E --> F
  F --> G{"Selected directories and generated-file targets valid, not symlinks?"}
  G -- "no" --> X["Reject without publishing"]
  G -- "yes" --> H["Create private sibling staging directory; generate fresh TLS"]
  H --> I{"Source"}
  I -- "scratch" --> J["Build scratch records"]
  I -- "JSON" --> K["Fill identity/schema; replace trust; retain other records"]
  J --> L["General and scratch record checks"]
  K --> M["General record checks"]
  L --> N["Build DB with write count 1; write enckey, INI, manifest"]
  M --> N
  N --> O["Set files 0600; back up prior owned files"]
  O -. "backup failure" .-> P
  O --> Q["Publish owned files individually; manifest last; keep unrelated state"]
  Q -. "ordinary failure" .-> R["Restore replaced files from backups"]
  R -. "recovery fails" .-> S["Retain private recovery directory; report path"]
  H -. "failure" .-> P["Clean staging; no partial set published"]
  J -. "failure" .-> P
  K -. "failure" .-> P
  L -. "failure" .-> P
  M -. "failure" .-> P
  N -. "failure" .-> P
```

*JSON input retains deployment state; scratch input builds the documented local-boot record set.*

Sources: [request assembly](../../src/tuyha/cli/create.py), [publication](../../src/tuyha/materializer/workflow.py), [import transformation](../../src/tuyha/materializer/imported.py), and [identity defaults](../../src/tuyha/materializer/identity.py). Default state root is cwd-relative `sd_card/custom/state`; TLS files go in `mqtt/`. Newly created directories use `0700`, existing permissions remain. One writer at a time; publication is not atomic across files or safe against power loss. Parsing and validation can reject input before staging.

## Matched TLS material

```mermaid
flowchart LR
  A["Broker target and certificate options"] --> B["Generate CA and server keys; sign certificates"]
  B --> C["CA PEM, DER and base64 DER files"]
  B --> D["Server certificate and private key"]
  C --> E["Replace DB tls_ca_cnt and numbered CA records"]
  C -. "unless omitted" .-> F["Refresh gw_ai.caArr"]
  B -. "unless omitted" .-> G["Refresh certificate in generated or decodable imported RCS"]
  D --> H["Write mqtt/server.crt and mqtt/server.key beside DB root; copy SD tree"]
```

*Fresh trust is deliberate creation behavior, not a dependency of database dumping.*

Sources: [TLS generator](../../src/tuyha/tls/generator.py), [scratch records](../../src/tuyha/materializer/records.py), [JSON import](../../src/tuyha/materializer/imported.py), and [deployment](../../README.md#3-prepare-the-sd-card). Both certificates start in 1999 and expire 365 days after creation by CLI default. The CA private key is not emitted. Keep the entire artifact set private.

## Optional latch rebuild

```mermaid
flowchart TD
  A["Run latch/build.sh"] --> B{"Configured or detected ARM compiler?"}
  B -- "yes" --> C["Use local cross-compiler"]
  B -- "no" --> D["Build Docker toolchain image; run isolated build container"]
  D --> C
  C --> E["Download/cache mbedTLS; build static libraries when missing"]
  E --> F["Compile static mqtt_latch and shared libnobind.so"]
  F --> G["Check latch is ARM32 ELF with no interpreter"]
  G --> H["Default outputs: repository sd_card/custom/bin"]
  C -. "compiler, download or build failure" .-> X["Stop with nonzero exit"]
  G -. "invalid ELF" .-> X
```

*The container is a cross-build tool, not a camera runtime service.*

Source: [latch/build.sh](../../latch/build.sh). `LATCH_OUTPUT_DIR` and `LATCH_CACHE_DIR` isolate outputs/cache; `LATCH_CC` selects a compiler. A successful cross-build or ELF check does not prove camera operation. Existing binaries are included, so normal setup does not require a rebuild.

# Database and logging state

The codec diagram describes tracked implementation, not all Tuya formats. The logging diagram describes the [examined firmware](../index.md#examined-firmware).

## DB build and load

```mermaid
flowchart LR
  subgraph build["Build"]
    A["KV records and 16-byte enckey"] --> B["Derive AES key"]
    B --> C["Sort records; pad and AES-ECB encrypt each value"]
    C --> D["Build header and record table; CRC32 header and ciphertext"]
    D --> E["Write user DB"]
  end
  subgraph load["Load"]
    F["User DB and enckey"] --> G["Derive AES key; validate header and CRC32"]
    G --> H["Validate active record ranges, names, overlap and CRC32"]
    H --> J["Decrypt and weakly unpad"]
    J --> I["Decoded KV map"]
    G -. "invalid" .-> X["Error"]
    H -. "invalid record" .-> X
    J -. "decode or unpad failure" .-> X
  end
```

*The tracked builder encrypts record values; the reader checks CRCs before decoding.*

Sources: [db.py](../../../src/tuyha/anyka/db.py), [crypto.py](../../../src/tuyha/anyka/crypto.py), and [database research](../database.md#kv-file-format). CRC32 and the weak padding check do not authenticate the DB. A successful reload is not proof that firmware will accept it.

## Key derivation and value encryption

```mermaid
flowchart TD
  raw["16 raw enckey bytes"] --> words["Read four little-endian u32 words: w0, w1, w2, w3"]
  words --> rotate["Repack words as w2, w3, w0, w1"]
  rotate --> swap["Swap adjacent byte pairs"]
  swap --> key["Derived 16-byte AES key"]
  value["One record's decoded value bytes"] --> pad["Append PKCS#7 padding to a 16-byte boundary"]
  pad --> encrypt["AES-128-ECB encrypt"]
  key --> encrypt
  encrypt --> ciphertext["Ciphertext stored at record offset"]
  ciphertext --> checksum["CRC32 over ciphertext; store in record entry"]
```

*Each record is encrypted separately with the derived key; CRC32 covers its ciphertext, not a cryptographic authentication tag.*

Source: [crypto.py](../../../src/tuyha/anyka/crypto.py). Even a value already aligned to 16 bytes receives a full padding block. The reader uses a weaker length check than strict PKCS#7 validation, so a decoded result is not authenticity evidence.

## Value terminators are part of the record

```mermaid
flowchart LR
  subgraph ca["Generated CA record"]
    der["CA certificate DER"] --> b64["Base64 text"] --> nul["Append NUL byte"] --> ca0["tls_ca0 value bytes"]
  end
  subgraph p2p["Generated P2P configuration"]
    type["ASCII 4"] --> typenul["Append NUL"] --> typerecord["p2p_type"]
    auth["Compact auth JSON"] --> authnul["Append NUL"] --> authrecord["p2p_auth_info"]
  end
  ca0 --> db["DB padding and encryption"]
  typerecord --> db
  authrecord --> db
  db --> decode["Decrypt and remove cipher padding"]
  decode --> retained["Original value terminators remain"]
```

*A record's terminating NUL is payload data; it is separate from AES padding and must survive decoding.*

Source: [records.py](../../../src/tuyha/materializer/records.py). Firmware certificate loading uses string lengths on CA text. The [tagged dump codec](../../../src/tuyha/anyka/json_dump.py) preserves decoded value bytes rather than normalizing terminators away.

## Log-level expiry

```mermaid
flowchart TD
  A["db.init handler"] --> B{"localLogLevel exists and reads successfully?"}
  B -- "yes" --> C["Save prior log level and set stored level"]
  B -- "no" --> D["No stored level applied by this handler"]
  E["time.sync handler"] --> F{"localLogLevel exists?"}
  F -- "no" --> G["No expiry action"]
  F -- "yes" --> H{"Expiry is in the future?"}
  H -- "yes" --> I["Schedule timeout"]
  I --> J["Restore prior level and delete record if present"]
  H -- "no" --> K["Delete record and restore prior level"]
```

*The examined handlers apply a saved log level and use synchronized time to manage its expiry.*

See [logging research](../database.md#logging-state) for the `db.init` and `time.sync` handlers. These handlers do not prove that every logging gate is open. Logs can expose secrets and identifiers.

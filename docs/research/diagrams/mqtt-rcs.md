# MQTT status, payload and register center

These diagrams describe the [examined firmware](../index.md#examined-firmware). The tracked [latch flow](../../diagrams/sd-boot.md#latch-startup-and-exit) is separate from the application-payload parser.

## MQTT event and boot-gate status

```mermaid
flowchart LR
  A["mqtt.con or mqtt.disc event"] --> B["ty_publish_event dispatches subscribed handler"]
  B --> C["Handler sets event-handler status 1 or 0"]
  D["Online or offline status callback"] --> E["Set separate boot-gate status"]
  E --> F["TUYA_IPC_Get_MqttStatus"]
  F --> G["Service gate reads public status"]
```

*Event-handler status and the public boot-gate status are distinct variables.*

Functions: `ty_publish_event()`, `tuya_ipc_set_mqtt_status()` and `TUYA_IPC_Get_MqttStatus()`; see [MQTT status research](../mqtt-tls-rcs.md#mqtt-events-and-status). The two checked paths are shown separately; no call between them is asserted.

## Event dispatch internals

```mermaid
flowchart TD
  publish["ty_publish_event with event name and data"] --> init["Initialize event system if needed"]
  init --> valid{"Event name valid?"}
  valid -- "no" --> bad["Return invalid-event error"]
  valid -- "yes" --> node["Find event node or create it"]
  node --> available{"Node available?"}
  available -- "no" --> alloc["Return allocation error"]
  available -- "yes" --> lock["Lock node mutex"]
  lock --> callback["Dispatch subscribed callbacks with event data"]
  callback --> next["Log nonzero callback result; continue subscriber traversal"]
  next --> unlock["Unlock node mutex"]
  unlock --> result["Return dispatcher result"]
```

*Callbacks execute within the event node's mutex; publishing dispatches handlers directly rather than proving a later network outcome.*

Functions: `ty_publish_event()` and `_event_node_dispatch()`. The dispatcher also removes subscriptions marked for removal by its checked branch. MQTT connected/disconnected handlers affect their own status variable, as shown above.

## MQTT application payload

```mermaid
flowchart LR
  A["MQTT PUBLISH payload"] --> B{"Version 2.3 and reserved byte zero?"}
  B -- "no" --> C["Reject this parser path"]
  B -- "yes" --> D["Read sequence, message code, nonce, ciphertext and tag"]
  D --> E["Authenticate header as additional data and decrypt payload"]
  E --> F["Decoded application payload or authentication error"]
```

*The 2.3 envelope is inside PUBLISH and is separate from the examined MQTT 3.1 CONNECT version.*

See [MQTT payload research](../mqtt-tls-rcs.md#mqtt-23-payload) for byte layout and authenticated header. The latch does not decode this envelope. This is not proof of app control.

## Latch packet dispatch

```mermaid
flowchart TD
  tls["TLS setup complete"] --> probe{"Loopback TCP port 88 accepts?"}
  probe -- "yes" --> close["Close client and exit"]
  probe -- "no" --> first["Read MQTT fixed-header byte"]
  first --> status{"Read result"}
  status -- "want read or write" --> poll["Poll briefly"]
  poll --> probe
  status -- "error or disconnect" --> close
  status -- "one byte" --> body["Read remaining length and body"]
  body --> ok{"Body read succeeds?"}
  ok -- "no" --> close
  ok -- "yes" --> kind{"Packet type"}
  kind -- "CONNECT" --> connack["Attempt CONNACK"]
  kind -- "SUBSCRIBE" --> suback["Parse topics; attempt SUBACK"]
  kind -- "PUBLISH" --> qos{"Nonzero QoS bits?"}
  qos -- "yes" --> puback["Read packet ID; attempt PUBACK"]
  qos -- "no" --> free["Free packet body"]
  kind -- "PINGREQ" --> ping["Attempt PINGRESP"]
  kind -- "DISCONNECT" --> close
  kind -- "other" --> free
  connack --> free
  suback --> free
  puback --> free
  ping --> free
  free --> probe
```

*The tracked latch checks port `88` between reads, responds by packet type and exits on several non-RTSP paths.*

Source: [mqtt_latch.c](../../../latch/mqtt_latch.c), `serve()`, `read_packet()`, `suback()` and `puback()`. Malformed SUBSCRIBE/PUBLISH bodies can receive no acknowledgement. Reply-write results are not used to prove successful delivery. The QoS-bit condition is source behavior, not a claim of full QoS 2 support.

## Latch connection and TLS lifecycle

```mermaid
flowchart TD
  start["Start mqtt_latch with certificate and key paths"] --> bind["Bind INADDR_ANY:8883; listen"]
  bind --> bound{"Listener created?"}
  bound -- "no" --> exit["Exit without serving"]
  bound -- "yes" --> accept["Accept one TCP client; close listening socket"]
  accept --> accepted{"Client accepted?"}
  accepted -- "no" --> exit
  accepted -- "yes" --> setup["Load certificate/key; configure TLS 1.2"]
  setup --> handshake{"TLS handshake completes?"}
  handshake -- "fatal error" --> cleanup["Release TLS state; close client; exit"]
  handshake -- "want read or write" --> wait["Poll and retry handshake"]
  wait --> handshake
  handshake -- "yes" --> packets["Enter packet loop and port-88 probes"]
  packets --> cleanup
```

*The only accept happens before TLS setup; the latch has no second-client recovery path.*

Source: [mqtt_latch.c](../../../latch/mqtt_latch.c), `main()` and `tls_setup()`. TLS uses the configured server certificate and disables client-certificate verification. A TLS setup error also exits. Isolate the camera network; the all-interface listener must not be treated as authenticated loopback-only access.

## RCS fallback and trust

```mermaid
flowchart TD
  A{"RCS endpoint already in memory?"} -- "yes" --> B["Keep in-memory state"]
  A -- "no" --> C["Read rcs.active"]
  C --> D{"Read succeeded?"}
  D -- "yes" --> E["Parse selected record"]
  D -- "no" --> F["Read rcs.mf"]
  F --> G{"Read succeeded?"}
  G -- "yes" --> E
  G -- "no" --> H["Use default RCS state"]
  E --> I{"Parse succeeds?"}
  I -- "yes" --> J["Use parsed RCS state"]
  I -- "no" --> H
```

*The fallback tries `rcs.mf` after a read failure, not after a parse failure.*

Functions: `tuya_register_center_init()` and `tuya_register_center_reset()`; see [RCS research](../mqtt-tls-rcs.md#register-center-fallback). Reset deletes `rcs.active`, not `rcs.mf`; regional default endpoints may be generated. Certificate-manager paths store and load `tls_caN` and `tls_ca_cnt`; RCS tag 6 is another trust surface. Do not assume all surfaces are interchangeable.

## Certificate-manager trust records

```mermaid
flowchart LR
  A["URL-config caArr elements"] --> B["Certificate manager saves tls_caN and tls_ca_cnt"]
  B --> C["NUL-terminated base64 CA records in KV"]
  C --> D["Certificate manager loads count and CA records"]
  D --> E["Base64-decode CA certificates into DER bytes"]
  F["RCS certificate tag 6"] --> G["Separate RCS certificate bytes"]
```

*Certificate-manager CA records and the RCS certificate field are distinct trust surfaces.*

See [trust research](../mqtt-tls-rcs.md#trust-records) for the certificate-manager load/save behavior. The [tracked generator](../../../src/tuyha/materializer/records.py) writes its own CA and optional certificate fields; hardware requirements vary by path and firmware.

## RCS TLV representation

```mermaid
flowchart LR
  subgraph entry["One TLV entry"]
    tag["Type: 1 byte"] --> length["Length: 2 bytes, little-endian"] --> value["Value: declared number of bytes"]
  end
  subgraph fields["Tracked field encoding"]
    source["1: source, one byte"]
    pub["2: pub, one byte"]
    code["3: code, UTF-8 plus NUL"]
    url0["4: URL 0, UTF-8 plus NUL"]
    url1["5: URL 1, UTF-8 plus NUL"]
    certificate["6: optional certificate DER bytes"]
  end
  value -. "field selected by type" .-> fields
```

*Lengths describe the encoded field bytes, including text terminators; the certificate field contains DER bytes, not base64 text.*

Source: [rcs.py](../../../src/tuyha/anyka/rcs.py). Its fixed eight-byte prefix, `01 01 00 00 02 01 00 01`, contains two TLVs: tag 1, length 1, value 0; tag 2, length 1, value 1. The tracked encoder then emits tags 1 and 2 again with the supplied `source` and `pub`, followed by the remaining fields. Its decoder checks and skips the first eight bytes before parsing those fields.

The firmware parser reads from byte 0; later tags 1 and 2 replace the earlier values. The firmware writer emits `source` and `pub` once, as the first two TLVs. The tracked decoder requires its fixed prefix and repeated fields, so it does not accept every firmware-written representation. Host/port validation and field names do not establish all firmware semantics.

## RCS save and reset

```mermaid
flowchart TD
  save["tuya_register_center_save"] --> parse["Parse supplied state; convert certificate PEM to DER"]
  parse --> encode["Encode RCS TLV"]
  encode --> target{"Save selector is 1?"}
  target -- "yes" --> mf["Write rcs.mf"]
  target -- "no" --> active["Write rcs.active"]
  mf --> written{"Write succeeds?"}
  active --> written
  written -- "yes" --> memory["Update in-memory RCS state"]
  written -- "no" --> unchanged["Keep previous in-memory RCS state"]
  memory --> publish["Free encoded buffer; publish rsc.update"]
  unchanged --> publish
  publish --> result["Return write result"]
  reset["tuya_register_center_reset"] --> remove["Delete rcs.active"]
  remove --> retained["rcs.mf is not deleted by this function"]
```

*The write result controls in-memory replacement, but either write outcome publishes `rsc.update`; the event is not proof of a successful save.*

Functions: `tuya_register_center_save()` and `tuya_register_center_reset()`. Parsing, conversion or allocation errors can stop the save before writing. Reset deletes only `rcs.active`. See [fallback selection](#rcs-fallback-and-trust) for what the next initialization reads.

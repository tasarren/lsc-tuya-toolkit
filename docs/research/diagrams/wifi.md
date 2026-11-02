# Wi-Fi internals

These diagrams describe the [examined firmware](../index.md#examined-firmware). They separate credential decoding, worker selection, adapter calls and reported connection state. See [boot and Wi-Fi](../boot-wifi.md) for their place in startup.

## Credential loading and worker selection

```mermaid
flowchart TD
  record["Read gw_wsm"] --> encoding{"wfb64=1?"}
  encoding -- "yes" --> decode["Base64-decode SSID and password"]
  encoding -- "no" --> plain["Use stored credential representation"]
  decode --> state["Populate SDK Wi-Fi state"]
  plain --> state
  state --> init["tuya_wifi_connect_init"]
  init --> eligible{"nc_tp selects normal connection worker?"}
  eligible -- "yes, includes 9" --> schedule["Schedule connection work"]
  eligible -- "no" --> other["Normal worker not selected by this branch"]
  schedule --> fast{"Fast-connect flag set?"}
  fast -- "yes" --> skip["Skip station-connect call"]
  fast -- "no" --> connected{"Already-connected helper says connected?"}
  connected -- "yes" --> skip
  connected -- "no" --> ssid{"SSID nonempty?"}
  ssid -- "no" --> skip
  ssid -- "yes" --> join["Call station-connect operation"]
```

*Decoding credentials and scheduling work are separate from actually calling the station adapter.*

Functions: `wd_gw_wsm_read()` and `tuya_wifi_connect_init()`, followed by the connection worker. [Scratch records](../../../src/tuyha/materializer/records.py) use `wfb64=1`, `nc_tp=9` and `stat=2`. This graph does not impose an order on the separate `db.init` handler.

Delayed-work initialization and work-mode setup can fail before the join guards shown here.

## Fast-connect cache can suppress a real join

```mermaid
sequenceDiagram
  participant Event as db.init
  participant Handler as Fast-connect handler
  participant KV as Saved AP record
  participant Adapter as tkl_wifi_station_fast_connect
  participant Worker as Normal connection worker
  Event->>Handler: Run registered handler
  Handler->>KV: Read saved AP information
  alt Record read fails
    KV-->>Handler: Read error
    Note over Handler: Return without setting success flag
  else Record read succeeds and wrapper reaches adapter
    KV-->>Handler: Saved AP information
    Handler->>Adapter: Fast-connect call through wrapper
    Adapter-->>Handler: Return 0 without joining
    Handler->>Handler: Set fast-connect success flag
  end
  Note over Handler,Worker: Separate paths with no relative execution timing shown
  Worker->>Worker: Test fast-connect flag
  alt Flag set
    Note over Worker: Skip normal station-connect call
  else Flag clear and other guards pass
    Worker->>Worker: Call normal station-connect operation
  end
```

*In this executable, a successful return from the fast-connect adapter does not mean an access-point join occurred.*

Functions: `tuya_wifi_fastconnect_init()`, the `db.init` handler, `tal_fast_station_connect()` and `tkl_wifi_station_fast_connect()`. Scratch creation omits `ap_info_v3`; [scratch verification](../../../src/tuyha/anyka/scratch_verify.py) rejects it. A full-dump import can retain it.

## Station-adapter network mode

```mermaid
flowchart TD
  call["tkl_wifi_station_connect"] --> mark["Set adapter-invoked flag; read net_mode"]
  mark --> ssid{"SSID pointer supplied?"}
  ssid -- "no" --> bind["Log bind-information path; no credential join here"]
  ssid -- "yes" --> mode{"net_mode value"}
  mode -- "1" --> cableonly["Skip Wi-Fi connector in this branch"]
  mode -- "2" --> cable{"Cable connected?"}
  cable -- "no" --> mixed["Invoke Anyka Wi-Fi connector"]
  cable -- "yes" --> flag["Set bool_has_config_wifi"]
  mixed --> flag
  mode -- "other" --> wifi["Invoke Anyka Wi-Fi connector"]
  bind --> notify["Update notifications and return 0"]
  cableonly --> notify
  flag --> notify
  wifi --> notify
```

*The adapter can return 0 without calling the Wi-Fi connector, depending on its inputs and network mode.*

Function: `tkl_wifi_station_connect()` at `0x000da914`. Its connector helper reaches `ht_network_connect_wifi()`. The adapter-invoked flag is not a successful-association flag; notifications and a zero return do not establish an IP address.

## Connection-status reporting

```mermaid
flowchart TD
  query["tkl_wifi_station_get_status"] --> invoked{"Station adapter invoked?"}
  invoked -- "no" --> waiting["Report WSS_CONNECTING"]
  invoked -- "yes" --> network{"Anyka network reports connected?"}
  network -- "yes" --> ip["Report WSS_GOT_IP"]
  network -- "no" --> mode{"Mode allows cable path?"}
  mode -- "yes" --> cable{"Cable connected?"}
  cable -- "yes" --> eth{"eth0 address found or previously recorded?"}
  eth -- "yes" --> ip
  eth -- "no" --> waiting
  cable -- "no" --> only{"Cable-only mode?"}
  only -- "yes" --> idle["Report disconnected status"]
  only -- "no" --> retry["Recheck Anyka network state"]
  mode -- "no" --> retry
  retry --> found{"Connected now?"}
  found -- "yes" --> ip
  found -- "no" --> waiting
```

*Status can reflect the cable path or an uninvoked adapter; it is not necessarily a WLAN association result.*

Function: `tkl_wifi_station_get_status()`. A null output pointer returns an argument error before these branches. Check the actual interface, address and route when validating a camera. Logs can contain SSIDs, passwords and addresses; redact before sharing.

# Firmware boot, Wi-Fi and media

These diagrams describe the [examined firmware](../index.md#examined-firmware), not every camera. Static branch analysis is separate from the [reported single-camera result](../index.md#evidence-and-scope).

## Service boot gate

```mermaid
flowchart TD
  A["main: read identity and initialize network"] --> B{"Identity checks pass?"}
  B -- "no" --> C["Service startup path not reached"]
  B -- "yes" --> D["ht_tuya_service_start"]
  D --> E{"SDK initialization succeeds?"}
  E -- "no" --> F["Log SDK init failure; retry while service runs"]
  F --> D
  E -- "yes" --> G{"TUYA_IPC_Get_MqttStatus is 1?"}
  G -- "no" --> H["Log wait mqtt online and retry"]
  H --> G
  G -- "yes" --> I["Log tuya mqtt online; call media init"]
  I --> J["Continue to ONVIF and other services if media init returns"]
```

*The examined service path waits on the public MQTT status before media initialization.*

Functions: `main()`, `ht_device_id_get()`, `ht_tuya_uuid_check()`, `ht_tuya_service_start()` and `TUYA_IPC_Get_MqttStatus()`. See [boot research](../boot-wifi.md#identity-and-service-gate) for identity encoding and length checks. Wi-Fi setup and the SDK may run asynchronously; this graph does not specify their complete timing.

## Normal versus factory branches

```mermaid
flowchart TD
  A["Earlier main initialization"] --> B{"Selected boot branch"}
  B -- "factory test" --> C["Factory-test setup and wait path"]
  B -- "direct RTSP test" --> D["ht_rtsp_start without normal service gate"]
  B -- "normal" --> E["Read INI identity; initialize network; validate identity"]
  E --> F{"Identity accepted?"}
  F -- "no" --> G["Normal service path not entered"]
  F -- "yes" --> H{"Saved Wi-Fi flag and decrypted credentials usable?"}
  H -- "yes" --> I["ht_network_connect_wifi from saved slots"]
  H -- "no" --> J["No saved-slot join here; SDK station path is separate"]
  I --> K{"Old-test marker exists?"}
  J --> K
  K -- "yes" --> L["ht_old_test"]
  K -- "no" --> M["ht_tuya_service_start; later stop on shutdown"]
  L --> M
```

*The current payload uses normal startup, not the separate factory or direct-RTSP test branches.*

Function: `main()`; see [decompilation methods](../decompilation.md). The saved-Wi-Fi path decrypts credential slots 3 and 4 before calling `ht_network_connect_wifi()`. It is separate from the SDK station worker. This diagram does not reproduce every initialization or shutdown action.

## Wi-Fi station and fast-connect paths

```mermaid
flowchart TD
  A["Read gw_wsm"] --> B["Decode SSID and password when wfb64 is 1"]
  B --> C{"Eligible nc_tp, including 9?"}
  C -- "yes" --> D["Schedule normal connection worker"]
  C -- "no" --> E["Other configuration path; not resolved here"]
  F["db.init fast-connect handler"] --> G{"Saved AP info read and fast-connect call succeed?"}
  G -- "yes" --> H["Set fast-connect flag"]
  G -- "no" --> I["No fast-connect flag from this handler"]
  D --> J{"SSID nonempty, not already connected, no fast-connect flag?"}
  H -. "may suppress" .-> J
  I -. "does not itself schedule worker" .-> J
  J -- "yes" --> K["Call station connect, with or without channel"]
  J -- "no" --> L["Skip station connect in this worker"]
```

*The normal worker and fast-connect handler are separate paths; their timing is not established by this diagram.*

Functions: `wd_gw_wsm_read()`, `tuya_wifi_connect_init()` and `tkl_wifi_station_fast_connect()`; see [station-join findings](../boot-wifi.md#station-join). The examined fast-connect adapter returns success without joining, and the normal worker skips its call when the flag is set. Scratch generation omits `ap_info_v3`; see [records.py](../../../src/tuyha/materializer/records.py).

For separate credential, cache, network-mode and status diagrams, see [Wi-Fi internals](wifi.md).

## Service after the initial MQTT gate

```mermaid
flowchart TD
  online["Public MQTT status is 1"] --> time["Synchronize UTC; launch auxiliary thread"]
  time --> media["TUYA_APP_Media_Init"]
  media --> returned{"Media initialization returns?"}
  returned -- "still blocked" --> blocked["Later service calls not reached yet"]
  returned -- "yes" --> config["Stop netcfg AP mode; set bound-service flag"]
  config --> onvif["Read and apply ONVIF switch"]
  onvif --> other["Storage reporting and other device-service initialization"]
  other --> monitor{"Service still running?"}
  monitor -- "yes" --> loop["Retry failed time sync; periodically check network and UTC"]
  loop --> sleep["Sleep 500 ms"]
  sleep --> monitor
  monitor -- "no" --> cleanup["Stop service activity and release resources"]
```

*The post-initialization monitoring loop does not repeat the initial MQTT-status gate while it remains active.*

Function: `ht_tuya_service_start()`. Its online/offline monitoring messages use `ht_network_get_connect_state()`, not a new read of the public MQTT getter. This does not prove sustained video after disconnect; [runtime validation](../../hardware-validation.md) must check that separately.

## P2P configuration and RTSP

```mermaid
flowchart TD
  A["MQTT online; call TUYA_APP_Media_Init"] --> B{"Media streaming enabled?"}
  B -- "no" --> C["Streaming path not entered"]
  B -- "yes" --> D["P2P auth update check"]
  D --> E{"Auth info nonempty and type canonical decimal 4?"}
  E -- "yes" --> F["Skip service configuration fetch"]
  E -- "no" --> G["Fetch P2P configuration"]
  G --> H{"Fetch succeeds?"}
  H -- "no" --> G
  H -- "yes" --> I["Write type and return from check"]
  F --> J["Media initialization may continue"]
  I --> J
  J --> K{"Media returns and ONVIF switch enables service?"}
  K -- "no" --> L["This RTSP start path not reached"]
  K -- "yes" --> M["Queue RTSP start request"]
```

*The checked P2P configuration branch can delay media initialization before the RTSP start path.*

Functions: `TUYA_APP_Media_Init()`, `TUYA_IPC_Media_Stream_Init()`, `tuya_ipc_media_stream_init()`, `tuya_imm_p2p_init()` and `tuya_ipc_check_p2p_auth_update()`; see [media research](../media-rtsp.md). The separate password getter is not placed in this call chain. A listener is not proof of video decode or real P2P.

The RTSP start call queues work; see [RTSP runtime](media-runtime.md) for the worker, listener/session failures and frame delivery.

## Separate P2P password path

```mermaid
flowchart LR
  A["tuya_ipc_p2p_get_pw"] --> B{"Stored p2p_pwd is nonempty?"}
  B -- "yes" --> C["Use stored password"]
  B -- "no" --> D{"Password update already active?"}
  D -- "no" --> E["Attempt password update, up to 20 times"]
  E --> F{"Update succeeds?"}
  F -- "yes" --> G["Write and return generated password"]
  F -- "no" --> H["Reset update flag; return failure"]
  D -- "yes" --> I["Poll stored password up to 20 times"]
  I --> J{"Read succeeds?"}
  J -- "yes" --> C
  J -- "no" --> K["Return 0 after polling timeout"]
```

*The password getter has its own fallback and retry path.*

Function: `tuya_ipc_p2p_get_pw()`; see [media research](../media-rtsp.md#p2p-configuration-gate). A polling timeout returns 0 without establishing that a password was obtained. This getter does not establish real P2P capability.

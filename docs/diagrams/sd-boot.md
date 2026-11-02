# SD deployment and boot

This flow describes the default SD payload and latch source. It does not prove that a particular card booted or that the binaries match the source. See the [SD payload guide](../SD_CARD.md) and [hardware runbook](../hardware-validation.md).

## Payload and database selection

```mermaid
flowchart TD
  A["Create into default state tree; copy sd_card contents to card root"] --> B{"Firmware starts card hostapd marker?"}
  B -- "no" --> C["Payload not invoked by this path"]
  B -- "yes" --> D{"Sandbox mode?"}
  D -- "yes" --> E["Run sandbox entrypoint"]
  D -- "no" --> F{"Stage 1 marker exists?"}
  F -- "no" --> G["Copy camera state and original DBs; create marker"]
  F -- "yes" --> H["Skip stage 1 copies"]
  G --> I["Run stage 2"]
  H --> I
  I --> O["Attempt busybox and wrapper mounts"]
  O --> J{"Hacked user DB exists?"}
  J -- "yes" --> K["Attempt hacked user DB and enckey mounts"]
  J -- "no" --> L["Attempt original DB pair mounts"]
  K --> M["Sync profiles, set flags, and attempt INI mounts"]
  L --> M
  M --> N["Normal firmware start calls mounted wrapper if active"]
```

*Stage 1 captures camera state; stage 2 selects the DB pair by hacked user-DB presence.*

Sources: [hostapd](../../sd_card/hostapd), [stage 1](../../sd_card/custom/scripts/hack_stage_1.sh), [stage 2](../../sd_card/custom/scripts/hack_stage_2.sh), and [mount helper](../../sd_card/custom/env.sh). Copies and mounts can fail without stopping the scripts. The stage 1 marker is not proof that every copy succeeded. Missing hacked DB or a failed mount can leave factory state active and may allow cloud access. Check stage logs and active mounts.

## Latch startup and exit

```mermaid
flowchart TD
  A["Wrapper start"] --> B{"anyka_ipc already running?"}
  B -- "yes" --> C["Exit without starting another process"]
  B -- "no" --> D{"Latch binary, certificate and key present?"}
  D -- "no" --> E["Skip latch startup"]
  D -- "yes" --> F["Start latch and wait up to 15 seconds for port 8883"]
  E --> G["Launch anyka_ipc; preload libnobind.so if present"]
  F --> G
  F -. "listener" .-> H["Accept one TCP connection; stop listening"]
  H --> I{"TLS setup and handshake succeed?"}
  I -- "no" --> X["Close connection and exit"]
  I -- "yes" --> K{"Loopback probe finds port 88?"}
  K -- "yes" --> X
  K -- "no" --> J["Handle supported MQTT packets"]
  J --> K
  J -. "disconnect or read failure" .-> X
```

*The wrapper starts the latch before the camera process; the latch exits after its one connection ends or its port probe succeeds.*

Sources: [startup wrapper](../../sd_card/custom/scripts/anyka_ipc.sh), [latch source](../../latch/mqtt_latch.c), and [preload source](../../latch/nobind.c). The listener binds all interfaces, not only loopback, and does not authenticate clients. An unrelated client can occupy the sole connection. The wrapper's port check alone does not prove that the intended latch owns the port; the port 88 probe alone does not prove decoded video. The source has no RTSP probe while waiting in `accept()` or the TLS handshake.

## Wrapper stop and restart

```mermaid
flowchart LR
  A{"Wrapper operation"} -- "start" --> B["Run startup flow above"]
  A -- "stop" --> C["Terminate anyka_ipc and mqtt_latch; wait; force-stop survivors"]
  A -- "restart" --> C
  C --> D{"Was operation restart?"}
  D -- "yes" --> B
  D -- "no" --> E["Stop complete"]
```

*Restart executes the wrapper's stop sequence before a fresh start.*

Source: [anyka_ipc.sh](../../sd_card/custom/scripts/anyka_ipc.sh). A restart does not rerun stage 2 or prove that bind mounts changed.

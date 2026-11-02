# Hardware validation and troubleshooting

Use this decision path with the [hardware validation runbook](../hardware-validation.md), not as a substitute for its raw evidence. The reported successful scratch result covers one LSC camera; see [evidence scope](../research/index.md#evidence-and-scope).

```mermaid
flowchart TD
  A["Generate and deploy one matching scratch artifact set"] --> B{"Generated DBs and INI actively mounted?"}
  B -- "no or unknown" --> C["Inspect stage 2 errors, card files and active mounts; do not pass"]
  B -- "yes" --> D{"Wi-Fi joined with an IP?"}
  D -- "no" --> E["Inspect gw_wsm, schema and station logs; do not pass"]
  D -- "yes" --> F{"MQTT online?"}
  F -- "no" --> G["Inspect latch listener, preload, certificate and DB trust; do not pass"]
  F -- "yes" --> H{"Media init and RTSP start logged?"}
  H -- "no" --> I["Inspect P2P seed and ONVIF switch; do not pass"]
  H -- "yes" --> J{"Both streams decode over UDP and remain available after latch exits?"}
  J -- "no" --> K["Check transport, stream logs and next keyframe; do not pass"]
  J -- "yes" --> L["Record pass with redacted firmware, payload, mount and log evidence"]
```

*Each checkpoint rules out a false positive before declaring this hardware run successful.*

Sources: [runbook](../hardware-validation.md), [troubleshooting](../troubleshooting.md), and [boot-to-RTSP guide](../LOCAL_RTSP.md). Branches identify checks, not guaranteed diagnoses. A listening port, a `Hack Stage 2 done.` line, `WSS_CONNECTING`, or MQTT online alone is not sufficient. Keep raw logs, artifacts, dumps and manifests private; redact before sharing.

# RTSP runtime

These diagrams describe the [examined firmware](../index.md#examined-firmware). They expand the [media-gate diagrams](boot-media.md#p2p-configuration-and-rtsp), separating start requests from listeners, sessions and video delivery.

## Queued start and stop

```mermaid
sequenceDiagram
  participant Caller as ONVIF/service caller
  participant API as ht_rtsp_start or ht_rtsp_stop
  participant Queue as RTSP message queue
  participant Worker as ht_rtsp_th
  Caller->>API: Request start or stop
  alt RTSP initialized and message allocation succeeds
    API->>Queue: Push command 0 for start or 1 for stop
    API-->>Caller: Return queue-push result
    alt Queue push succeeds
      Worker->>Queue: Pop queued command
      alt Command 0
        Worker->>Worker: Attempt listeners and session creation
      else Command 1
        Worker->>Worker: Delete sessions and listeners
      end
      Worker->>Worker: Free message and continue loop
    else Queue push fails
      Note over API,Queue: This request does not reach the worker
    end
  else Not initialized or message allocation fails
    API-->>Caller: Return failure
  end
```

*The public request returns the queue operation's result, not the later worker's listener-creation result.*

Functions: `ht_rtsp_init()`, `ht_rtsp_start()`, `ht_rtsp_stop()` and the worker logging `enter ht_rtsp_th`. Initialization creates the queue, mutex and thread; thread creation failure cleans up the queue/mutex. No camera run is implied by this static call relationship.

## Listener and session creation

```mermaid
flowchart TD
  start["Worker handles start command"] --> log["Log rtsp start; lock RTSP mutex"]
  log --> exists{"Main listener already present?"}
  exists -- "yes" --> already["Log already started; unlock and return 0"]
  exists -- "no" --> main["create_rtsp_demo on port 88"]
  main --> mainok{"Main listener created?"}
  mainok -- "no" --> failure["Unlock and return failure"]
  mainok -- "yes" --> sub["create_rtsp_demo on port 89"]
  sub --> subok{"Sub listener created?"}
  subok -- "no" --> delmain["Delete main listener"]
  delmain --> failure
  subok -- "yes" --> mainsession["Create /videoMain using main_enc_out_type"]
  mainsession --> sessionok{"Main session created?"}
  sessionok -- "no" --> both["Delete both listeners"]
  both --> failure
  sessionok -- "yes" --> subsession["Create /videoSub using sub_enc_out_type"]
  subsession --> subgood{"Sub session created?"}
  subgood -- "no" --> delsession["Delete main session and both listeners"]
  delsession --> failure
  subgood -- "yes" --> success["Unlock and return 0"]
```

*The `rtsp start.` log precedes allocation and session creation; it is not proof that both streams are ready.*

The worker's start routine calls `create_rtsp_demo()` and `create_rtsp_session()`. Each session uses codec selector 2 when its `*_enc_out_type` is 2, otherwise selector 1. The transmit path handles selectors 1 and 2 as H.264 and H.265 respectively. A port-88-only probe does not test the sub listener or either codec.

## Video-frame delivery

```mermaid
flowchart TD
  frame["ht_rtsp_send_video_frame receives encoded frame and stream index"] --> selected{"Selected listener handle present?"}
  selected -- "no" --> stop["No RTSP transmit call from this wrapper"]
  selected -- "yes" --> tx["rtsp_sever_tx_video with selected session"]
  tx --> valid{"Session, frame and codec available?"}
  valid -- "no" --> error["Return transmit error"]
  valid -- "yes" --> parse["Read codec data as needed; locate frame NAL units"]
  parse --> packetize["H.264 or H.265 RTP packetization"]
  packetize --> queued["Push produced packets into stream queue"]
  queued --> clients["Visit clients in PLAY state"]
  clients --> service["Run client-send work and rtsp_do_event"]
```

*A listener handle is only the first condition; frame parsing, RTP packetization and a playing client are separate parts of delivery.*

Functions: `ht_rtsp_send_video_frame()`, `rtsp_sever_tx_video()`, `rtp_enc_h264()`, `rtp_enc_h265()` and `rtsp_do_event()`. Packetization can return an error. This diagram does not claim a complete sensor/encoder pipeline or successful client decode.

## PLAY and PAUSE state

```mermaid
stateDiagram-v2
  state "Prepared or paused: state 1" as Ready
  state "Playing: state 2" as Playing
  state "Other client state" as Other
  Ready --> Playing: "PLAY: set available stream cursors to streamq_tail"
  Playing --> Playing: "PLAY: keep existing cursors"
  Playing --> Ready: PAUSE
  Ready --> Ready: PAUSE
  Other --> Other: PLAY or PAUSE returns RTSP 455
```

*Entering PLAY selects the current queue tail; repeating PLAY while already playing does not reset those cursors in the checked handler.*

Routines logging `rtsp_handle_PLAY` and `rtsp_handle_PAUSE` accept states 1 and 2; other states receive response `455`. Queue-tail selection does not request a new IDR in this handler. The [reported playback behavior](../media-rtsp.md#playback-observations-and-limits) includes waiting for an IDR and UDP transport; validate decode and duration separately.

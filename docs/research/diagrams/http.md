# Firmware HTTP paths

These diagrams describe the [examined firmware](../index.md#examined-firmware), not a supported HTTP service. See [HTTP research](../http-protocol.md) for the checked request and response behavior.

## URL configuration

```mermaid
flowchart TD
  A["Selected v2 URL-config path"] --> B["Delete stored TLS CA count and matching CA records; reload certificate state"]
  B --> C["Request endpoint variants from register center"]
  C --> D{"Request succeeds and response is present?"}
  D -- "no" --> E["Return request status without saving response CA"]
  D -- "yes" --> F{"Supplied endpoints parse successfully?"}
  F -- "no" --> G["Return parse error"]
  F -- "yes" --> H["Save response certificate material and reload certificates"]
  H --> I["Use parsed endpoint data"]
```

*The examined v2 path clears CA state before its request and reloads certificates after successful parsing.*

See [URL-config research](../http-protocol.md#url-configuration). A missing response can return the request's status even if it is zero. Some missing endpoint pairs are logged without immediate failure. Failed requests can leave trust state changed; this is not deployment guidance.

## Endpoint-object parsing

```mermaid
flowchart TD
  response["URL-config response"] --> pair{"Requested endpoint variant supplied?"}
  pair -- "not supplied" --> missing["Some absent pairs are logged without immediate failure"]
  pair -- "supplied" --> parse["Parse address and first available array entry"]
  parse --> valid{"Supplied object parses?"}
  valid -- "no" --> error["Return endpoint parse error"]
  valid -- "yes" --> store["Store parsed endpoint data"]
  store --> next["Continue response handling"]
  missing --> next
```

*An absent variant and a malformed supplied object do not necessarily take the same branch.*

See [URL-configuration findings](../http-protocol.md#url-configuration). The checked request asks for HTTP, MQTT, standard TLS, PSK and ghost variants. This diagram describes the parser's data dependencies without assigning unverified response-key names.

## Encrypted action exchange

```mermaid
flowchart TD
  subgraph request["One request-builder path"]
    R["Action request data and key"] --> S["Create authenticated blob: nonce, ciphertext and tag"]
    S --> T["Encode blob as hex in data parameter"]
  end
  subgraph response["One response-callback path"]
  A["Receive action response"] --> B{"Explicit e:false or no decode key?"}
  B -- "yes" --> C["Separate unencrypted response branch"]
  B -- "no" --> D{"t, sign and result present?"}
  D -- "no" --> X["Return decode error"]
  D -- "yes" --> E["Compute MD5 over result, timestamp and key; compare middle 16 hex characters"]
  E --> F{"Signature matches?"}
  F -- "no" --> X
  F -- "yes" --> G["Base64-decode result and authenticate/decrypt"]
  G --> H{"Decrypt and JSON parse succeed?"}
  H -- "no" --> X
  H -- "yes" --> I["Continue with decoded response"]
  end
```

*The request builder and response callback are distinct paths; the encrypted response branch verifies its signature before decryption.*

Function: `__httpc_gw_common_cb()` for the response; see [encrypted exchange research](../http-protocol.md#encrypted-action-exchange). The request builder constructs a separate hex-encoded authenticated blob. This records firmware behavior, not a recommended protocol or proof of app control. Do not publish captures, keys or signing inputs.

## Response decoding gates

```mermaid
sequenceDiagram
  participant Callback as __httpc_gw_common_cb
  participant Envelope as Response fields
  participant Decoder as Authenticated decoder
  participant Parser as JSON parser
  Callback->>Envelope: Read response mode and decode-key availability
  alt Explicit e:false or no decode key
    Note over Callback: Follow separate unencrypted branch
  else Encrypted branch
    Callback->>Envelope: Require t, sign and result
    Callback->>Callback: Compute signature and compare middle 16 hex characters
    alt Signature mismatch or required field missing
      Note over Callback: Return decode error
    else Signature accepted
      Callback->>Decoder: Base64-decoded result with authentication inputs
      alt Authentication or decryption fails
        Decoder-->>Callback: Error
      else Plaintext obtained
        Decoder-->>Callback: Plaintext bytes
        Callback->>Parser: Parse JSON
        Parser-->>Callback: Parsed response or parse error
      end
    end
  end
```

*Signature, authenticated decryption and JSON parsing are separate gates; an accepted signature alone does not establish a usable response.*

Function: `__httpc_gw_common_cb()`. No keys, captures or signing-input values are needed to understand these branches.

import base64
import json

import pytest

from tuyha.anyka.json_dump import dump_json, load_json
from tuyha.anyka.rcs import RcsActive, encode_rcs_active


def test_every_decoded_byte_survives_json_roundtrip() -> None:
    records = {
        "empty": b"", "nul": b"\x00", "tail": b"x\x00\x00", "short": b"\xff\xfe",
        "prefix": b"b64:AAAA", "json-space": b'{ "a": 1 }\n', "json": b'{"a":1}\x00',
        "binary": bytes(range(256)), "marker": b'{"encoding":"base64","value":"AAAA"}',
        "rcs.active": encode_rcs_active(RcsActive(code="EU-PROD", url0="rcs.local", url1="rcs.local")),
        "rcs.mf": b"\x00", "localLogLevel": (3).to_bytes(4, "little") + (123).to_bytes(4, "little"),
        "gw_wsm": b'{"ssid":"TGFibmV0","passwd":"TGFicGFzcw==","wfb64":1}',
    }
    text = dump_json(records)
    assert load_json(text) == records
    data = json.loads(text)
    assert data["records"]["gw_wsm"]["value"]["passwd"] == "Labpass"
    assert data["records"]["rcs.active"]["value"]["url0"] == "rcs.local"
    assert data["records"]["localLogLevel"]["value"]["level"] == 3
    # Base64-looking human text stays literal, rather than guessed to be already encoded.
    data["records"]["gw_wsm"]["value"]["ssid"] = "YWJj"
    changed = json.loads(load_json(json.dumps(data))["gw_wsm"])
    assert base64.b64decode(changed["ssid"]) == b"YWJj"


@pytest.mark.parametrize("text", [
    '{"format":"tuyha-db-v1","records":{},"records":{}}',
    '{"format":"wrong","records":{}}',
    '{"format":"tuyha-db-v1","records":{"a":{"encoding":"base64","value":"!"}}}',
    '{"format":"tuyha-db-v1","records":{"a":{"encoding":"json"}}}',
    '{"format":"tuyha-db-v1","records":{"a":{"encoding":"text","value":"x","nul":true}}}',
    '{"format":"tuyha-db-v1","records":{"a":{"encoding":"json","value":NaN}}}',
])
def test_bad_dump_inputs_rejected(text: str) -> None:
    with pytest.raises(ValueError, match="invalid TuyHA JSON"):
        load_json(text)

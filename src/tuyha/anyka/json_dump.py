"""Editable, unredacted JSON with exact decoded record-byte round trips."""

import base64
import json
from dataclasses import asdict

from .db import KVMap
from .rcs import RcsActive, decode_rcs_active, encode_rcs_active

FORMAT = "tuyha-db-v1"


def encode_record(record: object) -> bytes:
    if (not isinstance(record, dict) or not {"encoding", "value"}.issubset(record)
            or set(record) - {"encoding", "value", "nul"}):
        raise ValueError("invalid JSON record envelope")
    encoding, value = record.get("encoding"), record.get("value")
    nul = record.get("nul", 0)
    if type(nul) is not int or not 0 <= nul <= 65535:
        raise ValueError("invalid JSON record NUL count")
    match encoding:
        case "base64":
            if not isinstance(value, str):
                raise ValueError("base64 record requires a string")
            raw = base64.b64decode(value, validate=True)
        case "text":
            if not isinstance(value, str):
                raise ValueError("text record requires a string")
            raw = value.encode("utf-8")
        case "json" | "wifi":
            if encoding == "wifi":
                if not isinstance(value, dict):
                    raise ValueError("Wi-Fi record requires an object")
                value = dict(value)
                if value.get("wfb64") == 1:
                    for field in ("ssid", "passwd"):
                        if not isinstance(value.get(field), str):
                            raise ValueError("Wi-Fi credentials require strings")
                        value[field] = base64.b64encode(value[field].encode("utf-8")).decode("ascii")
            raw = json.dumps(value, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
        case "rcs":
            if value is None:
                raw = encode_rcs_active(None)
            else:
                if not isinstance(value, dict) or set(value) != {"code", "url0", "url1", "source", "pub", "cert_b64"}:
                    raise ValueError("invalid RCS JSON fields")
                if any(not isinstance(value[k], str) for k in ("code", "url0", "url1")):
                    raise ValueError("invalid RCS JSON strings")
                if any(type(value[k]) is not int for k in ("source", "pub")):
                    raise ValueError("invalid RCS JSON integers")
                if value["cert_b64"] is not None and not isinstance(value["cert_b64"], str):
                    raise ValueError("invalid RCS JSON certificate")
                raw = encode_rcs_active(RcsActive(**value))
        case "log-level":
            if not isinstance(value, dict) or set(value) != {"level", "expires_at"}:
                raise ValueError("invalid log-level JSON fields")
            if any(type(value[k]) is not int for k in value) or not 0 <= value["level"] <= 5:
                raise ValueError("invalid log-level JSON integers")
            raw = value["level"].to_bytes(4, "little") + value["expires_at"].to_bytes(4, "little")
        case _:
            raise ValueError("unknown JSON record encoding")
    return raw + b"\x00" * nul


def decode_record(name: str, raw: bytes) -> dict[str, object]:
    try:
        record = _readable_record(name, raw)
        if encode_record(record) == raw:
            return record
    except (ValueError, TypeError, OverflowError, UnicodeError, KeyError, RecursionError):
        pass
    try:
        return {"encoding": "text", "value": raw.decode("utf-8")}
    except UnicodeDecodeError:
        return {"encoding": "base64", "value": base64.b64encode(raw).decode("ascii")}


def _readable_record(name: str, raw: bytes) -> dict[str, object]:
    if name in {"rcs.active", "rcs.mf"}:
        rcs = decode_rcs_active(raw)
        return {"encoding": "rcs", "value": asdict(rcs) if rcs else None}
    if name == "localLogLevel" and len(raw) == 8:
        return {"encoding": "log-level", "value": {
            "level": int.from_bytes(raw[:4], "little"), "expires_at": int.from_bytes(raw[4:], "little"),
        }}
    stripped = raw.rstrip(b"\x00")
    value = json.loads(stripped)
    encoding = "json"
    if name == "gw_wsm" and isinstance(value, dict) and value.get("wfb64") == 1:
        for field in ("ssid", "passwd"):
            value[field] = base64.b64decode(value[field], validate=True).decode("utf-8")
        encoding = "wifi"
    return {"encoding": encoding, "value": value, "nul": len(raw) - len(stripped)}


def dump_json(kv: KVMap) -> str:
    records = {name: decode_record(name, value) for name, value in sorted(kv.items())}
    return json.dumps({"format": FORMAT, "records": records}, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def load_json(text: str) -> KVMap:
    try:
        value = json.loads(text, object_pairs_hook=_unique_object)
        if not isinstance(value, dict) or set(value) != {"format", "records"} or value["format"] != FORMAT:
            raise ValueError("unsupported JSON dump format")
        if not isinstance(value["records"], dict):
            raise ValueError("JSON records must be an object")
        return {name: encode_record(record) for name, record in value["records"].items()}
    except (ValueError, TypeError, OverflowError, UnicodeError, RecursionError) as exc:
        raise ValueError("invalid TuyHA JSON dump; check format and record encodings") from exc

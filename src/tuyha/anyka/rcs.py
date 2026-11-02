import base64
from dataclasses import dataclass


@dataclass(frozen=True)
class RcsActive:
    code: str
    url0: str
    url1: str
    source: int = 1
    pub: int = 0
    cert_b64: str | None = None


def validate_host_port(endpoint: str, field_name: str = "endpoint") -> None:
    if not endpoint:
        raise ValueError(f"{field_name} is required")
    if "://" in endpoint or "/" in endpoint:
        raise ValueError(f"{field_name} must be host[:port] only (no scheme/path)")
    if any(char.isspace() for char in endpoint) or any(char in endpoint for char in "\x00?#@"):
        raise ValueError(f"{field_name} contains invalid host characters")
    if ":" not in endpoint:
        return
    host, port_text = endpoint.rsplit(":", 1)
    if not host:
        raise ValueError(f"{field_name} host is empty")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError(f"{field_name} port is invalid") from exc
    if port < 1 or port > 65535:
        raise ValueError(f"{field_name} port must be 1-65535")


def _append_entry(out: bytearray, entry_type: int, data: bytes) -> None:
    if len(data) > 65535:
        raise ValueError("RCS entry is too large")
    out.extend([entry_type, len(data) & 0xFF, (len(data) >> 8) & 0xFF])
    out.extend(data)


def encode_rcs_active(value: RcsActive | None) -> bytes:
    if value is None:
        return b"\x00"
    if value.source < 0 or value.source > 255:
        raise ValueError("rcs.active.source must be 0-255")
    if value.pub < 0 or value.pub > 255:
        raise ValueError("rcs.active.pub must be 0-255")
    if not value.code or "\x00" in value.code:
        raise ValueError("rcs.active.code is required")
    validate_host_port(value.url0, "rcs.active.url0")
    validate_host_port(value.url1, "rcs.active.url1")

    out = bytearray(bytes([0x01, 0x01, 0x00, 0x00, 0x02, 0x01, 0x00, 0x01]))
    _append_entry(out, 1, bytes([value.source & 0xFF]))
    _append_entry(out, 2, bytes([value.pub & 0xFF]))
    _append_entry(out, 3, value.code.encode("utf-8") + b"\x00")
    _append_entry(out, 4, value.url0.encode("utf-8") + b"\x00")
    _append_entry(out, 5, value.url1.encode("utf-8") + b"\x00")
    if value.cert_b64 is not None:
        if not value.cert_b64:
            raise ValueError("rcs.active.cert_b64 must be a base64 string or null")
        _append_entry(out, 6, base64.b64decode(value.cert_b64, validate=True))
    return bytes(out)


def decode_rcs_active(data: bytes) -> RcsActive | None:
    if data == b"\x00":
        return None
    if data[:8] != bytes([1, 1, 0, 0, 2, 1, 0, 1]):
        raise ValueError("unsupported RCS header")
    entries: dict[int, bytes] = {}
    pos = 8
    while pos < len(data):
        if pos + 3 > len(data):
            raise ValueError("truncated RCS entry")
        tag = data[pos]
        size = int.from_bytes(data[pos + 1:pos + 3], "little")
        pos += 3
        if tag not in range(1, 7) or tag in entries or pos + size > len(data):
            raise ValueError("invalid RCS entry")
        entries[tag] = data[pos:pos + size]
        pos += size
    if not {1, 2, 3, 4, 5}.issubset(entries) or any(len(entries[t]) != 1 for t in (1, 2)):
        raise ValueError("missing or invalid RCS fields")
    texts: list[str] = []
    for tag in (3, 4, 5):
        raw = entries[tag]
        if not raw.endswith(b"\x00") or b"\x00" in raw[:-1]:
            raise ValueError("invalid RCS string")
        texts.append(raw[:-1].decode("utf-8"))
    result = RcsActive(
        code=texts[0], url0=texts[1], url1=texts[2], source=entries[1][0], pub=entries[2][0],
        cert_b64=base64.b64encode(entries[6]).decode("ascii") if 6 in entries else None,
    )
    encode_rcs_active(result)
    return result

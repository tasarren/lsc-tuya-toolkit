from dataclasses import dataclass
from pathlib import Path

from tuyha.contracts.inputs import GeneratedIdentity

UUID_INI_NAME = "_ht_uuid.ini"


@dataclass(frozen=True)
class UuidIni:
    pid: str
    uuid: str
    auth_key: str
    encrypt: int


def encode_not_string(value: str) -> str:
    # ENCRYPT=0 firmware stores per-byte bitwise NOT as raw 8-bit values.
    # latin-1 keeps high bytes as-is; UTF-8 would expand them and break ht_device_id_get.
    return bytes((~byte) & 0xFF for byte in value.encode("ascii")).decode("latin-1")


def decode_not_string(value: str) -> str:
    return bytes((~byte) & 0xFF for byte in value.encode("latin-1")).decode("ascii")


def write_uuid_ini(path: Path, identity: GeneratedIdentity) -> None:
    pid = identity.product_key or ""
    uuid = identity.uuid or ""
    auth_key = identity.auth_key or ""
    if not 8 <= len(pid) <= 16:
        raise ValueError("product_key must be 8 through 16 characters for _ht_uuid.ini pid")
    if len(uuid) not in {20, 43}:
        raise ValueError("uuid must be 20 or 43 characters for _ht_uuid.ini")
    if len(auth_key) != 32:
        raise ValueError("auth_key must be 32 characters for _ht_uuid.ini")
    body = (
        "[config]\n"
        f"pid = {encode_not_string(pid)}\n"
        f"uuid = {encode_not_string(uuid)}\n"
        f"authkey = {encode_not_string(auth_key)}\n"
        "encrypt = 0\n"
    )
    path.write_bytes(body.encode("latin-1"))


def decode_uuid_ini(raw: bytes) -> UuidIni:
    values: dict[str, str] = {}
    # Split on LF only. Do not str.splitlines()/str.strip(): both treat U+0085
    # as whitespace, and ASCII 'z' encodes to 0x85 under ENCRYPT=0 NOT.
    for line in raw.decode("latin-1").split("\n"):
        if line.endswith("\r"):
            line = line[:-1]
        if not line or line.startswith("[") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = _lstrip_one_space(value)
    encrypt = int(values.get("encrypt", "0"))
    pid = values.get("pid", "")
    uuid = values.get("uuid", "")
    auth_key = values.get("authkey", "")
    if encrypt == 0:
        return UuidIni(
            pid=decode_not_string(pid),
            uuid=decode_not_string(uuid),
            auth_key=decode_not_string(auth_key),
            encrypt=0,
        )
    return UuidIni(pid=pid, uuid=uuid, auth_key=auth_key, encrypt=encrypt)


def _lstrip_one_space(value: str) -> str:
    if value.startswith(" "):
        return value[1:]
    return value

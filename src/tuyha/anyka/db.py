import struct
from dataclasses import dataclass
from pathlib import Path

from .crypto import aes_ecb_decrypt, aes_ecb_encrypt, crc32, derive_aes_key_from_enckey
from .crypto import tal_get_actual_length_weak

MAGIC = 0x55AA55AA
REC_MAX = 0x200
REC_SIZE = 0x38
HD_SIZE = 0x1C + REC_MAX * REC_SIZE
NAME_SIZE = 0x24
NAME_MAX = 0x21
DATA_LEN_MAX = 0xFFFF
KVMap = dict[str, bytes]


@dataclass(frozen=True)
class RecordHeader:
    name: str
    capacity: int
    start: int
    enc_len: int
    data_crc: int


def cap_for(enc_len: int) -> int:
    return ((enc_len + 0x40) & ~3) + 4


def read_header(buf: bytes) -> tuple[int, int, int]:
    if len(buf) < HD_SIZE:
        raise ValueError("database is smaller than its fixed header")

    crc, ver, wr_count, data_hd_size, magic, rec_max, rec_cnt = struct.unpack_from("<7I", buf, 0)
    if magic != MAGIC:
        raise ValueError("database magic is not Anyka KV")
    if rec_max != REC_MAX:
        raise ValueError("declared record capacity does not match format")
    if data_hd_size != HD_SIZE:
        raise ValueError("declared header size does not match format")
    if rec_cnt > REC_MAX:
        raise ValueError("record count exceeds fixed capacity")

    crc_region_len = rec_cnt * REC_SIZE + 0x18
    calc = crc32(buf[0x04 : 0x04 + crc_region_len])
    if calc != crc:
        raise ValueError("header checksum mismatch")
    return ver, wr_count, rec_cnt


def load_kv_bytes(db_bytes: bytes, enckey: bytes) -> KVMap:
    key = derive_aes_key_from_enckey(enckey)
    read_header(db_bytes)
    kv: KVMap = {}
    for header in record_headers(db_bytes):
        ciphertext = db_bytes[header.start : header.start + header.enc_len]
        if crc32(ciphertext) != header.data_crc:
            raise ValueError("record checksum mismatch")
        padded = aes_ecb_decrypt(key, ciphertext)
        actual_len = _plain_length(padded)
        if actual_len < 0:
            raise ValueError("record padding check failed")
        kv[header.name] = padded[:actual_len]
    return kv


def load_kv(db_path: Path, enckey_path: Path) -> KVMap:
    return load_kv_bytes(db_path.read_bytes(), enckey_path.read_bytes())


def record_headers(db_bytes: bytes) -> tuple[RecordHeader, ...]:
    headers: list[RecordHeader] = []
    seen: set[str] = set()
    for index in range(REC_MAX):
        header = _parse_record(db_bytes, index)
        if header is None:
            continue
        if header.name in seen:
            raise ValueError("duplicate record name")
        seen.add(header.name)
        headers.append(header)
    _reject_overlap(headers)
    return tuple(headers)


def build_db(kv: KVMap, enckey: bytes, wr_count: int = 1) -> bytes:
    key = derive_aes_key_from_enckey(enckey)
    items = sorted(kv.items(), key=lambda item: item[0])
    if len(items) > REC_MAX:
        raise ValueError("too many records for the fixed record capacity")
    if not 0 <= wr_count <= 0xFFFFFFFF:
        raise ValueError("write count is out of range")
    header = bytearray(HD_SIZE)
    items_cnt = len(items)
    struct.pack_into("<7I", header, 0, 0, 2, wr_count, HD_SIZE, MAGIC, REC_MAX, items_cnt)
    data = bytearray()
    cur = HD_SIZE

    for idx, (name, value) in enumerate(items):
        key_bytes = _encode_name(name)
        ciphertext = aes_ecb_encrypt(key, value)
        enc_len = len(ciphertext)
        if enc_len > DATA_LEN_MAX:
            raise ValueError("record data exceeds the header length field")
        capacity = cap_for(enc_len)
        data.extend(ciphertext)
        data.extend(b"\x00" * (capacity - enc_len))
        rec_off = 0x1C + idx * REC_SIZE
        struct.pack_into("<I", header, rec_off, 1)
        header[rec_off + 0x04 : rec_off + 0x04 + NAME_SIZE] = key_bytes.ljust(NAME_SIZE, b"\x00")
        struct.pack_into("<II", header, rec_off + 0x28, capacity, cur)
        struct.pack_into("<H", header, rec_off + 0x30, enc_len)
        struct.pack_into("<H", header, rec_off + 0x32, 0)
        struct.pack_into("<I", header, rec_off + 0x34, crc32(ciphertext))
        cur += capacity

    out = bytearray(header) + bytes(data)
    crc_region_len = items_cnt * REC_SIZE + 0x18
    struct.pack_into("<I", out, 0, crc32(out[0x04 : 0x04 + crc_region_len]))
    return bytes(out)


def _parse_record(db_bytes: bytes, index: int) -> RecordHeader | None:
    off = 0x1C + index * REC_SIZE
    valid = struct.unpack_from("<I", db_bytes, off)[0]
    if valid != 1:
        return None
    name = _decode_name(db_bytes[off + 0x04 : off + 0x28])
    if name is None:
        return None
    capacity, start = struct.unpack_from("<II", db_bytes, off + 0x28)
    enc_len = struct.unpack_from("<H", db_bytes, off + 0x30)[0]
    data_crc = struct.unpack_from("<I", db_bytes, off + 0x34)[0]
    if enc_len == 0:
        raise ValueError("record has no data")
    if enc_len % 16:
        raise ValueError("record length is not a whole cipher block")
    if capacity < enc_len:
        raise ValueError("record capacity is smaller than its encoded length")
    if start < HD_SIZE:
        raise ValueError("record data starts inside the header")
    if start + capacity > len(db_bytes):
        raise ValueError("record data extends beyond the file")
    return RecordHeader(name=name, capacity=capacity, start=start, enc_len=enc_len, data_crc=data_crc)


def _plain_length(padded: bytes) -> int:
    actual_len = tal_get_actual_length_weak(padded)
    if actual_len == -3 and padded == b"\x10" * len(padded):
        return 0
    return actual_len


def _reject_overlap(headers: list[RecordHeader]) -> None:
    spans = sorted((header.start, header.start + header.capacity) for header in headers)
    for (_start, end), (next_start, _next_end) in zip(spans, spans[1:]):
        if next_start < end:
            raise ValueError("record data ranges overlap")


def _encode_name(name: str) -> bytes:
    if not name:
        raise ValueError("record name is empty")
    if "\x00" in name:
        raise ValueError("record name contains a NUL byte")
    try:
        name_bytes = name.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("record name is not valid UTF-8") from exc
    if len(name_bytes) >= NAME_MAX:
        raise ValueError("record name exceeds the name field limit")
    return name_bytes


def _decode_name(raw: bytes) -> str | None:
    name_bytes = raw.split(b"\x00", 1)[0]
    if not name_bytes:
        return None
    if len(name_bytes) >= NAME_MAX:
        raise ValueError("record name exceeds the name field limit")
    try:
        return name_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("record name is not valid UTF-8") from exc

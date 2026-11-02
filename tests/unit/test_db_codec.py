import struct

import pytest

from tuyha.anyka.crypto import crc32
from tuyha.anyka.db import (
    HD_SIZE,
    NAME_SIZE,
    REC_MAX,
    REC_SIZE,
    build_db,
    load_kv_bytes,
    read_header,
    record_headers,
)

ENCKEY = bytes(range(16))


def _db(kv: dict[str, bytes] | None = None) -> bytes:
    return build_db(kv if kv is not None else {"gw_ai": b'{"cloud_cap":1}'}, ENCKEY)


def _record_offset(index: int) -> int:
    return 0x1C + index * REC_SIZE


def _corrupt(db_bytes: bytes, offset: int, payload: bytes) -> bytes:
    body = bytearray(db_bytes)
    body[offset : offset + len(payload)] = payload
    return bytes(body)


def test_simplekv_build_reload_round_trip_with_enckey_bytes() -> None:
    kv = {"gw_ai": b'{"cloud_cap":1}', "tuya_seed": b"s" * 64}

    db_bytes = build_db(kv, ENCKEY, wr_count=7)
    version, wr_count, rec_cnt = read_header(db_bytes)

    assert version == 2
    assert wr_count == 7
    assert rec_cnt == len(kv)
    assert load_kv_bytes(db_bytes, ENCKEY) == kv


def test_record_headers_report_declared_layout() -> None:
    headers = record_headers(_db({"gw_ai": b"x" * 20}))

    assert len(headers) == 1
    assert headers[0].name == "gw_ai"
    assert headers[0].start >= HD_SIZE
    assert headers[0].enc_len % 16 == 0
    assert headers[0].capacity > headers[0].enc_len


def test_short_file_is_rejected() -> None:
    with pytest.raises(ValueError, match="smaller than its fixed header"):
        read_header(b"\x00" * 16)


def test_bad_magic_is_rejected() -> None:
    with pytest.raises(ValueError, match="magic"):
        read_header(_corrupt(_db(), 0x10, b"\x00\x00\x00\x00"))


def test_header_checksum_is_enforced() -> None:
    with pytest.raises(ValueError, match="header checksum"):
        read_header(_corrupt(_db(), 0x04, b"\xff"))


def test_record_count_beyond_capacity_is_rejected() -> None:
    db_bytes = _corrupt(_db(), 0x18, struct.pack("<I", REC_MAX + 1))

    with pytest.raises(ValueError, match="record count exceeds fixed capacity"):
        read_header(db_bytes)


def test_record_checksum_is_enforced_without_leaking_the_name() -> None:
    db_bytes = _corrupt(_db({"camera_secret_name": b"value"}), HD_SIZE, b"\xff")

    with pytest.raises(ValueError) as caught:
        load_kv_bytes(db_bytes, ENCKEY)
    assert "checksum" in str(caught.value)
    assert "camera_secret_name" not in str(caught.value)


def test_duplicate_record_name_is_rejected() -> None:
    db_bytes = _db({"gw_ai": b"a", "gw_di": b"b"})
    body = bytearray(db_bytes)
    first = body[_record_offset(0) + 0x04 : _record_offset(0) + 0x04 + NAME_SIZE]
    body[_record_offset(1) + 0x04 : _record_offset(1) + 0x04 + NAME_SIZE] = first

    with pytest.raises(ValueError, match="duplicate record name"):
        record_headers(bytes(body))


def test_bytes_after_the_name_terminator_are_ignored() -> None:
    db_bytes = _db({"gw_ai": b"a"})
    body = bytearray(db_bytes)
    body[_record_offset(0) + 0x04 + NAME_SIZE - 1] = 0x41

    headers = record_headers(bytes(body))

    assert headers[0].name == "gw_ai"


def test_unused_slot_flag_values_are_skipped() -> None:
    body = bytearray(_db({"gw_ai": b"a"}))
    struct.pack_into("<I", body, _record_offset(0), 2)

    assert record_headers(bytes(body)) == ()


def test_non_utf8_name_is_rejected() -> None:
    db_bytes = _db({"gw_ai": b"a"})
    body = bytearray(db_bytes)
    body[_record_offset(0) + 0x04] = 0xFF

    with pytest.raises(ValueError, match="UTF-8"):
        record_headers(bytes(body))


def test_length_beyond_file_is_rejected() -> None:
    db_bytes = _db({"gw_ai": b"a"})
    body = bytearray(_db({"gw_ai": b"a"}))
    struct.pack_into("<I", body, _record_offset(0) + 0x2C, len(db_bytes))

    with pytest.raises(ValueError, match="extends beyond the file"):
        record_headers(bytes(body))


def test_capacity_smaller_than_data_is_rejected() -> None:
    body = bytearray(_db({"gw_ai": b"a"}))
    enc_len = struct.unpack_from("<H", body, _record_offset(0) + 0x30)[0]
    struct.pack_into("<I", body, _record_offset(0) + 0x28, enc_len - 4)

    with pytest.raises(ValueError, match="capacity is smaller"):
        record_headers(bytes(body))


def test_capacity_larger_than_builder_alignment_is_accepted() -> None:
    body = bytearray(_db({"gw_ai": b"a"}))
    capacity = struct.unpack_from("<I", body, _record_offset(0) + 0x28)[0]
    struct.pack_into("<I", body, _record_offset(0) + 0x28, capacity + 8)
    body.extend(b"\x00" * 8)
    rec_cnt = struct.unpack_from("<I", body, 0x18)[0]
    region = bytes(body[0x04 : 0x04 + rec_cnt * REC_SIZE + 0x18])
    struct.pack_into("<I", body, 0, crc32(region))

    headers = record_headers(bytes(body))

    assert headers[0].capacity == capacity + 8
    assert load_kv_bytes(bytes(body), ENCKEY) == {"gw_ai": b"a"}


def test_empty_record_round_trips() -> None:
    db_bytes = build_db({"gw_ai": b""}, ENCKEY)

    assert load_kv_bytes(db_bytes, ENCKEY) == {"gw_ai": b""}


def test_overlapping_records_are_rejected() -> None:
    body = bytearray(_db({"gw_ai": b"a", "gw_di": b"b"}))
    first_start = struct.unpack_from("<I", body, _record_offset(0) + 0x2C)[0]
    struct.pack_into("<I", body, _record_offset(1) + 0x2C, first_start)

    with pytest.raises(ValueError, match="overlap"):
        record_headers(bytes(body))


def test_builder_rejects_unusable_names() -> None:
    with pytest.raises(ValueError, match="name is empty"):
        build_db({"": b"value"}, ENCKEY)
    with pytest.raises(ValueError, match="name field limit"):
        build_db({"k" * 33: b"value"}, ENCKEY)
    with pytest.raises(ValueError, match="contains a NUL byte"):
        build_db({"gw\x00ai": b"value"}, ENCKEY)


def test_builder_rejects_write_count_out_of_range() -> None:
    with pytest.raises(ValueError, match="write count is out of range"):
        build_db({"gw_ai": b"value"}, ENCKEY, wr_count=-1)


def test_builder_rejects_more_records_than_capacity() -> None:
    with pytest.raises(ValueError, match="too many records"):
        build_db({f"k{index:03d}": b"v" for index in range(REC_MAX + 1)}, ENCKEY)


def test_builder_rejects_data_beyond_length_field() -> None:
    with pytest.raises(ValueError, match="length field"):
        build_db({"gw_ai": b"x" * 0x10000}, ENCKEY)

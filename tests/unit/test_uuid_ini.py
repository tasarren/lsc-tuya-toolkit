from pathlib import Path

from tuyha.contracts.inputs import GeneratedIdentity
from tuyha.materializer.uuid_ini import decode_not_string, decode_uuid_ini, encode_not_string, write_uuid_ini


def test_encrypt0_not_encoding_round_trips_ascii_identity() -> None:
    plaintext = "tuyhaLocalPk"
    encoded = encode_not_string(plaintext)

    assert encoded != plaintext
    assert decode_not_string(encoded) == plaintext


def test_write_uuid_ini_uses_encrypt0_and_matches_identity(tmp_path: Path) -> None:
    identity = GeneratedIdentity(
        uuid="u" * 20,
        auth_key="a" * 32,
        product_key="tuyhaLocalPk",
    )
    path = tmp_path / "_ht_uuid.ini"

    write_uuid_ini(path, identity)
    decoded = decode_uuid_ini(path.read_bytes())

    assert decoded.encrypt == 0
    assert decoded.pid == "tuyhaLocalPk"
    assert decoded.uuid == "u" * 20
    assert decoded.auth_key == "a" * 32
    assert b"encrypt = 0" in path.read_bytes()


def test_write_uuid_ini_round_trips_ascii_z_which_encodes_to_u0085(tmp_path: Path) -> None:
    identity = GeneratedIdentity(
        uuid="z" * 20,
        auth_key="z" * 32,
        product_key="tuyhaLocalPk",
    )
    path = tmp_path / "_ht_uuid.ini"

    write_uuid_ini(path, identity)
    decoded = decode_uuid_ini(path.read_bytes())

    assert decoded.uuid == "z" * 20
    assert decoded.auth_key == "z" * 32
    assert b"\x85" in path.read_bytes()


def test_write_uuid_ini_keeps_not_bytes_as_latin1_not_utf8(tmp_path: Path) -> None:
    identity = GeneratedIdentity(
        uuid="u" * 20,
        auth_key="a" * 32,
        product_key="tuyhaLocalPk",
    )
    path = tmp_path / "_ht_uuid.ini"
    write_uuid_ini(path, identity)
    raw = path.read_bytes()
    not_pid = bytes((~byte) & 0xFF for byte in b"tuyhaLocalPk")

    assert not_pid in raw
    assert all(byte >= 0x80 for byte in not_pid)
    assert b"\xc2" not in raw

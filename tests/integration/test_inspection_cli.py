import base64
import json
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization

from tuyha.anyka.db import build_db, load_kv
from tuyha.anyka.json_dump import load_json
from tuyha.cli.main import main
from tuyha.materializer.uuid_ini import decode_uuid_ini


def create(path: Path, *options: str) -> Path:
    assert main(["create", "--output-dir", str(path), "--wifi-ssid", "LabNet",
                 "--wifi-password", "LabPass", *options]) == 0
    return path / "tuya_user.hacked.db"


def test_create_dump_edit_create_and_verify(tmp_path: Path, capsys) -> None:
    db = create(tmp_path / "first", "--rcs-host", "rcs.local", "--no-rcs-cert-b64")
    key = db.with_name("tuya_enckey.hacked.db")
    original = load_kv(db, key)
    original["vendor.binary"] = b"\x00\xff\x01\x00"
    original["prefix"] = b"b64:AAAA"
    db.write_bytes(build_db(original, key.read_bytes()))
    before = {path.relative_to(db.parent): path.read_bytes() for path in db.parent.rglob("*") if path.is_file()}
    assert main(["verify", "--file", str(db), "--scratch"]) == 0
    dumped = tmp_path / "full.json"
    assert main(["dump", "--file", str(db), "--output", str(dumped)]) == 0
    assert load_json(dumped.read_text()) == original
    assert dumped.stat().st_mode & 0o777 == 0o600
    payload = json.loads(dumped.read_text())
    assert payload["records"]["gw_wsm"]["value"]["passwd"] == "LabPass"
    payload["records"]["gw_wsm"]["value"]["ssid"] = "YWJj"
    dumped.write_text(json.dumps(payload))
    out = tmp_path / "second"
    assert main(["create", "--from", str(dumped), "--output-dir", str(out),
                 "--wifi-password", "NewPass", "--broker-host", "broker.local"]) == 0
    rebuilt = load_kv(out / db.name, out / key.name)
    assert rebuilt["vendor.binary"] == original["vendor.binary"]
    assert rebuilt["prefix"] == original["prefix"]
    assert rebuilt["gw_bi"] == original["gw_bi"]
    assert rebuilt["tuya_seed"] == original["tuya_seed"]
    assert rebuilt["tls_ca0"] != original["tls_ca0"]
    assert base64.b64decode(json.loads(rebuilt["gw_wsm"])["ssid"]) == b"YWJj"
    assert base64.b64decode(json.loads(rebuilt["gw_wsm"])["passwd"]) == b"NewPass"
    assert json.loads(rebuilt["gw_ai"])["mqs_url"] == "broker.local:8883"
    assert main(["verify", "--file", str(out / db.name), "--scratch"]) == 0
    assert decode_uuid_ini((out / "_ht_uuid.ini").read_bytes()).uuid == json.loads(rebuilt["gw_bi"])["uuid"]
    cert = x509.load_pem_x509_certificate((out / "mqtt/server.crt").read_bytes())
    private_key = serialization.load_pem_private_key((out / "mqtt/server.key").read_bytes(), None)
    assert cert.public_key().public_numbers() == private_key.public_key().public_numbers()
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["source_kind"] == "json"
    assert {path.relative_to(db.parent): path.read_bytes() for path in db.parent.rglob("*") if path.is_file()} == before
    assert out.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in out.rglob("*") if path.is_file())
    output = capsys.readouterr()
    for secret in ("LabPass", "NewPass", json.loads(original["gw_bi"])["auth_key"]):
        assert secret not in output.out + output.err


def test_dump_verify_without_tls_and_explicit_custom_key(tmp_path: Path) -> None:
    db, key = tmp_path / "custom.db", tmp_path / "key.bin"
    key.write_bytes(bytes(range(16)))
    kv = {"vendor": b"\xff\x00", "empty": b""}
    db.write_bytes(build_db(kv, key.read_bytes()))
    assert main(["verify", "--file", str(db), "--enckey", str(key)]) == 0
    assert main(["verify", "--file", str(db), "--enckey", str(key), "--scratch"]) == 1
    dumped = tmp_path / "dump.json"
    assert main(["dump", "--file", str(db), "--enckey", str(key), "--output", str(dumped)]) == 0
    assert load_json(dumped.read_text()) == kv
    assert main(["verify", "--file", str(db)]) == 2
    assert main(["dump", "--file", str(db), "--enckey", str(key), "--output", str(db)]) == 2
    assert load_kv(db, key) == kv


def test_failed_creation_preserves_source_and_existing_output(tmp_path: Path) -> None:
    out = tmp_path / "existing"
    db = create(out)
    before = {path.relative_to(out): path.read_bytes() for path in out.rglob("*") if path.is_file()}
    assert main(["create", "--output-dir", str(out), "--wifi-ssid", "X", "--wifi-password", "Y",
                 "--tls-validity-days", "0"]) == 2
    dumped = tmp_path / "bad.json"
    assert main(["dump", "--file", str(db), "--output", str(dumped)]) == 0
    data = json.loads(dumped.read_text())
    data["records"]["rcs.active"]["value"]["source"] = -1
    dumped.write_text(json.dumps(data))
    assert main(["create", "--from", str(dumped), "--output-dir", str(tmp_path / "bad")]) == 2
    assert not (tmp_path / "bad").exists()
    assert {path.relative_to(out): path.read_bytes() for path in out.rglob("*") if path.is_file()} == before
    assert not list(tmp_path.glob(".tuyha-*"))


def test_inactive_dump_import_and_late_failure_cleanup(tmp_path: Path) -> None:
    from tuyha.anyka.json_dump import dump_json

    source = tmp_path / "inactive.json"
    source.write_text(dump_json({
        "gw_bi": b'{"uuid":"","auth_key":""}',
        "gw_di": b'{"id":"","pk":"","s_id":""}',
        "gw_ai": b'{"mqs_url":""}',
        "gw_wsm": b'{"ssid":"","passwd":"","wfb64":1,"stat":0}',
        "rcs.active": b"\x00",
    }))
    out = tmp_path / "imported"
    assert main(["create", "--from", str(source), "--output-dir", str(out),
                 "--broker-host", "127.0.0.1"]) == 0
    assert main(["verify", "--file", str(out / "tuya_user.hacked.db")]) == 0
    assert main(["verify", "--file", str(out / "tuya_user.hacked.db"), "--scratch"]) == 1
    # Bad semantic data gets as far as staging, but must never be published.
    source.write_text(dump_json({"gw_ai": b'{"mqs_url":"127.0.0.1:8883"}',
                                 "localLogLevel": b"bad"}))
    assert main(["create", "--from", str(source), "--output-dir", str(tmp_path / "failed")]) == 2
    assert not (tmp_path / "failed").exists()
    assert not list(tmp_path.glob(".tuyha-*"))


@pytest.mark.parametrize("name", ["tuya_user.db", "tuya_user.original.db", "tuya_user.hacked.db"])
def test_sibling_enckey_name(name: str, tmp_path: Path) -> None:
    db = tmp_path / name
    key = tmp_path / name.replace("tuya_user", "tuya_enckey")
    key.write_bytes(bytes(range(16)))
    db.write_bytes(build_db({"unknown": b"value"}, key.read_bytes()))
    assert main(["verify", "--file", str(db)]) == 0

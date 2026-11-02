"""Synthetic inactive state with null fields observed in factory DBs."""

import json
from pathlib import Path

import pytest

from tuyha.anyka.db import build_db, load_kv
from tuyha.anyka.json_dump import load_json
from tuyha.anyka.verify import verify_kv
from tuyha.cli.main import main


def factory_records() -> dict[str, bytes]:
    objects = {
        "gw_ai": dict.fromkeys(("mq_url", "mqs_url", "mq_psk", "h_url", "hs_url", "hs_psk", "key", "lckey")),
        "gw_wsm": {"ssid": None, "passwd": None, "region": None, "wfb64": 1, "stat": 0},
        "gw_bi": {"uuid": "u" * 20, "auth_key": "a" * 32, "psk_key": None},
        "gw_di": {"id": None, "pk": "factoryProduct", "s_id": None},
    }
    return {name: json.dumps(value, separators=(",", ":")).encode() for name, value in objects.items()}


def test_factory_null_dump_rebuild_preserves_inactive_state(tmp_path: Path, capsys) -> None:
    records = factory_records()
    records["tuya_seed"] = bytes(range(64))
    db, key = tmp_path / "tuya_user.original.db", tmp_path / "tuya_enckey.original.db"
    key.write_bytes(bytes(range(16)))
    db.write_bytes(build_db(records, key.read_bytes()))
    before = db.read_bytes(), key.read_bytes()
    assert main(["verify", "--file", str(db)]) == 0
    assert main(["verify", "--file", str(db), "--scratch"]) == 1
    dumped = tmp_path / "factory.json"
    assert main(["dump", "--file", str(db), "--output", str(dumped)]) == 0
    assert load_json(dumped.read_text()) == records
    out = tmp_path / "rebuilt"
    assert main(["create", "--from", str(dumped), "--output-dir", str(out)]) == 0
    rebuilt = load_kv(out / "tuya_user.hacked.db", out / "tuya_enckey.hacked.db")
    assert main(["verify", "--file", str(out / "tuya_user.hacked.db")]) == 0
    assert main(["verify", "--file", str(out / "tuya_user.hacked.db"), "--scratch"]) == 1
    assert rebuilt["gw_wsm"] == records["gw_wsm"]
    assert rebuilt["tuya_seed"] == records["tuya_seed"]
    assert json.loads(rebuilt["gw_ai"])["mqs_url"] is None
    assert json.loads(rebuilt["gw_bi"])["uuid"] == "u" * 20
    assert json.loads(rebuilt["gw_bi"])["auth_key"] == "a" * 32
    assert json.loads(rebuilt["gw_di"])["pk"] == "factoryProduct"
    assert json.loads(rebuilt["gw_di"])["id"]
    assert (db.read_bytes(), key.read_bytes()) == before
    output = capsys.readouterr()
    assert "a" * 32 not in output.out + output.err


@pytest.mark.parametrize("value", [123, False, [], {}])
def test_non_null_invalid_factory_field_types_still_fail(value: object) -> None:
    records = factory_records()
    for name, field in (("gw_ai", "mqs_url"), ("gw_wsm", "ssid"),
                        ("gw_bi", "psk_key"), ("gw_di", "id")):
        data = json.loads(records[name])
        data[field] = value
        changed = {**records, name: json.dumps(data).encode()}
        assert f"{name}.{field} is not a string" in verify_kv(changed)

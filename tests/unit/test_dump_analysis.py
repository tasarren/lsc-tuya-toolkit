import json
from pathlib import Path

from tuyha.anyka.db import load_kv
from tuyha.materializer.uuid_ini import decode_uuid_ini


def test_research_dump_records_wsm_wipe_and_encrypted_uuid_lengths(private_root: Path) -> None:
    config = private_root / "research" / "dumps" / "20000101_000016" / "etc" / "config"
    user_db = config / "tuya_user.db"
    enckey_db = config / "tuya_enckey.db"
    uuid_ini = config / "_ht_uuid.ini"
    assert user_db.is_file()
    assert enckey_db.is_file()
    assert uuid_ini.is_file()

    kv = load_kv(user_db, enckey_db)
    wsm = json.loads(kv["gw_wsm"].decode("utf-8"))
    bi = json.loads(kv["gw_bi"].decode("utf-8"))
    di = json.loads(kv["gw_di"].decode("utf-8"))
    decoded_ini = decode_uuid_ini(uuid_ini.read_bytes())

    # Factory dump after firmware reject: packed gw_wsm was reset, so STA strings are empty.
    for field in ("token", "reg_key", "region", "ssid", "passwd"):
        assert field in wsm
        assert wsm[field] in (None, "")
    assert set(wsm) >= {"token", "reg_key", "region", "ssid", "passwd"}

    assert decoded_ini.encrypt == 1
    assert int(decoded_ini.pid) == len(str(di["pk"]))
    assert int(decoded_ini.uuid) == len(str(bi["uuid"]))
    assert int(decoded_ini.auth_key) == len(str(bi["auth_key"]))
    assert int(decoded_ini.pid) == 16
    assert int(decoded_ini.uuid) == 20
    assert int(decoded_ini.auth_key) == 32

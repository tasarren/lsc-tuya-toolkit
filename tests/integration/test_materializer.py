import json
from pathlib import Path

from tuyha.anyka.db import load_kv
from tuyha.contracts.artifacts import TlsArtifactSet
from tuyha.contracts.inputs import ArtifactRequest, BrokerTarget, GeneratedIdentity, WifiInput
from tuyha.materializer.records import REQUIRED_SCRATCH_RECORDS
from tuyha.materializer.workflow import materialize_artifacts


def test_scratch_materializer_outputs_reloadable_minimum_records(tmp_path: Path) -> None:
    request = ArtifactRequest(
        wifi=WifiInput(ssid="LabNet", password="LabPass", region="EU"),
        broker_target=BrokerTarget(host="broker.local", port=8883),
        output_dir=tmp_path,
        identity=GeneratedIdentity(
            uuid="u" * 20,
            auth_key="a" * 32,
            device_id="dev12345",
            tuya_seed=b"s" * 64,
            enckey=bytes(range(16)),
        ),
    )

    artifacts = materialize_artifacts(request)
    kv = load_kv(artifacts.user_db, artifacts.enckey_db)
    manifest = json.loads(artifacts.manifest.read_text())

    assert artifacts.user_db.exists()
    assert isinstance(artifacts.tls, TlsArtifactSet)
    assert not (tmp_path / "tuya_user.hacked.db_bak").exists()
    assert "user_db_bak" not in manifest["files"]
    assert artifacts.enckey_db.read_bytes() == bytes(range(16))
    assert set(REQUIRED_SCRATCH_RECORDS).issubset(kv)
    assert json.loads(kv["gw_bi"].decode("utf-8"))["uuid"] == "u" * 20
    assert json.loads(kv["gw_di"].decode("utf-8"))["id"] == "dev12345"
    wsm = json.loads(kv["gw_wsm"].decode("utf-8"))
    assert wsm["region"] == "EU"
    assert len(wsm["token"]) <= 8
    assert len(wsm["reg_key"]) <= 4
    assert wsm["is_auto_connect"] is True
    assert wsm["is_auto_recover"] is True
    assert wsm["stat"] == 2
    assert wsm["nc_tp"] == 9
    assert kv[json.loads(kv["gw_di"].decode("utf-8"))["s_id"]] == b"[]"
    assert "ap_info_v3" not in kv
    assert kv["wf_start_md"] == b"2\x00"
    assert artifacts.uuid_ini is not None and artifacts.uuid_ini.exists()
    assert manifest["sd_copy_targets"]["uuid_ini"] == "sd_card/custom/state/_ht_uuid.ini"
    assert json.loads(kv["gw_ai"].decode("utf-8"))["mq_url"] == "broker.local:8883"
    assert len(kv["tuya_seed"]) == 64
    assert kv["rcs.active"] != b"\x00"
    assert kv["tls_ca_cnt"] == b"1\x00"
    assert kv["tls_ca0"].endswith(b"\x00")
    assert kv["tls_ca0"].rstrip(b"\x00").decode("ascii") == artifacts.tls.ca_cert_b64.read_text().strip()
    assert kv["p2p_type"] == b"4\x00"
    p2p_auth = json.loads(kv["p2p_auth_info"].rstrip(b"\x00").decode("utf-8"))
    assert p2p_auth["type"] == 4
    assert kv["p2p_auth_info"].startswith(b"{")
    assert kv["p2p_auth_info"].endswith(b"\x00")
    assert len(kv["p2p_pwd"]) == 9
    assert kv["p2p_pwd"].endswith(b"\x00")
    assert kv["p2p_pwd"][:-1].isascii() and len(kv["p2p_pwd"][:-1]) == 8
    assert json.loads(kv["gw_ai"].decode("utf-8"))["caArr"] == [
        kv["tls_ca0"].rstrip(b"\x00").decode("ascii")
    ]
    assert artifacts.tls.server_key_pem.exists()
    assert "PRIVATE KEY" not in artifacts.manifest.read_text()
    assert manifest["tls_files"]["server_key_pem_private"] is True
    assert "mosquitto_config" not in manifest["tls_files"]
    assert not (tmp_path / "mosquitto-tls.conf").exists()
    assert manifest["trust_mapping"]["hardware_sensitive"] is True
    assert manifest["sd_copy_targets"]["user_db"] == "sd_card/custom/state/tuya_user.hacked.db"


def test_regeneration_leaves_existing_db_bak_untouched(tmp_path: Path) -> None:
    stale_bak = tmp_path / "tuya_user.hacked.db_bak"
    stale_bak.write_bytes(b"previous-generation")
    request = ArtifactRequest(
        wifi=WifiInput(ssid="LabNet", password="LabPass", region="EU"),
        broker_target=BrokerTarget(host="broker.local", port=8883),
        output_dir=tmp_path,
        identity=GeneratedIdentity(uuid="u" * 20, auth_key="a" * 32, device_id="dev12345", enckey=bytes(range(16))),
    )

    materialize_artifacts(request)

    assert stale_bak.read_bytes() == b"previous-generation"
    assert (tmp_path / "tuya_user.hacked.db").exists()

import json
from pathlib import Path

from cryptography import x509

from tuyha.anyka.db import load_kv
from tuyha.cli.main import main


def test_cli_scratch_run_prints_artifact_location(tmp_path: Path, capsys) -> None:
    code = main(
        [
            "create",
            "--output-dir",
            str(tmp_path),
            "--wifi-ssid",
            "LabNet",
            "--wifi-password",
            "LabPass",
            "--broker-host",
            "broker.local",
            "--uuid",
            "u" * 20,
            "--auth-key",
            "a" * 32,
            "--device-id",
            "dev12345",
            "--enckey-hex",
            bytes(range(16)).hex(),
        ]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "manifest.json" in output
    assert "LabPass" not in output
    assert (tmp_path / "_ht_uuid.ini").exists()
    assert not (tmp_path / "tuya_user.hacked.db_bak").exists()
    assert "user_db_bak" not in output
    assert json.loads((tmp_path / "manifest.json").read_text())["source_kind"] == "scratch"


def test_cli_default_generation_keeps_loopback_broker_and_cert_sans(tmp_path: Path) -> None:
    code = main(
        [
            "create",
            "--output-dir",
            str(tmp_path),
            "--wifi-ssid",
            "LabNet",
            "--wifi-password",
            "LabPass",
        ]
    )

    assert code == 0
    kv = load_kv(tmp_path / "tuya_user.hacked.db", tmp_path / "tuya_enckey.hacked.db")
    gw_ai = json.loads(kv["gw_ai"].decode("utf-8"))
    assert gw_ai["mq_url"] == "127.0.0.1:8883"
    assert gw_ai["mqs_url"] == "127.0.0.1:8883"
    server_cert = x509.load_pem_x509_certificate((tmp_path / "mqtt/server.crt").read_bytes())
    sans = server_cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert set(sans.get_values_for_type(x509.DNSName)) == {"127.0.0.1"}
    assert {str(addr) for addr in sans.get_values_for_type(x509.IPAddress)} == {"127.0.0.1"}
    assert not (tmp_path / "mosquitto-tls.conf").exists()


def test_package_does_not_implement_deferred_runtime_surfaces() -> None:
    source_root = Path(__file__).parents[2] / "src" / "tuyha"
    source_text = "\n".join(path.read_text() for path in source_root.rglob("*.py"))

    assert "FastAPI(" not in source_text
    assert "sidecar" not in source_text.lower()

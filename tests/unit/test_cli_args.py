import pytest
from pathlib import Path

from tuyha.cli.args import parse_args
from tuyha.cli.create import build_request

REQUIRED = ["create", "--output-dir", "OUT", "--wifi-ssid", "LabNet", "--wifi-password", "LabPass"]


def test_default_request_and_tls_overrides() -> None:
    assert parse_args(["create"]).output_dir == Path("sd_card/custom/state")
    request = build_request(parse_args(REQUIRED))
    assert request.records is None
    assert request.wifi.ssid == "LabNet"
    assert request.broker_target.host == "127.0.0.1"
    assert request.broker_target.port == 8883
    request = build_request(parse_args(REQUIRED + [
        "--tls-ip-address", "127.0.0.1", "--tls-ip-address", "10.1.2.3",
        "--tls-dns-name", "camera.local", "--tls-common-name", "camera.local",
        "--tls-validity-days", "30", "--no-rcs-cert-b64", "--no-gw-ai-ca-arr",
    ]))
    assert request.tls.ip_addresses == ("127.0.0.1", "10.1.2.3")
    assert request.tls.dns_names == ("camera.local",)
    assert request.tls.common_name == "camera.local"
    assert request.tls.validity_days == 30
    assert not request.tls.include_rcs_cert_b64
    assert not request.tls.include_gw_ai_ca_arr


@pytest.mark.parametrize("args", [["profile", "dump"], REQUIRED[1:], REQUIRED + ["--mode", "compatibility"],
                                  REQUIRED + ["--source-user-db", "old.db"]])
def test_old_commands_rejected_without_echoing_values(args, capsys) -> None:
    with pytest.raises(SystemExit) as error:
        parse_args(args)
    assert error.value.code == 2
    assert "LabPass" not in capsys.readouterr().err


@pytest.mark.parametrize("option,value", [("--broker-port", "0"), ("--tls-validity-days", "0"),
                                          ("--broker-host", "example:9999"),
                                          ("--enckey-hex", "00"), ("--tuya-seed-b64", "!"),
                                          ("--region", "TOOLONG")])
def test_creation_input_validation(option, value) -> None:
    with pytest.raises(ValueError):
        build_request(parse_args(REQUIRED + [option, value]))

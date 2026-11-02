import pytest

from tuyha.anyka.rcs import RcsActive, encode_rcs_active


def test_rcs_active_encoder_accepts_host_port_values() -> None:
    encoded = encode_rcs_active(RcsActive(code="EU-PROD", url0="mqtt.local", url1="mqtt.local:443"))

    assert encoded.startswith(bytes([0x01, 0x01, 0x00, 0x00, 0x02, 0x01, 0x00, 0x01]))
    assert b"EU-PROD\x00" in encoded
    assert b"mqtt.local\x00" in encoded
    assert b"mqtt.local:443\x00" in encoded


@pytest.mark.parametrize("endpoint", ["https://mqtt.local", "mqtt.local/path", ":443"])
def test_rcs_active_encoder_rejects_scheme_path_or_empty_host(endpoint: str) -> None:
    with pytest.raises(ValueError, match=r"host\[:port\]|host"):
        encode_rcs_active(RcsActive(code="EU-PROD", url0=endpoint, url1="mqtt.local"))

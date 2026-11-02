import base64
import ipaddress
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization

from tuyha.contracts.inputs import BrokerTarget, TlsRequest
from tuyha.tls import generate_tls_material

CAMERA_EPOCH = datetime(2000, 1, 1, tzinfo=timezone.utc)


def test_tls_generator_writes_public_trust_inputs(tmp_path: Path) -> None:
    material = generate_tls_material(
        tmp_path,
        TlsRequest(common_name="broker.local", dns_names=("broker.local",)),
        BrokerTarget(host="broker.local", port=8899),
    )

    ca_cert = x509.load_pem_x509_certificate(material.artifacts.ca_cert_pem.read_bytes())
    server_cert = x509.load_pem_x509_certificate(material.artifacts.server_cert_pem.read_bytes())
    server_key = serialization.load_pem_private_key(
        material.artifacts.server_key_pem.read_bytes(),
        password=None,
    )

    assert material.artifacts.ca_cert_der.read_bytes() == material.ca_der
    assert material.artifacts.ca_cert_b64.read_text().strip() == material.ca_der_b64
    assert base64.b64decode(material.ca_der_b64) == material.ca_der
    assert ca_cert.subject == server_cert.issuer
    assert server_key is not None
    assert not (tmp_path / "mosquitto-tls.conf").exists()
    assert material.artifacts.server_key_pem.stat().st_mode & 0o777 == 0o600


def test_generated_certs_are_valid_at_camera_epoch_2000_01_01(tmp_path: Path) -> None:
    material = generate_tls_material(
        tmp_path,
        TlsRequest(common_name="10.42.0.1", ip_addresses=("10.42.0.1",)),
        BrokerTarget(host="10.42.0.1", port=8883),
    )

    ca_cert = x509.load_pem_x509_certificate(material.artifacts.ca_cert_pem.read_bytes())
    server_cert = x509.load_pem_x509_certificate(material.artifacts.server_cert_pem.read_bytes())

    for cert in (ca_cert, server_cert):
        assert cert.not_valid_before_utc <= CAMERA_EPOCH
        assert cert.not_valid_after_utc > CAMERA_EPOCH

    san = server_cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert x509.DNSName("10.42.0.1") in san
    assert x509.IPAddress(ipaddress.ip_address("10.42.0.1")) in san

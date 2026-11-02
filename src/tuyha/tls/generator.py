import base64
import ipaddress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from tuyha.contracts.artifacts import TlsArtifactSet
from tuyha.contracts.inputs import BrokerTarget, TlsRequest

CA_CERT_PEM = "ca.crt"
CA_CERT_DER = "ca.der"
CA_CERT_B64 = "tls_ca0.b64"
SERVER_CERT_PEM = "server.crt"
SERVER_KEY_PEM = "server.key"
# anyka_ipc clock starts at 2000-01-01; mbedTLS rejects not-yet-valid certs.
CERT_NOT_BEFORE = datetime(1999, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class TlsMaterial:
    artifacts: TlsArtifactSet
    ca_der: bytes
    ca_der_b64: str
    server_cert_der_b64: str


def generate_tls_material(
    output_dir: Path,
    request: TlsRequest,
    broker: BrokerTarget,
) -> TlsMaterial:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = tls_paths(output_dir)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    ca_cert = _build_ca_cert(ca_key, now, request.validity_days)
    server_cert = _build_server_cert(ca_cert, ca_key, server_key, request, broker, now)
    ca_der = ca_cert.public_bytes(serialization.Encoding.DER)
    ca_der_b64 = base64.b64encode(ca_der).decode("ascii")
    server_der_b64 = base64.b64encode(
        server_cert.public_bytes(serialization.Encoding.DER)
    ).decode("ascii")

    paths.ca_cert_pem.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    paths.ca_cert_der.write_bytes(ca_der)
    paths.ca_cert_b64.write_text(ca_der_b64 + "\n")
    paths.server_cert_pem.write_bytes(server_cert.public_bytes(serialization.Encoding.PEM))
    paths.server_key_pem.write_bytes(
        server_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    paths.server_key_pem.chmod(0o600)
    return TlsMaterial(paths, ca_der, ca_der_b64, server_der_b64)


def tls_paths(output_dir: Path) -> TlsArtifactSet:
    return TlsArtifactSet(
        ca_cert_pem=output_dir / CA_CERT_PEM,
        ca_cert_der=output_dir / CA_CERT_DER,
        ca_cert_b64=output_dir / CA_CERT_B64,
        server_cert_pem=output_dir / SERVER_CERT_PEM,
        server_key_pem=output_dir / SERVER_KEY_PEM,
    )


def _build_ca_cert(
    ca_key: rsa.RSAPrivateKey,
    now: datetime,
    validity_days: int,
) -> x509.Certificate:
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Local Tuya MQTT CA")]
    )
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(CERT_NOT_BEFORE)
        .not_valid_after(now + timedelta(days=validity_days))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(_ca_key_usage(), critical=True)
        .sign(ca_key, hashes.SHA256())
    )


def _build_server_cert(
    ca_cert: x509.Certificate,
    ca_key: rsa.RSAPrivateKey,
    server_key: rsa.RSAPrivateKey,
    request: TlsRequest,
    broker: BrokerTarget,
    now: datetime,
) -> x509.Certificate:
    common_name = request.common_name or broker.host
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(CERT_NOT_BEFORE)
        .not_valid_after(now + timedelta(days=request.validity_days))
        .add_extension(x509.SubjectAlternativeName(_subject_alt_names(request, broker)), False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(_server_key_usage(), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False)
        .sign(ca_key, hashes.SHA256())
    )


def _subject_alt_names(request: TlsRequest, broker: BrokerTarget) -> list[x509.GeneralName]:
    dns_names = set(request.dns_names)
    ip_addresses = set(request.ip_addresses)
    try:
        ip_addresses.add(str(ipaddress.ip_address(broker.host)))
        # Anyka mbedtls hostname checks dNSName/CN strings, not iPAddress SANs.
        # An IP-only SAN yields BADCERT_CN_MISMATCH (verify flag 4/12).
        dns_names.add(broker.host)
    except ValueError:
        dns_names.add(broker.host)
    names: list[x509.GeneralName] = [x509.DNSName(name) for name in sorted(dns_names)]
    names.extend(x509.IPAddress(ipaddress.ip_address(addr)) for addr in sorted(ip_addresses))
    return names


def _ca_key_usage() -> x509.KeyUsage:
    return x509.KeyUsage(
        digital_signature=True,
        content_commitment=False,
        key_encipherment=False,
        data_encipherment=False,
        key_agreement=False,
        key_cert_sign=True,
        crl_sign=True,
        encipher_only=False,
        decipher_only=False,
    )


def _server_key_usage() -> x509.KeyUsage:
    return x509.KeyUsage(
        digital_signature=True,
        content_commitment=False,
        key_encipherment=True,
        data_encipherment=False,
        key_agreement=False,
        key_cert_sign=False,
        crl_sign=False,
        encipher_only=False,
        decipher_only=False,
    )

from dataclasses import dataclass
from pathlib import Path


class InputError(ValueError):
    """An actionable error containing only a developer-controlled message."""


@dataclass(frozen=True)
class WifiInput:
    ssid: str
    password: str
    region: str = "EU"


@dataclass(frozen=True)
class BrokerTarget:
    host: str
    port: int = 8883
    username: str | None = None
    password: str | None = None
    tls_mode: str = "ca"


@dataclass(frozen=True)
class TlsRequest:
    common_name: str | None = None
    dns_names: tuple[str, ...] = ()
    ip_addresses: tuple[str, ...] = ()
    validity_days: int = 36500
    include_rcs_cert_b64: bool = True
    include_gw_ai_ca_arr: bool = True


@dataclass(frozen=True)
class GeneratedIdentity:
    uuid: str | None = None
    auth_key: str | None = None
    device_id: str | None = None
    psk_key: str | None = None
    product_key: str | None = None
    schema_id: str | None = None
    lan_key: str | None = None
    lan_local_key: str | None = None
    tuya_seed: bytes | None = None
    enckey: bytes | None = None


@dataclass(frozen=True)
class ArtifactRequest:
    wifi: WifiInput
    broker_target: BrokerTarget
    output_dir: Path
    identity: GeneratedIdentity = GeneratedIdentity()
    records: dict[str, bytes] | None = None
    rcs_host: str | None = None
    tls_ca_pem: bytes | None = None
    tls: TlsRequest = TlsRequest()

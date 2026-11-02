from dataclasses import dataclass
from pathlib import Path

SD_USER_DB_TARGET = "sd_card/custom/state/tuya_user.hacked.db"
SD_ENCKEY_TARGET = "sd_card/custom/state/tuya_enckey.hacked.db"
SD_UUID_INI_TARGET = "sd_card/custom/state/_ht_uuid.ini"
SD_SERVER_CERT_TARGET = "sd_card/custom/state/mqtt/server.crt"
SD_SERVER_KEY_TARGET = "sd_card/custom/state/mqtt/server.key"


@dataclass(frozen=True)
class TlsArtifactSet:
    ca_cert_pem: Path
    ca_cert_der: Path
    ca_cert_b64: Path
    server_cert_pem: Path
    server_key_pem: Path


@dataclass(frozen=True)
class ArtifactSet:
    user_db: Path
    enckey_db: Path
    manifest: Path
    uuid_ini: Path | None = None
    tls: TlsArtifactSet | None = None

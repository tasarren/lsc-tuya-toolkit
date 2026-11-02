import json
from pathlib import Path

from tuyha.contracts.artifacts import ArtifactSet
from tuyha.contracts.artifacts import (
    SD_ENCKEY_TARGET, SD_SERVER_CERT_TARGET, SD_SERVER_KEY_TARGET, SD_USER_DB_TARGET, SD_UUID_INI_TARGET,
)
from tuyha.contracts.inputs import ArtifactRequest, GeneratedIdentity
from tuyha.tls import TlsMaterial


def write_manifest(
    path: Path,
    request: ArtifactRequest,
    artifacts: ArtifactSet,
    identity: GeneratedIdentity,
    record_names: tuple[str, ...],
    tls_material: TlsMaterial,
) -> None:
    manifest = {
        "source_kind": "json" if request.records is not None else "scratch",
        "files": {
            "user_db": str(artifacts.user_db),
            "enckey_db": str(artifacts.enckey_db),
            "uuid_ini": str(artifacts.uuid_ini) if artifacts.uuid_ini is not None else "",
        },
        "tls_files": _tls_file_manifest(artifacts),
        "sd_copy_targets": {
            "user_db": SD_USER_DB_TARGET,
            "enckey_db": SD_ENCKEY_TARGET,
            "uuid_ini": SD_UUID_INI_TARGET,
            "server_cert_pem": SD_SERVER_CERT_TARGET,
            "server_key_pem": SD_SERVER_KEY_TARGET,
        },
        "record_names": sorted(record_names),
        "identity_lengths": {
            "uuid": len(identity.uuid or ""),
            "auth_key": len(identity.auth_key or ""),
            "device_id": len(identity.device_id or ""),
            "tuya_seed": len(identity.tuya_seed or b""),
            "enckey": len(identity.enckey or b""),
        },
        "trust_mapping": {
            "tls_ca_cnt": 1,
            "tls_ca0_sha256": _sha256_hex(tls_material.ca_der),
            "tls_ca0_base64_length": len(tls_material.ca_der_b64),
            "rcs_active_cert_b64": request.tls.include_rcs_cert_b64,
            "gw_ai_caArr": request.tls.include_gw_ai_ca_arr,
            "hardware_sensitive": True,
            "note": "Local trust-record assertions are not hardware boot proof.",
        },
    }
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def _tls_file_manifest(artifacts: ArtifactSet) -> dict[str, str | bool]:
    if artifacts.tls is None:
        return {}
    return {
        "ca_cert_pem": str(artifacts.tls.ca_cert_pem),
        "ca_cert_der": str(artifacts.tls.ca_cert_der),
        "ca_cert_b64": str(artifacts.tls.ca_cert_b64),
        "server_cert_pem": str(artifacts.tls.server_cert_pem),
        "server_key_pem": str(artifacts.tls.server_key_pem),
        "server_key_pem_private": True,
    }


def _sha256_hex(value: bytes) -> str:
    import hashlib

    return hashlib.sha256(value).hexdigest()

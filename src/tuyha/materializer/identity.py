import secrets
import string

from tuyha.contracts.inputs import GeneratedIdentity

ALPHABET = string.ascii_letters + string.digits


def _rand_alnum(length: int) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def validate_uuid(value: str) -> None:
    if len(value) not in {20, 43}:
        raise ValueError("uuid must be exactly 20 or 43 characters")


def validate_auth_key(value: str) -> None:
    if len(value) != 32:
        raise ValueError("auth_key must be exactly 32 characters")


def validate_device_id(value: str) -> None:
    if len(value) < 8 or len(value) > 16:
        raise ValueError("device_id must be 8 through 16 characters")


def resolved_identity(overrides: GeneratedIdentity) -> GeneratedIdentity:
    for value in vars(overrides).values():
        if value == "" or value == b"":
            raise ValueError("identity overrides must not be empty")
    uuid = overrides.uuid or _rand_alnum(20)
    auth_key = overrides.auth_key or _rand_alnum(32)
    device_id = overrides.device_id or _rand_alnum(12)
    validate_uuid(uuid)
    validate_auth_key(auth_key)
    validate_device_id(device_id)
    identity = GeneratedIdentity(
        uuid=uuid,
        auth_key=auth_key,
        device_id=device_id,
        psk_key=overrides.psk_key or _rand_alnum(16),
        product_key=overrides.product_key or "tuyhaLocalPk",
        schema_id=overrides.schema_id or "tuyhaLocalSchema",
        lan_key=overrides.lan_key or _rand_alnum(16),
        lan_local_key=overrides.lan_local_key or _rand_alnum(16),
        tuya_seed=overrides.tuya_seed or secrets.token_bytes(64),
        enckey=overrides.enckey or secrets.token_bytes(16),
    )
    for value in (identity.uuid, identity.auth_key, identity.device_id, identity.product_key,
                  identity.schema_id, identity.psk_key, identity.lan_key, identity.lan_local_key):
        if not isinstance(value, str) or not value.isascii() or not value.isprintable() or not value:
            raise ValueError("identity fields must contain printable ASCII")
    if not 8 <= len(identity.product_key) <= 16:
        raise ValueError("product_key must be 8 through 16 characters")
    if len(identity.schema_id) > 32:
        raise ValueError("schema_id must be at most 32 bytes")
    if len(identity.tuya_seed) != 64 or len(identity.enckey) != 16:
        raise ValueError("tuya_seed must be 64 bytes and enckey must be 16 bytes")
    return identity

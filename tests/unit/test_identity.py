import pytest

from tuyha.contracts.inputs import GeneratedIdentity
from tuyha.materializer.identity import resolved_identity
from tuyha.materializer.identity import validate_auth_key, validate_device_id, validate_uuid


def test_generated_identity_satisfies_firmware_lengths() -> None:
    identity = resolved_identity(GeneratedIdentity())

    assert len(identity.uuid or "") in {20, 43}
    assert len(identity.auth_key or "") == 32
    assert 8 <= len(identity.device_id or "") <= 16
    assert len(identity.tuya_seed or b"") == 64
    assert len(identity.enckey or b"") == 16


def test_identity_overrides_replace_generated_defaults() -> None:
    seed = b"s" * 64
    enckey = bytes(range(16))
    identity = resolved_identity(
        GeneratedIdentity(
            uuid="u" * 43,
            auth_key="a" * 32,
            device_id="device123",
            tuya_seed=seed,
            enckey=enckey,
        )
    )

    assert identity.uuid == "u" * 43
    assert identity.auth_key == "a" * 32
    assert identity.device_id == "device123"
    assert identity.tuya_seed == seed
    assert identity.enckey == enckey


@pytest.mark.parametrize("value", ["short", "x" * 21, "x" * 42])
def test_uuid_validator_rejects_unsupported_lengths(value: str) -> None:
    with pytest.raises(ValueError, match="uuid"):
        validate_uuid(value)


def test_auth_key_validator_rejects_non_32_length() -> None:
    with pytest.raises(ValueError, match="auth_key"):
        validate_auth_key("a" * 31)


def test_device_id_validator_rejects_out_of_range_lengths() -> None:
    with pytest.raises(ValueError, match="device_id"):
        validate_device_id("d" * 7)

import base64
import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from hashlib import md5

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from tuyha.anyka.db import KVMap, load_kv
from tuyha.anyka.rcs import RcsActive, encode_rcs_active
from tuyha.anyka.verify import verify_kv
from tuyha.contracts.inputs import ArtifactRequest, BrokerTarget, GeneratedIdentity, WifiInput

SCHEMA_ID = "schema077"
IDENTITY = GeneratedIdentity(
    uuid="u" * 20, auth_key="z" * 32, device_id="dev12345", enckey=bytes(range(16))
)


def _json(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


@lru_cache(maxsize=4)
def _ca_der_b64(common_name: str = "Lab CA") -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    return base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode("ascii")


def _scratch_kv(
    *, rcs_host: str = "127.0.0.1:8883", include_rcs_cert: bool = True, broker: str = "127.0.0.1:8883"
) -> KVMap:
    ca_b64 = _ca_der_b64()
    return {
        "gw_ai": _json({
            "key": "lankey01", "lckey": "localkey01", "h_url": "127.0.0.1", "hs_url": "127.0.0.1",
            "hs_psk": "127.0.0.1", "mq_url": broker, "mqs_url": broker, "mq_psk": broker,
            "lp_url": "127.0.0.1:443", "time_z": "+00:00", "s_time_z": "[]", "cloud_cap": 1,
            "dy_tls_m": 0, "caArr": [ca_b64],
        }),
        "gw_wsm": _json({
            "ssid": base64.b64encode(b"LabNet").decode("ascii"),
            "passwd": base64.b64encode(b"LabPass").decode("ascii"),
            "wfb64": 1, "nc_tp": 9, "md": 3, "stat": 2, "token": "tuyhatok", "region": "US",
            "reg_key": "tuyh", "dns_prio": 0, "is_psk30_cfg": True, "is_auto_recover": True,
            "is_auto_connect": True,
        }),
        "gw_bi": _json({"uuid": "u" * 20, "auth_key": "a" * 32, "psk_key": "p" * 32}),
        "gw_di": _json({"id": "dev12345", "pk": "tuyhaLocalPk", "s_id": SCHEMA_ID, "lpv": "3.5"}),
        SCHEMA_ID: b"[]",
        "rcs.active": encode_rcs_active(
            RcsActive(
                code="US-PROD",
                url0=rcs_host,
                url1=rcs_host,
                cert_b64=_ca_der_b64() if include_rcs_cert else None,
            )
        ),
        "tuya_seed": bytes(range(64)),
        "tls_ca_cnt": b"1\x00",
        "tls_ca0": ca_b64.encode("ascii") + b"\x00",
        "wf_start_md": b"2\x00",
        "p2p_type": b"4\x00",
        "p2p_auth_info": _json({"p2pId": "", "type": 4}) + b"\x00",
        "p2p_pwd": b"tuyhap2p\x00",
    }


def _patched(kv: KVMap, **changes: bytes | None) -> KVMap:
    updated = dict(kv)
    for name, value in changes.items():
        if value is None:
            updated.pop(name, None)
        else:
            updated[name] = value
    return updated


def _patch_json(kv: KVMap, name: str, **fields: object) -> KVMap:
    data = json.loads(kv[name])
    data.update(fields)
    return _patched(kv, **{name: json.dumps(data, separators=(",", ":")).encode("utf-8")})


def test_generated_scratch_set_passes_every_check() -> None:
    kv = _scratch_kv()

    assert verify_kv(kv, scratch=True) == ()
    assert verify_kv(kv) == ()


def test_distinct_rcs_host_is_accepted() -> None:
    kv = _scratch_kv(rcs_host="rcs.example.net:443")

    assert verify_kv(kv, scratch=True) == ()


def test_rcs_certificate_is_optional() -> None:
    kv = _scratch_kv(include_rcs_cert=False)

    assert verify_kv(kv, scratch=True) == ()


def test_unknown_record_bytes_are_ignored() -> None:
    kv = _patched(_scratch_kv(), **{"vendor.blob": b"\x00\xff\x10"})

    assert verify_kv(kv, scratch=True) == ()


def test_inactive_factory_shape_passes_general_checks() -> None:
    kv = _patched(
        _scratch_kv(),
        gw_wsm=json.dumps(
            {"ssid": "", "passwd": "", "wfb64": 1, "nc_tp": 2, "stat": 1, "ap_info_v3": {"k": 1}},
            separators=(",", ":"),
        ).encode("utf-8"),
        **{"rcs.active": b"\x00", "tls_ca_cnt": b"0\x00", "tls_ca0": None, "p2p_type": None},
    )

    assert verify_kv(kv) == ()
    assert verify_kv(kv, scratch=True) != ()


def test_scratch_reports_activated_fields() -> None:
    kv = _patch_json(_scratch_kv(), "gw_wsm", stat=3, nc_tp=2, is_auto_connect=False)

    failures = verify_kv(kv, scratch=True)

    assert "gw_wsm.stat is not the activated value" in failures
    assert "gw_wsm.nc_tp is not the activated value" in failures
    assert "gw_wsm.is_auto_connect is not enabled" in failures


def test_scratch_rejects_fast_connect_blob() -> None:
    kv = _patch_json(_scratch_kv(), "gw_wsm", ap_info_v3={"ssid": "x"})

    assert "gw_wsm.ap_info_v3 must stay absent so the station join is not skipped" in verify_kv(kv, scratch=True)


def test_missing_rcs_activation_is_scratch_only() -> None:
    kv = _patched(_scratch_kv(), **{"rcs.active": b"\x00"})

    assert "rcs.active is inactive" not in verify_kv(kv)
    assert verify_kv(kv, scratch=True) != ()


def test_tls_ca_nul_termination_is_scratch_only() -> None:
    kv = _scratch_kv()
    ca = kv["tls_ca0"]
    kv = _patched(kv, tls_ca0=ca[:-1])

    assert verify_kv(kv) == ()
    assert "a tls_ca record is not NUL-terminated" in verify_kv(kv, scratch=True)


def test_ca_count_must_match_stored_records() -> None:
    kv = _patched(_scratch_kv(), tls_ca_cnt=b"2\x00")

    assert "tls_ca_cnt does not match the stored CA certificate records" in verify_kv(kv)


def test_schema_record_must_be_an_empty_array() -> None:
    kv = _scratch_kv()
    schema_id = json.loads(kv["gw_di"])["s_id"]
    kv = _patched(kv, **{schema_id: b"{}"})

    assert "the schema id record is not an empty JSON array" in verify_kv(kv, scratch=True)


def test_p2p_marker_and_nul_shapes() -> None:
    kv = _patched(_scratch_kv(), p2p_type=b"9\x00", p2p_pwd=b"tuyhap2p")

    failures = verify_kv(kv, scratch=True)

    assert "p2p_type is not the P2P auth-skip marker" in failures
    assert "p2p_pwd is not eight ASCII bytes followed by NUL" in failures


def test_md5_record_must_match_its_key() -> None:
    kv = {"md5_encrypt_key": json.dumps(
        {"md5_value": "AAAA", "md5_len": 32, "encrypt_key_value": "c29tZWtleQ=="},
        separators=(",", ":"),
    ).encode("utf-8")}

    failures = verify_kv(kv)

    assert "md5_encrypt_key.md5_value does not match its key" in failures


def test_md5_record_with_broken_base64_is_reported() -> None:
    kv = {"md5_encrypt_key": json.dumps(
        {"md5_value": "!!!", "md5_len": 32, "encrypt_key_value": "c29tZWtleQ=="},
        separators=(",", ":"),
    ).encode("utf-8")}

    assert "md5_encrypt_key values are not base64" in verify_kv(kv)


def test_md5_mismatch_is_reported() -> None:
    digest = base64.b64encode(md5(b"expected").hexdigest().encode("ascii")).decode("ascii")
    key_b64 = base64.b64encode(b"different").decode("ascii")
    kv = {"md5_encrypt_key": json.dumps(
        {"md5_value": digest, "md5_len": 32, "encrypt_key_value": key_b64}, separators=(",", ":")
    ).encode("utf-8")}

    assert "md5_encrypt_key.md5_value does not match its key" in verify_kv(kv)


def test_local_log_level_range_is_checked() -> None:
    kv = {"localLogLevel": (9).to_bytes(4, "little") + (1).to_bytes(4, "little")}

    assert "localLogLevel level is outside 0-5" in verify_kv(kv)


def test_ca_array_entry_must_be_a_certificate() -> None:
    kv = _patch_json(_scratch_kv(), "gw_ai", caArr=["bm90IGEgY2VydA=="])

    assert "gw_ai.caArr holds an entry that is not a DER certificate" in verify_kv(kv)


def test_failures_never_echo_record_values() -> None:
    kv = _patch_json(_scratch_kv(), "gw_ai", mq_url=12345)

    failures = verify_kv(kv, scratch=True)

    assert any("gw_ai.mq_url" in failure for failure in failures)
    assert all("12345" not in failure for failure in failures)


def test_garbage_database_fails_structurally() -> None:
    from tuyha.anyka.db import load_kv_bytes

    try:
        load_kv_bytes(b"not a kv file", bytes(16))
    except ValueError as exc:
        assert "smaller than its fixed header" in str(exc)
    else:
        raise AssertionError("truncated database was accepted")


def test_non_hex_generated_auth_key_is_accepted() -> None:
    kv = _patch_json(_scratch_kv(), "gw_bi", auth_key="z" * 32)

    assert verify_kv(kv, scratch=True) == ()


def test_inactive_identity_shape_passes_general_checks() -> None:
    kv = _patch_json(_scratch_kv(), "gw_bi", uuid="", auth_key="")

    assert verify_kv(kv) == ()


def test_scratch_requires_identity_fields() -> None:
    kv = _patch_json(_scratch_kv(), "gw_bi", uuid="short")
    kv = _patch_json(kv, "gw_di", id="short")

    failures = verify_kv(kv, scratch=True)

    assert "gw_bi.uuid is not a generated identifier" in failures
    assert "gw_di.id is not a device identifier" in failures


def test_scratch_requires_p2p_auth_shape() -> None:
    kv = _patched(
        _scratch_kv(),
        p2p_auth_info=_json({"p2pId": "abc", "type": 5}) + b"\x00",
        p2p_pwd=b"tuyhap2p\x00",
    )

    failures = verify_kv(kv, scratch=True)

    assert "p2p_auth_info type is not the P2P auth value" in failures
    assert "p2p_auth_info p2pId is not empty" in failures


def test_top_level_ap_info_v3_is_rejected_in_scratch() -> None:
    kv = _patched(_scratch_kv(), ap_info_v3=_json({"ssid": "x"}))

    assert "ap_info_v3 must stay absent so the station join is not skipped" in verify_kv(kv, scratch=True)


def test_generated_materializer_output_passes_verification(tmp_path: Path) -> None:
    from tuyha.materializer.workflow import materialize_artifacts

    request = ArtifactRequest(
        wifi=WifiInput(ssid="LabNet", password="LabPass", region="US"),
        broker_target=BrokerTarget(host="127.0.0.1", port=8883),
        output_dir=tmp_path,
        identity=IDENTITY,
    )
    artifacts = materialize_artifacts(request)
    kv = load_kv(artifacts.user_db, artifacts.enckey_db)

    assert verify_kv(kv, scratch=True) == ()


def test_any_eight_ascii_p2p_password_is_accepted() -> None:
    kv = _patched(_scratch_kv(), p2p_pwd=b"abcd1234\x00")

    assert verify_kv(kv, scratch=True) == ()


def test_ca_indices_must_start_at_zero() -> None:
    kv = _scratch_kv()
    kv = _patched(kv, **{"tls_ca1": kv["tls_ca0"], "tls_ca0": None})

    assert "CA certificate record indices are not contiguous from tls_ca0" in verify_kv(kv)


def test_ca_array_must_carry_stored_certificates() -> None:
    kv = _scratch_kv()
    other = _ca_der_b64("Other CA")
    kv = _patch_json(kv, "gw_ai", caArr=[other])

    assert "gw_ai.caArr does not carry every stored CA certificate" in verify_kv(kv, scratch=True)


def test_p2p_password_with_internal_nul_is_rejected() -> None:
    kv = _patched(_scratch_kv(), p2p_pwd=b"tuy\x00ha2p\x00")

    assert "p2p_pwd is not eight ASCII bytes followed by NUL" in verify_kv(kv, scratch=True)


def test_non_string_identity_fields_are_rejected() -> None:
    kv = _patched(_scratch_kv(), gw_bi=_json({"uuid": 123, "auth_key": 456, "psk_key": 789}))

    failures = verify_kv(kv)

    assert "gw_bi.uuid is not a string" in failures
    assert "gw_bi.auth_key is not a string" in failures


def test_decoded_wifi_field_limits_are_enforced() -> None:
    long_ssid = base64.b64encode(b"s" * 33).decode("ascii")
    long_password = base64.b64encode(b"p" * 65).decode("ascii")
    kv = _patch_json(_scratch_kv(), "gw_wsm", ssid=long_ssid, passwd=long_password)

    failures = verify_kv(kv)

    assert "gw_wsm.ssid decodes to more than 32 bytes" in failures
    assert "gw_wsm.passwd decodes to more than 64 bytes" in failures


def test_decoded_wifi_nul_is_rejected() -> None:
    kv = _patch_json(_scratch_kv(), "gw_wsm", ssid=base64.b64encode(b"lab\x00net").decode("ascii"))

    assert "gw_wsm.ssid decodes to a value containing NUL" in verify_kv(kv)


def test_inactive_empty_wifi_fields_pass_general_checks() -> None:
    kv = _patch_json(_scratch_kv(), "gw_wsm", ssid="", passwd="")

    assert verify_kv(kv) == ()


def test_integer_fields_reject_bool_values() -> None:
    kv = _patch_json(_scratch_kv(), "gw_wsm", nc_tp=True, is_auto_connect=1)

    failures = verify_kv(kv)

    assert "gw_wsm.nc_tp has the wrong type" in failures
    assert "gw_wsm.is_auto_connect has the wrong type" in failures


def test_inactive_empty_device_fields_pass_general_checks() -> None:
    kv = _patched(_scratch_kv(), gw_di=_json({"id": "", "pk": "", "s_id": ""}))

    assert verify_kv(kv) == ()

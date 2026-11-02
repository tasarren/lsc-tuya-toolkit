"""Format and record semantics checks for an Anyka KV map.

`verify_kv` reports structural damage and known-format violations without
printing record values. It never requires a scratch (activated) shape; pass
`scratch=True` to add the generator's own invariants.
"""

import base64
import binascii
import hashlib
import json

from cryptography import x509

from tuyha.anyka.db import KVMap
from tuyha.anyka.rcs import decode_rcs_active, validate_host_port

GW_WSM_TOKEN_MAX_LEN = 8
GW_WSM_REG_KEY_MAX_LEN = 4
GW_WSM_REGION_MAX_LEN = 2
WIFI_SSID_MAX_LEN = 32
WIFI_PASSWORD_MAX_LEN = 64
LOCAL_LOG_LEVEL_MIN = 0
LOCAL_LOG_LEVEL_MAX = 5
LOCAL_LOG_LEVEL_SIZE = 8
UUID_LENS = (20, 43)
AUTH_KEY_LEN = 32
MD5_LEN = 32


def verify_kv(kv: KVMap, *, scratch: bool = False) -> tuple[str, ...]:
    """Return safe failure descriptions; an empty tuple means every check passed."""
    failures: list[str] = []
    _check_gw_ai(kv, failures)
    _check_gw_wsm(kv, failures)
    _check_gw_bi(kv, failures)
    _check_gw_di(kv, failures)
    _check_rcs(kv, failures)
    _check_trust(kv, failures)
    _check_p2p(kv, failures)
    _check_storage(kv, failures)
    if scratch:
        from tuyha.anyka.scratch_verify import verify_scratch_kv

        failures.extend(verify_scratch_kv(kv))
    return tuple(failures)


def ca_record_names(kv: KVMap) -> list[str]:
    return sorted(name for name in kv if _is_ca_record_name(name))


def _check_gw_ai(kv: KVMap, failures: list[str]) -> None:
    if "gw_ai" not in kv:
        return
    data = _json_object(kv, "gw_ai", failures)
    if data is None:
        return
    for field in ("mq_url", "mqs_url", "mq_psk", "h_url", "hs_url", "hs_psk"):
        if data.get(field) is not None and not isinstance(data[field], str):
            failures.append(f"gw_ai.{field} is not a string")
    if "caArr" in data:
        _check_ca_array(data["caArr"], failures)


def _check_gw_wsm(kv: KVMap, failures: list[str]) -> None:
    if "gw_wsm" not in kv:
        return
    data = _json_object(kv, "gw_wsm", failures)
    if data is None:
        return
    for field in ("wfb64", "nc_tp", "stat", "dns_prio"):
        if field in data and type(data[field]) is not int:
            failures.append(f"gw_wsm.{field} has the wrong type")
    for field in ("ssid", "passwd"):
        if data.get(field) is not None and not isinstance(data[field], str):
            failures.append(f"gw_wsm.{field} is not a string")
    if "is_auto_connect" in data and type(data["is_auto_connect"]) is not bool:
        failures.append("gw_wsm.is_auto_connect has the wrong type")
    for field, limit in (("ssid", WIFI_SSID_MAX_LEN), ("passwd", WIFI_PASSWORD_MAX_LEN)):
        value = data.get(field)
        if not isinstance(value, str) or not value:
            continue
        try:
            decoded = base64.b64decode(value, validate=True) if data.get("wfb64") == 1 else value.encode("utf-8")
        except (binascii.Error, ValueError, UnicodeError):
            tls_note = f"gw_wsm.{field} is not base64 although wfb64 is set"
            failures.append(tls_note)
            continue
        if b"\x00" in decoded:
            failures.append(f"gw_wsm.{field} decodes to a value containing NUL")
        elif len(decoded) > limit:
            failures.append(f"gw_wsm.{field} decodes to more than {limit} bytes")
    _check_max_len(data, "token", GW_WSM_TOKEN_MAX_LEN, failures)
    _check_max_len(data, "reg_key", GW_WSM_REG_KEY_MAX_LEN, failures)
    _check_max_len(data, "region", GW_WSM_REGION_MAX_LEN, failures)
    if "ap_info_v3" in data and not isinstance(data["ap_info_v3"], dict):
        failures.append("gw_wsm.ap_info_v3 is not a JSON object")


def _check_gw_bi(kv: KVMap, failures: list[str]) -> None:
    if "gw_bi" not in kv:
        return
    data = _json_object(kv, "gw_bi", failures)
    if data is None:
        return
    # Null/empty identity fields are inactive state; only a non-empty
    # value can be checked against the length the firmware reads.
    uuid = data.get("uuid")
    if uuid is not None and not isinstance(uuid, str):
        failures.append("gw_bi.uuid is not a string")
    elif isinstance(uuid, str) and uuid and len(uuid) not in UUID_LENS:
        failures.append("gw_bi.uuid has an unsupported length")
    auth_key = data.get("auth_key")
    if auth_key is not None and not isinstance(auth_key, str):
        failures.append("gw_bi.auth_key is not a string")
    elif isinstance(auth_key, str) and auth_key:
        if len(auth_key) != AUTH_KEY_LEN:
            failures.append("gw_bi.auth_key has an unsupported length")
        elif not _is_printable_ascii(auth_key):
            failures.append("gw_bi.auth_key is not printable ASCII")
    if data.get("psk_key") is not None and not isinstance(data["psk_key"], str):
        failures.append("gw_bi.psk_key is not a string")


def _check_gw_di(kv: KVMap, failures: list[str]) -> None:
    if "gw_di" not in kv:
        return
    data = _json_object(kv, "gw_di", failures)
    if data is None:
        return
    for field in ("id", "pk", "s_id"):
        if data.get(field) is not None and not isinstance(data[field], str):
            failures.append(f"gw_di.{field} is not a string")


def _check_rcs(kv: KVMap, failures: list[str]) -> None:
    raw = kv.get("rcs.active")
    if raw is None:
        return
    try:
        active = decode_rcs_active(raw)
    except ValueError:
        failures.append("rcs.active is not a valid TLV blob")
        return
    if active is None:
        return
    if not active.code:
        failures.append("rcs.active.code is empty")
    _require_host_port(active.url0, "rcs.active.url0", failures)
    _require_host_port(active.url1, "rcs.active.url1", failures)
    if active.cert_b64 is not None and not is_der_certificate(active.cert_b64):
        failures.append("rcs.active.cert_b64 is not a DER certificate")


def _check_trust(kv: KVMap, failures: list[str]) -> None:
    ca_names = ca_record_names(kv)
    declared = _int_record(kv.get("tls_ca_cnt"), "tls_ca_cnt", failures)
    if declared is not None and declared != len(ca_names):
        failures.append("tls_ca_cnt does not match the stored CA certificate records")
    contiguous = {f"tls_ca{index}" for index in range(len(ca_names))}
    if set(ca_names) != contiguous:
        failures.append("CA certificate record indices are not contiguous from tls_ca0")
    for name in ca_names:
        raw = kv[name]
        body = raw[:-1] if raw.endswith(b"\x00") else raw
        if not is_der_certificate(body.decode("ascii", errors="replace")):
            failures.append("a tls_ca record is not a DER certificate")


def _check_p2p(kv: KVMap, failures: list[str]) -> None:
    p2p_type = kv.get("p2p_type")
    if p2p_type is not None:
        _int_record(p2p_type, "p2p_type", failures)
    if kv.get("p2p_auth_info") is not None:
        _json_object(kv, "p2p_auth_info", failures)
    wf_start_md = kv.get("wf_start_md")
    if wf_start_md is not None:
        _int_record(wf_start_md, "wf_start_md", failures)


def _check_storage(kv: KVMap, failures: list[str]) -> None:
    log_level = kv.get("localLogLevel")
    if log_level is not None:
        if len(log_level) != LOCAL_LOG_LEVEL_SIZE:
            failures.append("localLogLevel is not two 32-bit words")
        else:
            level = int.from_bytes(log_level[:4], "little")
            if not LOCAL_LOG_LEVEL_MIN <= level <= LOCAL_LOG_LEVEL_MAX:
                failures.append("localLogLevel level is outside 0-5")
    if "md5_encrypt_key" in kv:
        md5_record = _json_object(kv, "md5_encrypt_key", failures)
    else:
        md5_record = None
    if md5_record is not None:
        _check_md5_record(md5_record, failures)


def _check_md5_record(data: dict[str, object], failures: list[str]) -> None:
    md5_value = data.get("md5_value")
    key_value = data.get("encrypt_key_value")
    if not isinstance(md5_value, str) or not isinstance(key_value, str):
        failures.append("md5_encrypt_key fields are not strings")
        return
    if data.get("md5_len") is not None and data["md5_len"] != MD5_LEN:
        failures.append("md5_encrypt_key.md5_len is not 32")
    try:
        key_bytes = base64.b64decode(key_value, validate=True)
        stored = base64.b64decode(md5_value, validate=True).decode("ascii")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        failures.append("md5_encrypt_key values are not base64")
        return
    if data.get("encrypt_key_len") is not None and data["encrypt_key_len"] != len(key_bytes):
        failures.append("md5_encrypt_key.encrypt_key_len does not match its key")
    if stored != hashlib.md5(key_bytes).hexdigest():
        failures.append("md5_encrypt_key.md5_value does not match its key")


def _check_ca_array(value: object, failures: list[str]) -> None:
    if not isinstance(value, list) or not value:
        failures.append("gw_ai.caArr is not a non-empty list")
        return
    for entry in value:
        if not isinstance(entry, str) or not is_der_certificate(entry):
            failures.append("gw_ai.caArr holds an entry that is not a DER certificate")
            return


def is_der_certificate(text: str) -> bool:
    try:
        x509.load_der_x509_certificate(base64.b64decode(text, validate=True))
    except (binascii.Error, ValueError):
        return False
    return True


def _json_object(kv: KVMap, name: str, failures: list[str]) -> dict[str, object] | None:
    raw = kv.get(name)
    if raw is None:
        failures.append(f"{name} is missing")
        return None
    try:
        value = json.loads(raw.rstrip(b"\x00").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        failures.append(f"{name} is not valid JSON")
        return None
    if not isinstance(value, dict):
        failures.append(f"{name} is not a JSON object")
        return None
    return value


def _int_record(raw: bytes | None, name: str, failures: list[str]) -> int | None:
    if raw is None:
        return None
    body = raw[:-1] if raw.endswith(b"\x00") else raw
    if not body.isdigit():
        failures.append(f"{name} is not a decimal value")
        return None
    return int(body)


def _check_max_len(data: dict[str, object], field: str, limit: int, failures: list[str]) -> None:
    value = data.get(field)
    if value is None:
        return
    if not isinstance(value, str) or len(value) > limit:
        failures.append(f"gw_wsm.{field} is longer than {limit} characters")


def _require_host_port(value: str, label: str, failures: list[str]) -> None:
    try:
        validate_host_port(value, label)
    except ValueError:
        failures.append(f"{label} is not host[:port]")


def _is_ca_record_name(name: str) -> bool:
    return name.startswith("tls_ca") and name[len("tls_ca") :].isdigit()


def _non_empty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _is_printable_ascii(text: str) -> bool:
    return text.isascii() and text.isprintable()

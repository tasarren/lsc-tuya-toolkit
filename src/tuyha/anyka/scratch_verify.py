"""Scratch-generation invariants for a generated Anyka KV map.

These checks only describe the artifact set TuyHA generates. They must not be
applied to a camera's own database: a factory or user-modified DB legitimately
has an inactive Wi-Fi state, extra records, and no RCS activation.
"""

from tuyha.anyka.db import KVMap
from tuyha.anyka.rcs import decode_rcs_active
from tuyha.anyka.verify import (
    _int_record,
    _json_object,
    _non_empty_text,
    _require_host_port,
    ca_record_names,
)

SCRATCH_NC_TP = 9
SCRATCH_STAT = 2
SCRATCH_P2P_TYPE = b"4\x00"
SCRATCH_WF_START_MD = b"2\x00"
SCRATCH_SCHEMA_VALUE = b"[]"
SCRATCH_SEED_SIZE = 64
SCRATCH_P2P_AUTH_TYPE = 4
SCRATCH_P2P_PWD_LEN = 8
DEVICE_ID_MIN, DEVICE_ID_MAX = 8, 16
PRODUCT_KEY_MIN, PRODUCT_KEY_MAX = 8, 16
SCHEMA_ID_MAX = 32
UUID_LENS = (20, 43)
AUTH_KEY_LEN = 32
SCRATCH_CA_COUNT = 1
REQUIRED_SCRATCH_RECORDS = (
    "gw_ai",
    "gw_wsm",
    "gw_bi",
    "gw_di",
    "rcs.active",
    "tuya_seed",
    "tls_ca_cnt",
    "tls_ca0",
    "wf_start_md",
    "p2p_type",
    "p2p_auth_info",
    "p2p_pwd",
)


def verify_scratch_kv(kv: KVMap) -> tuple[str, ...]:
    failures = [f"{name} is missing from the scratch record set"
                for name in REQUIRED_SCRATCH_RECORDS if name not in kv]
    _check_gw_ai(kv, failures)
    _check_gw_wsm(kv, failures)
    _check_rcs(kv, failures)
    _check_identity(kv, failures)
    _check_schema_link(kv, failures)
    if "ap_info_v3" in kv:
        failures.append("ap_info_v3 must stay absent so the station join is not skipped")
    _check_ca_array(kv, failures)
    _check_trust(kv, failures)
    _check_p2p(kv, failures)
    return tuple(failures)


def _check_gw_ai(kv: KVMap, failures: list[str]) -> None:
    if "gw_ai" not in kv:
        return
    data = _json_object(kv, "gw_ai", failures)
    if data is None:
        return
    endpoints: list[str] = []
    for field in ("mq_url", "mqs_url", "mq_psk"):
        value = data.get(field)
        if not _non_empty_text(value):
            failures.append(f"gw_ai.{field} is not a non-empty string")
            continue
        _require_host_port(value, f"gw_ai.{field}", failures)
        endpoints.append(value)
    if len(set(endpoints)) > 1:
        failures.append("gw_ai MQTT endpoints disagree")
    for field in ("key", "lckey"):
        if not _non_empty_text(data.get(field)):
            failures.append(f"gw_ai.{field} is not a non-empty LAN key")


def _check_gw_wsm(kv: KVMap, failures: list[str]) -> None:
    if "gw_wsm" not in kv:
        return
    data = _json_object(kv, "gw_wsm", failures)
    if data is None:
        return
    for field in ("ssid", "passwd", "token", "reg_key", "region"):
        if not _non_empty_text(data.get(field)):
            failures.append(f"gw_wsm.{field} is not a non-empty string")
    _require_equals(data, "nc_tp", SCRATCH_NC_TP, failures)
    _require_equals(data, "stat", SCRATCH_STAT, failures)
    _require_equals(data, "wfb64", 1, failures)
    _require_equals(data, "is_auto_connect", True, failures, label="is not enabled")
    if "ap_info_v3" in data:
        failures.append("gw_wsm.ap_info_v3 must stay absent so the station join is not skipped")


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
        failures.append("rcs.active is inactive")


def _check_identity(kv: KVMap, failures: list[str]) -> None:
    bi = _json_object(kv, "gw_bi", failures)
    if bi is not None:
        uuid = bi.get("uuid")
        if not _non_empty_text(uuid) or len(uuid) not in UUID_LENS:
            failures.append("gw_bi.uuid is not a generated identifier")
        auth_key = bi.get("auth_key")
        if not _non_empty_text(auth_key) or len(auth_key) != AUTH_KEY_LEN:
            failures.append("gw_bi.auth_key is not a generated key")
        elif not (auth_key.isascii() and auth_key.isprintable()):
            failures.append("gw_bi.auth_key is not printable ASCII")
        if not _non_empty_text(bi.get("psk_key")):
            failures.append("gw_bi.psk_key is not a generated key")
    di = _json_object(kv, "gw_di", failures)
    if di is not None:
        device_id = di.get("id")
        if not isinstance(device_id, str) or not DEVICE_ID_MIN <= len(device_id) <= DEVICE_ID_MAX:
            failures.append("gw_di.id is not a device identifier")
        product_key = di.get("pk")
        if not isinstance(product_key, str) or not PRODUCT_KEY_MIN <= len(product_key) <= PRODUCT_KEY_MAX:
            failures.append("gw_di.pk is not a product key")
        schema_id = di.get("s_id")
        if not _non_empty_text(schema_id) or len(schema_id) > SCHEMA_ID_MAX:
            failures.append("gw_di.s_id is not a schema id")
    seed = kv.get("tuya_seed")
    if seed is not None and len(seed) != SCRATCH_SEED_SIZE:
        failures.append("tuya_seed is not 64 bytes")


def _check_schema_link(kv: KVMap, failures: list[str]) -> None:
    if "gw_di" not in kv:
        return
    data = _json_object(kv, "gw_di", failures)
    if data is None:
        return
    schema_id = data.get("s_id")
    if not _non_empty_text(schema_id):
        return
    if kv.get(schema_id) != SCRATCH_SCHEMA_VALUE:
        failures.append("the schema id record is not an empty JSON array")


def _check_ca_array(kv: KVMap, failures: list[str]) -> None:
    gw_ai = _json_object(kv, "gw_ai", failures)
    if gw_ai is None or "caArr" not in gw_ai:
        return
    entries = gw_ai["caArr"]
    if not isinstance(entries, list):
        return
    declared = {entry for entry in entries if isinstance(entry, str)}
    for name in ca_record_names(kv):
        raw = kv[name]
        body = raw[:-1] if raw.endswith(b"\x00") else raw
        if body.decode("ascii", errors="replace") not in declared:
            failures.append("gw_ai.caArr does not carry every stored CA certificate")
            return


def _check_trust(kv: KVMap, failures: list[str]) -> None:
    ca_names = ca_record_names(kv)
    if len(ca_names) != SCRATCH_CA_COUNT:
        failures.append("the scratch set must carry exactly one CA certificate record")
    count = _int_record(kv.get("tls_ca_cnt"), "tls_ca_cnt", failures)
    if count is not None and count != SCRATCH_CA_COUNT:
        failures.append("tls_ca_cnt is not the scratch CA count")
    for name in ca_names:
        if not kv[name].endswith(b"\x00"):
            failures.append("a tls_ca record is not NUL-terminated")


def _check_p2p(kv: KVMap, failures: list[str]) -> None:
    p2p_type = kv.get("p2p_type")
    if p2p_type is not None and p2p_type != SCRATCH_P2P_TYPE:
        failures.append("p2p_type is not the P2P auth-skip marker")
    pwd = kv.get("p2p_pwd")
    if pwd is not None:
        body = pwd[:-1] if pwd.endswith(b"\x00") else pwd
        if (not pwd.endswith(b"\x00") or len(body) != SCRATCH_P2P_PWD_LEN or not body.isascii()
                or b"\x00" in body):
            failures.append("p2p_pwd is not eight ASCII bytes followed by NUL")
    auth = kv.get("p2p_auth_info")
    if auth is not None:
        if not auth.endswith(b"\x00"):
            failures.append("p2p_auth_info is not NUL-terminated")
        record = _json_object(kv, "p2p_auth_info", failures)
        if record is not None:
            if record.get("type") != SCRATCH_P2P_AUTH_TYPE:
                failures.append("p2p_auth_info type is not the P2P auth value")
            if record.get("p2pId") != "":
                failures.append("p2p_auth_info p2pId is not empty")
    wf_start_md = kv.get("wf_start_md")
    if wf_start_md is not None and wf_start_md != SCRATCH_WF_START_MD:
        failures.append("wf_start_md is not the STA start marker")


def _require_equals(
    data: dict[str, object],
    field: str,
    expected: object,
    failures: list[str],
    *,
    label: str = "is not the activated value",
) -> None:
    value = data.get(field)
    if type(value) is not type(expected) or value != expected:
        failures.append(f"gw_wsm.{field} {label}")

"""Identity and fresh trust material for JSON-sourced records."""

import json
from dataclasses import replace

from tuyha.anyka.rcs import decode_rcs_active, encode_rcs_active
from tuyha.contracts.inputs import ArtifactRequest, GeneratedIdentity
from tuyha.tls import TlsMaterial

from .records import json_record


def record_object(records: dict[str, bytes], name: str) -> dict[str, object]:
    try:
        value = json.loads(records.get(name, b"{}").rstrip(b"\x00"))
        if isinstance(value, dict):
            return value
    except (ValueError, UnicodeError):
        pass
    raise ValueError("expected a JSON object in a known gateway record")


def imported_identity(records: dict[str, bytes], overrides: GeneratedIdentity) -> GeneratedIdentity:
    bi, di, ai = (record_object(records, name) for name in ("gw_bi", "gw_di", "gw_ai"))
    fields = {
        "uuid": bi.get("uuid"), "auth_key": bi.get("auth_key"), "psk_key": bi.get("psk_key"),
        "device_id": di.get("id"), "product_key": di.get("pk"), "schema_id": di.get("s_id"),
        "lan_key": ai.get("key"), "lan_local_key": ai.get("lckey"),
    }
    for field, value in fields.items():
        if value is not None and not isinstance(value, str):
            raise ValueError("invalid imported identity field type")
        explicit = getattr(overrides, field)
        if explicit is not None:
            fields[field] = explicit
        elif value == "":
            fields[field] = None
    return replace(overrides, **fields, tuya_seed=overrides.tuya_seed or records.get("tuya_seed"))


def refresh_imported_records(
    request: ArtifactRequest, identity: GeneratedIdentity, tls: TlsMaterial,
) -> dict[str, bytes]:
    records = dict(request.records)
    for name, fields in (
        ("gw_bi", {"uuid": identity.uuid, "auth_key": identity.auth_key, "psk_key": identity.psk_key}),
        ("gw_di", {"id": identity.device_id, "pk": identity.product_key, "s_id": identity.schema_id}),
        ("gw_ai", {"key": identity.lan_key, "lckey": identity.lan_local_key}),
    ):
        obj = record_object(records, name)
        previous = dict(obj)
        obj.update(fields)
        if name == "gw_ai":
            endpoint = f"{request.broker_target.host}:{request.broker_target.port}"
            for field in ("mq_url", "mqs_url", "mq_psk"):
                obj.setdefault(field, endpoint)
            obj.pop("caArr", None)
            if request.tls.include_gw_ai_ca_arr:
                obj["caArr"] = [tls.ca_der_b64]
        if obj != previous:
            records[name] = json_record(obj)
    records["tuya_seed"] = identity.tuya_seed
    records.setdefault(identity.schema_id, b"[]")
    for name in tuple(records):
        if name == "tls_ca_cnt" or (name.startswith("tls_ca") and name[6:].isdigit()):
            del records[name]
    records["tls_ca_cnt"] = b"1\x00"
    records["tls_ca0"] = tls.ca_der_b64.encode("ascii") + b"\x00"
    for name in ("rcs.active", "rcs.mf"):
        if name not in records:
            continue
        rcs = decode_rcs_active(records[name])
        if rcs is not None:
            rcs = replace(rcs, cert_b64=tls.server_cert_der_b64 if request.tls.include_rcs_cert_b64 else None)
            records[name] = encode_rcs_active(rcs)
    return records

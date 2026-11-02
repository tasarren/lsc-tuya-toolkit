import argparse
import base64
from dataclasses import fields, replace

from tuyha.anyka.json_dump import load_json
from tuyha.anyka.rcs import decode_rcs_active, encode_rcs_active, validate_host_port
from tuyha.contracts.inputs import ArtifactRequest, BrokerTarget, GeneratedIdentity, InputError, TlsRequest, WifiInput
from tuyha.materializer.imported import record_object
from tuyha.materializer.records import json_record
from tuyha.materializer.workflow import owned_paths


def build_request(args: argparse.Namespace) -> ArtifactRequest:
    if args.from_json is not None:
        if args.from_json.resolve() in {path.resolve() for path in owned_paths(args.output_dir)}:
            raise InputError("JSON input must not be a generated output file; choose another input or output path")
    records = load_json(args.from_json.read_text(encoding="utf-8")) if args.from_json else None
    wsm = record_object(records, "gw_wsm") if records is not None else {}
    ssid, password = args.wifi_ssid, args.wifi_password
    if records is None and (ssid is None or password is None):
        raise InputError("scratch creation requires --wifi-ssid and --wifi-password")
    if records is not None:
        if ssid is not None or password is not None:
            for field, explicit in (("ssid", ssid), ("passwd", password)):
                value = explicit if explicit is not None else wsm.get(field)
                if explicit is None and wsm.get("wfb64") == 1 and isinstance(value, str):
                    value = base64.b64decode(value, validate=True).decode("utf-8")
                if not isinstance(value, str):
                    raise ValueError("imported Wi-Fi field missing or invalid")
                wsm[field] = base64.b64encode(value.encode("utf-8")).decode("ascii")
            wsm["wfb64"] = 1
        if args.region is not None:
            wsm["region"] = args.region
        if ssid is not None or password is not None or args.region is not None:
            records["gw_wsm"] = json_record(wsm)
    region = args.region if args.region is not None else wsm.get("region", "EU")
    if args.region is None and region in (None, ""):
        region = "EU"
    if not isinstance(region, str) or not 1 <= len(region) <= 2 or not region.isascii():
        raise InputError("region must contain one or two ASCII characters")
    if ssid is not None and (not 1 <= len(ssid.encode("utf-8")) <= 32 or "\x00" in ssid):
        raise InputError("Wi-Fi SSID must contain 1-32 UTF-8 bytes without NUL")
    if password is not None and (len(password.encode("utf-8")) > 64 or "\x00" in password):
        raise InputError("Wi-Fi password must contain at most 64 UTF-8 bytes without NUL")
    host, port = "127.0.0.1", 8883
    if records is not None:
        ai = record_object(records, "gw_ai")
        endpoint = ai.get("mqs_url", f"{host}:{port}")
        if endpoint in (None, ""):
            endpoint = f"{host}:{port}"
        if not isinstance(endpoint, str):
            raise ValueError("JSON input requires gw_ai.mqs_url")
        validate_host_port(endpoint)
        if ":" in endpoint:
            host, port_text = endpoint.rsplit(":", 1)
            port = int(port_text)
        else:
            host = endpoint
    host = args.broker_host if args.broker_host is not None else host
    port = args.broker_port if args.broker_port is not None else port
    if ":" in host:
        raise InputError("broker host must be a hostname or IPv4 address without a port")
    validate_host_port(f"{host}:{port}")
    if args.rcs_host is not None:
        validate_host_port(args.rcs_host, "rcs_host")
    if records is not None:
        if args.broker_host is not None or args.broker_port is not None:
            for field in ("mq_url", "mqs_url", "mq_psk"):
                ai[field] = f"{host}:{port}"
            if args.broker_host is not None:
                ai.update(h_url=host, hs_url=host, hs_psk=host, lp_url=f"{host}:443")
            records["gw_ai"] = json_record(ai)
        for name in ("rcs.active", "rcs.mf"):
            if name not in records:
                continue
            rcs = decode_rcs_active(records[name])
            if rcs is not None and args.rcs_host is not None:
                records[name] = encode_rcs_active(replace(rcs, url0=args.rcs_host, url1=args.rcs_host))
    if args.tls_validity_days < 1:
        raise InputError("TLS validity must be positive")
    return ArtifactRequest(
        wifi=WifiInput(ssid=ssid or "", password=password or "", region=region),
        broker_target=BrokerTarget(host, port),
        output_dir=args.output_dir, records=records, identity=_identity_from_args(args), rcs_host=args.rcs_host,
        tls=TlsRequest(args.tls_common_name, tuple(args.tls_dns_name),
                       tuple(dict.fromkeys(args.tls_ip_address)), args.tls_validity_days,
                       not args.no_rcs_cert_b64, not args.no_gw_ai_ca_arr),
    )


def _identity_from_args(args: argparse.Namespace) -> GeneratedIdentity:
    values = {field.name: getattr(args, field.name) for field in fields(GeneratedIdentity)
              if field.name not in {"tuya_seed", "enckey"}}
    seed = base64.b64decode(args.tuya_seed_b64, validate=True) if args.tuya_seed_b64 is not None else None
    enckey = bytes.fromhex(args.enckey_hex) if args.enckey_hex is not None else None
    if seed is not None and len(seed) != 64:
        raise InputError("tuya_seed must decode to 64 bytes")
    if enckey is not None and len(enckey) != 16:
        raise InputError("enckey must decode to 16 bytes")
    return GeneratedIdentity(**values, tuya_seed=seed, enckey=enckey)

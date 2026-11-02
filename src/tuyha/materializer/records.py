import base64
import json

from tuyha.anyka.rcs import RcsActive, encode_rcs_active, validate_host_port
from tuyha.contracts.inputs import ArtifactRequest, GeneratedIdentity
from tuyha.tls import TlsMaterial

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
WF_START_MD_STA = b"2\x00"
# Firmware iot_wd_common_write is strlen+1. p2p_type must be the ASCII "4"
# (not "mqtt_p2p") so tuya_ipc_check_p2p_auth_update skips HTTP fetch.
P2P_TYPE = b"4\x00"
P2P_PWD = b"tuyhap2p\x00"
TASK1_TLS_PLACEHOLDER = b"TuyHA task 1 TLS placeholder materialized.\n"


def json_record(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def build_firmware_records(
    request: ArtifactRequest,
    identity: GeneratedIdentity,
    tls_material: TlsMaterial | None = None,
) -> dict[str, bytes]:
    broker = request.broker_target
    mqtt_endpoint = f"{broker.host}:{broker.port}"
    rcs_host = request.rcs_host or broker.host
    validate_host_port(rcs_host, "rcs_host")
    wifi = request.wifi
    tls_ca_b64 = _tls_ca_b64(request, tls_material)
    rcs_cert_b64 = _rcs_cert_b64(request, tls_material)
    gw_ai = {
        "key": identity.lan_key,
        "lckey": identity.lan_local_key,
        "h_url": broker.host,
        "hs_url": broker.host,
        "hs_psk": broker.host,
        "mq_url": mqtt_endpoint,
        "mqs_url": mqtt_endpoint,
        "mq_psk": mqtt_endpoint,
        "lp_url": f"{broker.host}:443",
        "time_z": "+00:00",
        "s_time_z": "[]",
        "cloud_cap": 1,
        "dy_tls_m": 0,
    }
    if request.tls.include_gw_ai_ca_arr:
        gw_ai["caArr"] = [tls_ca_b64]
    return {
        "gw_ai": json_record(gw_ai),
        "gw_wsm": json_record(
            {
                "ssid": base64.b64encode(wifi.ssid.encode("utf-8")).decode("ascii"),
                "passwd": base64.b64encode(wifi.password.encode("utf-8")).decode("ascii"),
                "wfb64": 1,
                # nc_tp=9: STA/normal (tuya_wifi_connect_init schedules __wifi_net_conn).
                # Do not use 1/2/10 (is_wifi_need_netconfig → SmartLife AP) or 11/12 (proxy AP).
                "nc_tp": 9,
                "md": 3,
                # stat=2: documented activated MQTT path. Do not use 3 or 4.
                # ap_info_v3 is optional and must stay absent: tkl_wifi_station_fast_connect
                # is a return-0 stub and a dump-shaped blob would skip SSID join.
                "stat": 2,
                "token": "tuyhatok",
                "region": wifi.region,
                "reg_key": "tuyh",
                "dns_prio": 0,
                "is_psk30_cfg": True,
                "is_auto_recover": True,
                "is_auto_connect": True,
            }
        ),
        "gw_bi": json_record(
            {"uuid": identity.uuid, "auth_key": identity.auth_key, "psk_key": identity.psk_key}
        ),
        "gw_di": json_record(
            {"id": identity.device_id, "pk": identity.product_key, "s_id": identity.schema_id,
             "lpv": "3.5"}
        ),
        # destos_init with stat>1 reads this KV key (wd_gw_schema_read). Miss
        # returns -17 and factory-resets packed gw_wsm (nc_tp=2, empty SSID,
        # SmartLife AP). kvtool's working profile writes the same empty array.
        identity.schema_id: b"[]",
        "rcs.active": encode_rcs_active(
            RcsActive(
                code=f"{wifi.region}-PROD",
                url0=rcs_host,
                url1=rcs_host,
                cert_b64=rcs_cert_b64,
            )
        ),
        "tuya_seed": identity.tuya_seed or b"",
        "tls_ca_cnt": b"1\x00",
        # Firmware tuya_cert_save_to_kv writes strlen+1; tuya_base64_decode uses
        # strlen() on the KV blob. Without a trailing NUL, decode overreads PKCS7
        # padding and mbedtls_x509_crt_parse returns 0x2180 (INVALID_FORMAT).
        "tls_ca0": tls_ca_b64.encode("ascii") + b"\x00",
        "wf_start_md": WF_START_MD_STA,
        "p2p_type": P2P_TYPE,
        "p2p_auth_info": json_record({"p2pId": "", "type": 4}) + b"\x00",
        "p2p_pwd": P2P_PWD,
    }


def _tls_ca_b64(request: ArtifactRequest, tls_material: TlsMaterial | None) -> str:
    if tls_material is not None:
        return tls_material.ca_der_b64
    if request.tls_ca_pem is not None:
        return base64.b64encode(request.tls_ca_pem).decode("ascii")
    return base64.b64encode(TASK1_TLS_PLACEHOLDER).decode("ascii")


def _include_rcs_cert(request: ArtifactRequest) -> bool:
    return request.tls.include_rcs_cert_b64


def _rcs_cert_b64(request: ArtifactRequest, tls_material: TlsMaterial | None) -> str | None:
    if not _include_rcs_cert(request) or tls_material is None:
        return None
    return tls_material.server_cert_der_b64

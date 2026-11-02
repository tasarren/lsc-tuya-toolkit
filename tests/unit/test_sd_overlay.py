from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOSTAPD = REPO / "sd_card" / "hostapd"
STAGE2 = REPO / "sd_card" / "custom" / "scripts" / "hack_stage_2.sh"


def test_hostapd_tears_down_ap_addressing_after_stage2() -> None:
    text = HOSTAPD.read_text(encoding="utf-8")
    stage1_at = text.index("hack_stage_1.sh")
    udhcpd_at = text.index("killall udhcpd")
    ifconfig_at = text.index("ifconfig wlan0 0.0.0.0")
    marker_at = text.index("rm /tmp/_ht_ap_mode.conf")
    hostapd_at = text.index("rm /tmp/hostapd")

    assert stage1_at < udhcpd_at < marker_at
    assert udhcpd_at < ifconfig_at < marker_at < hostapd_at
    assert "kill_anyka" in text


def test_stage2_bind_mounts_generated_uuid_ini_when_present() -> None:
    text = STAGE2.read_text(encoding="utf-8")

    assert 'if [ -f "${STATE_DIR}/_ht_uuid.ini" ]; then' in text
    assert 'do_mount "${STATE_DIR}/_ht_uuid.ini" /etc/config/_ht_uuid.ini' in text


def test_stage2_marks_bind_service_before_sw_settings_mount() -> None:
    text = STAGE2.read_text(encoding="utf-8")
    bind_at = text.index("bool_has_bind_service")
    wifi_at = text.index("bool_has_config_wifi")
    mount_at = text.index('do_mount "${STATE_DIR}/_ht_sw_settings.ini" /etc/config/_ht_sw_settings.ini')

    assert bind_at < mount_at
    assert wifi_at < mount_at
    assert 'ensure_ini_flag "bool_has_bind_service"' in text
    assert 'ensure_ini_flag "bool_has_config_wifi"' in text

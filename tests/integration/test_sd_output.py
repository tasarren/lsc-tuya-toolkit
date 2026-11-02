import os
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tuyha.cli.main import main
from tuyha.anyka.json_dump import dump_json
from tuyha.materializer import workflow


def snapshot(root: Path) -> dict[Path, bytes]:
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_default_sd_layout_and_regeneration_preserve_camera_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    state = tmp_path / "sd_card/custom/state"
    (state / "mqtt").mkdir(parents=True)
    for name in (".gitkeep", ".stage1", "_ht_sw_settings.ini", "_ht_hw_settings.ini", "tuya_user.original.db",
                 "tuya_enckey.original.db", "tuya_user.hacked.db_bak", "mqtt/.gitkeep", "mqtt/notes.txt"):
        (state / name).write_bytes(b"existing camera state")
    preserved = snapshot(state)
    command = ["create", "--wifi-ssid", "LabNet", "--wifi-password", "LabPass"]
    assert main(command) == 0
    assert main(["verify", "--file", str(state / "tuya_user.hacked.db"), "--scratch"]) == 0
    assert (state / "mqtt/server.crt").is_file()
    assert (state / "mqtt/server.key").stat().st_mode & 0o777 == 0o600
    assert not (state / "server.key").exists()
    first_key = (state / "tuya_enckey.hacked.db").read_bytes()
    assert main(command) == 0
    assert (state / "tuya_enckey.hacked.db").read_bytes() != first_key
    assert main(["verify", "--file", str(state / "tuya_user.hacked.db"), "--scratch"]) == 0
    assert all((state / name).read_bytes() == content for name, content in preserved.items())
    assert not list(state.parent.glob(".tuyha-*"))
    manifest = json.loads((state / "manifest.json").read_text())
    assert manifest["tls_files"]["server_key_pem"] == "sd_card/custom/state/mqtt/server.key"
    assert manifest["sd_copy_targets"]["server_cert_pem"] == "sd_card/custom/state/mqtt/server.crt"
    generated = set(snapshot(state)) - set(preserved)
    paths = [f"sd_card/custom/state/{name}" for name in generated]
    repo = Path(__file__).resolve().parents[2]
    if not shutil.which("git") or not (repo / ".git").exists():
        return  # Source archives have no Git ignore metadata to check.
    ignored = subprocess.run(["git", "check-ignore", "--no-index", *paths], cwd=repo,
                             capture_output=True, text=True, check=True)
    assert set(ignored.stdout.splitlines()) == set(paths)


def test_publication_error_restores_whole_previous_set(tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / "state"
    command = ["create", "--output-dir", str(state), "--wifi-ssid", "LabNet", "--wifi-password", "LabPass"]
    assert main(command) == 0
    assert (state / "mqtt").stat().st_mode & 0o777 == 0o700
    assert (state / "tuya_user.hacked.db").stat().st_mode & 0o777 == 0o600
    before = snapshot(state)
    original_replace = workflow.os.replace

    def fail_midway(source: Path, target: Path) -> None:
        if source.parent.name == "mqtt" and source.name == "server.crt" and "artifacts" in source.parts:
            raise OSError("simulated publication failure")
        original_replace(source, target)

    monkeypatch.setattr(workflow.os, "replace", fail_midway)
    assert main(command) == 2
    assert snapshot(state) == before
    assert not list(tmp_path.glob(".tuyha-*"))


def test_recovery_failure_retains_previous_artifacts(tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / "state"
    command = ["create", "--output-dir", str(state), "--wifi-ssid", "LabNet", "--wifi-password", "LabPass"]
    assert main(command) == 0
    before = snapshot(state)
    original_replace = workflow.os.replace

    def fail_publish_and_recovery(source: Path, target: Path) -> None:
        if "previous" in source.parts or source.name == "server.crt":
            raise OSError("simulated publication and recovery failure")
        original_replace(source, target)

    monkeypatch.setattr(workflow.os, "replace", fail_publish_and_recovery)
    assert main(command) == 2
    recovery, = tmp_path.glob(".tuyha-*")
    assert snapshot(recovery / "previous") == before


def test_special_file_destination_rejected(tmp_path: Path) -> None:
    os.mkfifo(tmp_path / "tuya_user.hacked.db")
    assert main(["create", "--output-dir", str(tmp_path), "--wifi-ssid", "LabNet", "--wifi-password", "LabPass"]) == 2


@pytest.mark.parametrize("name", ["manifest.json", "tuya_user.hacked.db", "mqtt/server.key"])
def test_json_input_cannot_be_overwritten_by_creation(tmp_path: Path, name: str) -> None:
    source = tmp_path / name
    source.parent.mkdir(parents=True, exist_ok=True)
    content = dump_json({})
    source.write_text(content)
    assert main(["create", "--from", str(source), "--output-dir", str(tmp_path)]) == 2
    assert source.read_text() == content
    assert not list(tmp_path.parent.glob(".tuyha-*"))


@pytest.mark.parametrize("name", ["mqtt", "tuya_user.hacked.db", "mqtt/server.key"])
def test_symlink_destinations_rejected_without_touching_source(tmp_path: Path, name: str) -> None:
    state = tmp_path / "state"
    (state / name).parent.mkdir(parents=True)
    source = tmp_path / "source"
    source.write_bytes(b"preserve source")
    (state / name).symlink_to(source)
    assert main(["create", "--output-dir", str(state), "--wifi-ssid", "LabNet", "--wifi-password", "LabPass"]) == 2
    assert source.read_bytes() == b"preserve source"
    assert not list(tmp_path.glob(".tuyha-*"))

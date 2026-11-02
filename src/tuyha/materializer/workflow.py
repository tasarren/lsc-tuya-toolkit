import os
import shutil
import tempfile
from dataclasses import astuple
from pathlib import Path

from tuyha.anyka.db import build_db
from tuyha.anyka.verify import verify_kv
from tuyha.contracts.artifacts import ArtifactSet, TlsArtifactSet
from tuyha.contracts.inputs import ArtifactRequest, InputError
from tuyha.tls import generate_tls_material
from tuyha.tls.generator import tls_paths

from .identity import resolved_identity
from .imported import imported_identity, refresh_imported_records
from .manifest import write_manifest
from .records import build_firmware_records
from .uuid_ini import UUID_INI_NAME, write_uuid_ini

OUTPUT_USER_DB = "tuya_user.hacked.db"
OUTPUT_ENCKEY_DB = "tuya_enckey.hacked.db"
OUTPUT_MANIFEST = "manifest.json"
TLS_SUBDIR = "mqtt"


def owned_paths(output: Path) -> tuple[Path, ...]:
    return (output / OUTPUT_USER_DB, output / OUTPUT_ENCKEY_DB, output / UUID_INI_NAME,
            *astuple(tls_paths(output / TLS_SUBDIR)), output / OUTPUT_MANIFEST)


def materialize_artifacts(request: ArtifactRequest) -> ArtifactSet:
    output = request.output_dir
    tls_artifacts = tls_paths(output / TLS_SUBDIR)
    artifacts = _artifact_paths(output, tls_artifacts)
    relative_files = [path.relative_to(output) for path in owned_paths(output)]
    for path in (output, output / TLS_SUBDIR, *(output / name for name in relative_files)):
        if path.is_symlink():
            raise InputError("output directories and generated files must not be symlinks")
        directory = path in (output, output / TLS_SUBDIR)
        if path.exists() and not (path.is_dir() if directory else path.is_file()):
            raise InputError("output path has the wrong file type")
    overrides = request.identity
    if request.records is not None:
        overrides = imported_identity(request.records, overrides)
        build_db(request.records, bytes(16))  # Validate record names and sizes before generation.
    identity = resolved_identity(overrides)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".tuyha-", dir=output.parent))
    stage = temp / "artifacts"
    try:
        stage.mkdir(mode=0o700)
        (stage / TLS_SUBDIR).mkdir(mode=0o700)
        tls = generate_tls_material(stage / TLS_SUBDIR, request.tls, request.broker_target)
        records = (build_firmware_records(request, identity, tls) if request.records is None
                   else refresh_imported_records(request, identity, tls))
        if verify_kv(records, scratch=request.records is None):
            raise ValueError("generated records failed offline validation")
        (stage / OUTPUT_USER_DB).write_bytes(build_db(records, identity.enckey))
        (stage / OUTPUT_ENCKEY_DB).write_bytes(identity.enckey)
        write_uuid_ini(stage / UUID_INI_NAME, identity)
        write_manifest(stage / OUTPUT_MANIFEST, request, artifacts, identity, tuple(records), tls)
        for name in relative_files:
            (stage / name).chmod(0o600)
    except BaseException:
        shutil.rmtree(temp)
        raise
    _publish(stage, output, relative_files)
    shutil.rmtree(temp)
    return artifacts


def _publish(stage: Path, output: Path, names: list[Path]) -> None:
    # ponytail: per-file rollback covers ordinary errors; power-loss transactions need directory indirection.
    backup = stage.parent / "previous"
    replaced: list[Path] = []
    created_dirs: list[Path] = []
    try:
        for name in names:
            target = output / name
            if target.exists():
                saved = backup / name
                saved.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                shutil.copy2(target, saved)
        for directory in (output, output / TLS_SUBDIR):
            if not directory.exists():
                directory.mkdir(mode=0o700)
                created_dirs.append(directory)
        for name in names:
            os.replace(stage / name, output / name)
            replaced.append(name)
    except BaseException:
        try:
            for name in reversed(replaced):
                if (backup / name).exists():
                    os.replace(backup / name, output / name)
                else:
                    (output / name).unlink()
            for directory in reversed(created_dirs):
                directory.rmdir()
        except OSError:
            raise InputError(f"publication recovery failed; recovery files retained in {stage.parent}") from None
        shutil.rmtree(stage.parent)
        raise


def _artifact_paths(output_dir: Path, tls_artifacts: TlsArtifactSet) -> ArtifactSet:
    return ArtifactSet(
        user_db=output_dir / OUTPUT_USER_DB,
        enckey_db=output_dir / OUTPUT_ENCKEY_DB,
        manifest=output_dir / OUTPUT_MANIFEST,
        uuid_ini=output_dir / UUID_INI_NAME,
        tls=tls_artifacts,
    )

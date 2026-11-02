import os
from pathlib import Path

from tuyha.anyka.db import load_kv
from tuyha.anyka.json_dump import dump_json
from tuyha.anyka.verify import verify_kv
from tuyha.contracts.inputs import InputError


def enckey_path(db: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    if not db.name.startswith("tuya_user.") or not db.name.endswith(".db"):
        raise InputError("custom DB filename requires --enckey")
    return db.with_name(db.name.replace("tuya_user.", "tuya_enckey.", 1))


def dump_db(db: Path, enckey: Path, output: Path) -> None:
    content = dump_json(load_kv(db, enckey))
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
    except BaseException:
        output.unlink()
        raise


def verify_db(db: Path, enckey: Path, *, scratch: bool) -> tuple[str, ...]:
    return verify_kv(load_kv(db, enckey), scratch=scratch)

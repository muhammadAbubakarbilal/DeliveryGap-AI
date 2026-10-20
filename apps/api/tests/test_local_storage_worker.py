from datetime import timedelta
from pathlib import Path

import pytest
from app.models import now
from app.operation_models import Operation
from app.source_storage import FilesystemStorage
from sqlalchemy import select
from test_foundation import create_project

from scripts.local_worker import recover_expired_operations


def test_filesystem_storage_preserves_originals_and_reads_bytes(tmp_path: Path):
    storage = FilesystemStorage(tmp_path / "objects")
    storage.put("project/version/original.txt", b"immutable")

    assert storage.get("project/version/original.txt") == b"immutable"
    with pytest.raises(FileExistsError):
        storage.put("project/version/original.txt", b"replacement")
    assert storage.get("project/version/original.txt") == b"immutable"


@pytest.mark.parametrize(
    "key",
    ["", "../outside", "a/../outside", "/absolute", "a\\..\\outside", "C:/outside", "a:b"],
)
def test_filesystem_storage_rejects_unsafe_keys(tmp_path: Path, key: str):
    storage = FilesystemStorage(tmp_path / "objects")

    with pytest.raises(ValueError, match="Invalid private-storage object key"):
        storage.put(key, b"content")


def test_filesystem_storage_rejects_symlink_escape(tmp_path: Path):
    storage = FilesystemStorage(tmp_path / "objects")
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (storage.root / "escape").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable on this Windows account")

    with pytest.raises(ValueError, match="outside the configured root"):
        storage.put("escape/original.txt", b"content")


def test_filesystem_storage_rejects_oversized_object(tmp_path: Path, monkeypatch):
    storage = FilesystemStorage(tmp_path / "objects")
    (storage.root / "original.txt").write_bytes(b"12345")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "4")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="exceeds limit"):
            storage.get("original.txt")
    finally:
        get_settings.cache_clear()


def test_local_worker_recovers_expired_operations(client, login, database):
    login()
    project = create_project(client)
    with database() as db:
        db.add(
            Operation(
                project_id=project["id"],
                actor_id="admin",
                kind="report",
                status="running",
                payload={},
                attempts=1,
                dispatched_at=now() - timedelta(minutes=30),
                lease_until=now() - timedelta(seconds=1),
                fence="expired-fence",
            )
        )
        db.commit()
        operation_id = db.scalar(select(Operation.id))

    assert recover_expired_operations(database) == [operation_id]

    with database() as db:
        operation = db.get_one(Operation, operation_id)
        assert operation.status == "queued"
        assert operation.fence is None
        assert operation.lease_until is None
        assert operation.dispatched_at is None

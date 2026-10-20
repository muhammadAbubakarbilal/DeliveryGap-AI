import os
import tempfile
from pathlib import Path
from typing import Protocol

import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]

from app.config import get_settings


class Storage(Protocol):
    def put(self, key: str, content: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...


class S3Storage:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.s3_access_key or not settings.s3_secret_key:
            raise RuntimeError("Private storage credentials are not configured")
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name="us-east-1",
            config=Config(connect_timeout=5, read_timeout=20, retries={"max_attempts": 2}),
        )

    def put(self, key: str, content: bytes) -> None:
        # Never overwrite an original, including on retries.
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType="application/octet-stream",
            IfNoneMatch="*",
        )

    def get(self, key: str) -> bytes:
        result = self.client.get_object(Bucket=self.bucket, Key=key)
        stream = result["Body"]
        try:
            content: bytes = stream.read(get_settings().max_upload_bytes + 1)
            if len(content) > get_settings().max_upload_bytes:
                raise ValueError("Stored original exceeds limit")
            return content
        finally:
            stream.close()


class FilesystemStorage:
    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        self.root = root.resolve()

    def _path(self, key: str, *, allow_missing: bool) -> Path:
        if (
            not key
            or "\x00" in key
            or "\\" in key
            or any(part in {"", ".", ".."} or ":" in part for part in key.split("/"))
        ):
            raise ValueError("Invalid private-storage object key")
        resolved = self.root.joinpath(*key.split("/")).resolve(strict=not allow_missing)
        if os.path.commonpath((str(self.root), str(resolved))) != str(self.root):
            raise ValueError("Private-storage object is outside the configured root")
        return resolved

    def put(self, key: str, content: bytes) -> None:
        destination = self._path(key, allow_missing=True)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination = self._path(key, allow_missing=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=destination.parent, prefix=".deliverygap-", delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def get(self, key: str) -> bytes:
        path = self._path(key, allow_missing=False)
        if not path.is_file():
            raise FileNotFoundError("Private-storage original is unavailable")
        with path.open("rb") as stream:
            content = stream.read(get_settings().max_upload_bytes + 1)
        if len(content) > get_settings().max_upload_bytes:
            raise ValueError("Stored original exceeds limit")
        return content


def get_storage() -> Storage:
    settings = get_settings()
    if settings.source_storage_backend == "filesystem":
        return FilesystemStorage(Path(settings.local_storage_path))
    return S3Storage()

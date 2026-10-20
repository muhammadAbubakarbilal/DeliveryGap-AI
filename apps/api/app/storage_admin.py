"""Initialize private local storage or remove abandoned originals after a grace period."""

import sys
import time
from datetime import timedelta

from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from sqlalchemy import select

from app.db import SessionLocal
from app.models import now
from app.source_models import DocumentVersion
from app.source_storage import S3Storage


def initialize() -> None:
    store = S3Storage()
    try:
        store.client.head_bucket(Bucket=store.bucket)
    except ClientError as exc:
        if str(exc.response["Error"]["Code"]) not in {"404", "NoSuchBucket"}:
            raise RuntimeError("Private bucket initialization failed") from None
        store.client.create_bucket(Bucket=store.bucket)
    # Fail closed if a bucket policy already permits any anonymous access.
    try:
        store.client.get_bucket_policy(Bucket=store.bucket)
    except ClientError as exc:
        if str(exc.response["Error"]["Code"]) not in {"NoSuchBucketPolicy", "404"}:
            raise RuntimeError("Cannot verify private bucket policy") from None
    else:
        raise RuntimeError("Local private bucket must not have a public bucket policy")


def cleanup() -> None:
    store = S3Storage()
    cutoff = now() - timedelta(hours=24)
    paginator = store.client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=store.bucket, Prefix="originals/"):
        for item in page.get("Contents", []):
            if item["LastModified"] >= cutoff:
                continue
            with SessionLocal() as db:
                exists = db.scalar(
                    select(DocumentVersion.id).where(DocumentVersion.storage_key == item["Key"])
                )
                if exists is None:
                    store.client.delete_object(Bucket=store.bucket, Key=item["Key"])


if __name__ == "__main__":
    if "--cleanup-loop" in sys.argv:
        while True:
            try:
                cleanup()
            except Exception:
                print("Private storage cleanup unavailable", flush=True)
            time.sleep(3600)
    else:
        for attempt in range(30):
            try:
                initialize()
                break
            except Exception:
                if attempt == 29:
                    raise SystemExit("Private storage initialization failed") from None
                time.sleep(2)

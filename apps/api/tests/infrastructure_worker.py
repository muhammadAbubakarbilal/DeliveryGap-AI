"""Real RQ worker with an optional test-only pause after reading the private original."""

import os
import time
from pathlib import Path

from app import operation_jobs, source_jobs
from app.config import get_settings
from app.source_storage import S3Storage
from redis import Redis
from rq import Queue, Worker


class PausedStorage(S3Storage):
    def get(self, key: str) -> bytes:
        content = super().get(key)
        Path(os.environ["ACCEPTANCE_PAUSE_MARKER"]).touch()
        time.sleep(120)
        return content


def pause_operation(function):
    def paused(db, operation):
        result = function(db, operation)
        db.flush()
        Path(os.environ["ACCEPTANCE_PAUSE_MARKER"]).touch()
        time.sleep(120)
        return result

    return paused


if __name__ == "__main__":
    if os.environ.get("ACCEPTANCE_PAUSE_MARKER"):
        source_jobs.get_storage = PausedStorage
        operation_jobs.apply_import = pause_operation(operation_jobs.apply_import)
        operation_jobs.create_snapshot = pause_operation(operation_jobs.create_snapshot)
    connection = Redis.from_url(get_settings().redis_url)
    queue = Queue(os.environ["ACCEPTANCE_QUEUE"], connection=connection)
    Worker([queue], connection=connection).work(burst=True, logging_level="WARNING")

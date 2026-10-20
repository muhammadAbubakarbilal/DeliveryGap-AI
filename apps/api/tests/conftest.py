import os
from collections.abc import Generator
from uuid import uuid4

import pytest
from app.db import Base, get_db
from app.main import app
from app.models import User
from app.security import hasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def database() -> Generator[sessionmaker[Session], None, None]:
    """Postgres integration when TEST_DATABASE_URL is supplied; isolated unit DB otherwise.

    PostgreSQL uses a unique schema, never drops a shared database or public tables.
    SQLite tests validate API behavior only, not PostgreSQL concurrency/migrations.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    schema = "test_" + uuid4().hex
    if url:
        admin = create_engine(url)
        with admin.begin() as connection:
            if (
                connection.scalar(text("SELECT to_regtype('deliverygap_test_extensions.vector')"))
                is None
            ):
                admin.dispose()
                pytest.fail(
                    "Test database requires vector in deliverygap_test_extensions. "
                    "Provision infrastructure/test-extensions.sql in a dedicated test database."
                )
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(
            url,
            connect_args={"options": f"-csearch_path={schema},deliverygap_test_extensions"},
        )
    else:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )

        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    try:
        Base.metadata.create_all(engine)
        factory = sessionmaker(engine, expire_on_commit=False)
        with factory() as db:
            for name, admin_flag in [
                ("admin", True),
                ("lead", False),
                ("member", False),
                ("reviewer", False),
                ("outsider", False),
            ]:
                db.add(
                    User(
                        id=name,
                        email=f"{name}@example.com",
                        display_name=name.title(),
                        password_hash=hasher.hash("test-password-long"),
                        is_admin=admin_flag,
                    )
                )
            db.commit()
        yield factory
    finally:
        engine.dispose()
        if url:
            try:
                with admin.begin() as connection:
                    connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            finally:
                admin.dispose()


@pytest.fixture
def client(database) -> Generator[TestClient, None, None]:
    def override():
        with database() as db:
            yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app, headers={"origin": "http://localhost:3000"}) as instance:
        yield instance
    app.dependency_overrides.clear()


@pytest.fixture
def login(client):
    def as_user(name="admin"):
        client.cookies.clear()
        response = client.post(
            "/api/v1/auth/login",
            json={"email": f"{name}@example.com", "password": "test-password-long"},
        )
        assert response.status_code == 200, response.text
        client.headers["x-csrf-token"] = response.json()["csrf_token"]
        return response

    return as_user

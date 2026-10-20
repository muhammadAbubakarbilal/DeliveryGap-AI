from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
from app import neon_auth
from app.config import Settings
from app.models import User
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def test_neon_exchange_validates_signature_identity_and_expiry(client, database, monkeypatch):
    key = Ed25519PrivateKey.generate()
    origin = "https://example.neonauth.neon.tech"
    monkeypatch.setattr(
        neon_auth,
        "get_settings",
        lambda: Settings(
            neon_auth_base_url=origin + "/neondb/auth",
            neon_auth_jwks_url=origin + "/neondb/auth/.well-known/jwks.json",
        ),
    )
    monkeypatch.setattr(
        neon_auth,
        "key_client",
        lambda _: SimpleNamespace(
            get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key())
        ),
    )
    with database() as db:
        member = db.get(User, "member")
        member.neon_subject = "managed-member"
        db.commit()
    now = datetime.now(UTC)
    claims = {
        "sub": "managed-member",
        "iss": origin,
        "aud": origin,
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "role": "admin",
    }

    def exchange(payload, signing_key=key):
        token = jwt.encode(payload, signing_key, algorithm="EdDSA")
        return client.post("/api/v1/auth/neon", headers={"Authorization": "Bearer " + token})

    response = exchange({**claims, "iat": now + timedelta(seconds=2)})
    assert response.status_code == 200, response.text
    assert response.json()["auth_provider"] == "neon"
    assert response.json()["user"]["is_admin"] is False
    assert client.get("/api/v1/auth/me").status_code == 200
    assert exchange({**claims, "aud": "https://wrong.example"}).status_code == 401
    assert exchange({**claims, "exp": now - timedelta(seconds=1)}).status_code == 401
    assert exchange({**claims, "iat": now + timedelta(minutes=1)}).status_code == 401
    assert exchange(claims, Ed25519PrivateKey.generate()).status_code == 401
    assert exchange({**claims, "sub": "unmapped", "email": "admin@example.com"}).status_code == 403
    assert exchange({**claims, "banned": True}).status_code == 401
    logout = client.post(
        "/api/v1/auth/logout", headers={"X-CSRF-Token": response.json()["csrf_token"]}
    )
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_neon_postgres_urls_preserve_tls_options():
    settings = Settings(
        database_url="postgresql://u:p@db.example/db?sslmode=require",
        database_url_unpooled="postgres://u:p@direct.example/db?sslmode=require",
    )
    assert settings.database_url == "postgresql+psycopg://u:p@db.example/db?sslmode=require"
    assert settings.database_url_unpooled.startswith("postgresql+psycopg://")

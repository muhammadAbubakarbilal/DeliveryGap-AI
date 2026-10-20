from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.models import AuditEvent, LoginSession
from sqlalchemy import select


def create_project(client, name="ShopFlow"):
    response = client.post(
        "/api/v1/projects",
        json={"name": name, "description": "Checkout"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_session_cookie_logout_and_revocation(client, login, database):
    assert client.get("/api/v1/auth/me").status_code == 401
    response = login()
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    token = client.cookies.get("deliverygap_session")
    with database() as db:
        row = db.scalar(select(LoginSession))
        assert row.token_hash != token
    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 204
    client.cookies.set("deliverygap_session", token)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_csrf_origin_and_validation_do_not_echo_secrets(client, login):
    login()
    assert (
        client.post(
            "/api/v1/projects", json={"name": "x"}, headers={"origin": "https://evil.example"}
        ).status_code
        == 403
    )
    client.headers.pop("x-csrf-token")
    assert client.post("/api/v1/projects", json={"name": "x"}).status_code == 403
    response = client.post("/api/v1/auth/login", json={"email": "bad", "password": "secret!"})
    assert response.status_code == 422
    assert "secret!" not in response.text
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store"


def test_project_isolation_roles_and_membership_removal(client, login):
    login()
    project = create_project(client)
    path = f"/api/v1/projects/{project['id']}"
    for name in ["member", "reviewer"]:
        assert (
            client.post(
                path + "/members", json={"email": f"{name}@example.com", "role": name}
            ).status_code
            == 201
        )
    for role in ["member", "reviewer"]:
        login(role)
        assert client.get(path).status_code == 200
        assert client.patch(path, json={"name": "hack", "revision": 1}).status_code == 403
        assert (
            client.post(
                "/api/v1/projects", json={"name": "hack"}, headers={"Idempotency-Key": str(uuid4())}
            ).status_code
            == 403
        )
        assert client.delete(path + "/members/admin").status_code == 403
    login("outsider")
    assert client.get(path).status_code == 404
    assert client.get(path + "/members").status_code == 404
    assert client.get("/api/v1/projects").json()["total"] == 0
    login()
    assert client.delete(path + "/members/member").status_code == 204
    login("member")
    assert client.get(path).status_code == 404


def test_last_lead_and_stale_project_update(client, login):
    login()
    project = create_project(client)
    path = f"/api/v1/projects/{project['id']}"
    assert client.delete(path + "/members/admin").status_code == 409
    assert client.patch(path + "/members/admin", json={"role": "member"}).status_code == 409
    update = {"name": "Revised", "description": "Updated", "revision": 1}
    assert client.patch(path, json=update).status_code == 200
    assert client.patch(path, json=update).status_code == 409
    assert client.get(path).json()["name"] == "Revised"


def test_external_ai_consent_is_lead_controlled_audited_and_revocable(client, login, database):
    login()
    project = create_project(client)
    path = f"/api/v1/projects/{project['id']}"
    assert project["external_ai_consent"] is False
    assert (
        client.post(
            path + "/members", json={"email": "lead@example.com", "role": "lead"}
        ).status_code
        == 201
    )
    assert (
        client.post(
            path + "/members", json={"email": "member@example.com", "role": "member"}
        ).status_code
        == 201
    )

    login("member")
    assert client.patch(path + "/ai-consent", json={"enabled": True}).status_code == 403
    login("lead")
    enabled = client.patch(path + "/ai-consent", json={"enabled": True})
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["external_ai_consent"] is True
    login()
    disabled = client.patch(path + "/ai-consent", json={"enabled": False})
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["external_ai_consent"] is False
    with database() as db:
        events = list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.project_id == project["id"],
                    AuditEvent.event_type == "project.external_ai_consent.changed",
                )
            )
        )
        assert sorted(event.details["enabled"] for event in events) == [False, True]


def test_admin_user_creation_disabled_sessions_and_duplicates(client, login):
    login()
    body = {
        "email": "NEW@EXAMPLE.COM",
        "display_name": "New user",
        "password": "a-long-new-password",
    }
    response = client.post("/api/v1/admin/users", json=body)
    assert response.status_code == 201
    assert response.json()["email"] == "new@example.com"
    assert "password" not in response.text
    assert client.post("/api/v1/admin/users", json=body).status_code == 409
    login("member")
    token = client.cookies.get("deliverygap_session")
    assert client.get("/api/v1/admin/users").status_code == 403
    login()
    assert client.patch("/api/v1/admin/users/member", json={"is_active": False}).status_code == 200
    client.cookies.clear()
    client.cookies.set("deliverygap_session", token)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_lead_management_and_admin_bypass_is_audited(client, login, database):
    login()
    project = create_project(client)
    path = f"/api/v1/projects/{project['id']}"
    assert (
        client.post(
            path + "/members", json={"email": "lead@example.com", "role": "lead"}
        ).status_code
        == 201
    )
    login("lead")
    assert client.delete(path + "/members/admin").status_code == 204
    assert (
        client.post(
            path + "/members", json={"email": "reviewer@example.com", "role": "reviewer"}
        ).status_code
        == 201
    )
    login()
    assert client.get(path).status_code == 200
    assert client.patch("/api/v1/admin/users/lead", json={"is_active": False}).status_code == 409
    with database() as db:
        assert db.scalar(select(AuditEvent).where(AuditEvent.event_type == "admin.project_access"))


def test_expired_sessions_and_login_throttle(client, login, database):
    login()
    with database() as db:
        session = db.scalar(select(LoginSession))
        session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401
    for _ in range(10):
        assert (
            client.post(
                "/api/v1/auth/login", json={"email": "unknown@example.com", "password": "bad"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "unknown@example.com", "password": "bad"}
        ).status_code
        == 429
    )


def test_search_pagination_and_health(client, login):
    login()
    create_project(client, "ShopFlow")
    create_project(client, "Internal Tool")
    result = client.get("/api/v1/projects?q=shop&page_size=1").json()
    assert result["total"] == 1 and result["items"][0]["name"] == "ShopFlow"
    assert client.get("/api/v1/projects?page_size=1000").status_code == 422
    assert client.get("/api/v1/health/live").status_code == 200
    assert client.get("/api/v1/health/ready").status_code == 200

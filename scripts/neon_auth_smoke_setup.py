"""Create one synthetic managed identity for end-to-end verification; keep secrets ignored."""

import json
import secrets
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api"))
import httpx  # noqa: E402
from app.config import get_settings  # noqa: E402

root = Path(__file__).resolve().parents[1]
state_file = root / ".cache/neon-smoke.json"
settings = get_settings()
if state_file.exists():
    print("Synthetic identity already prepared; reuse its ignored local credentials.")
    raise SystemExit(0)
identity = {
    "email": f"deliverygap-smoke-{uuid4().hex[:12]}@example.invalid",
    "password": secrets.token_urlsafe(32),
    "name": "DeliveryGap integration test",
}
try:
    response = httpx.post(
        settings.neon_auth_base_url.rstrip("/") + "/sign-up/email",
        json=identity,
        headers={"Origin": settings.app_origin},
        timeout=30,
    )
    if response.status_code not in (200, 201):
        print("Neon Auth synthetic signup failed: HTTP", response.status_code)
        raise SystemExit(1)
    payload = response.json()
    identity["subject"] = payload["user"]["id"]
    state_file.parent.mkdir(exist_ok=True)
    state_file.write_text(json.dumps(identity), encoding="utf-8")
    print("Neon Auth synthetic signup passed; credentials stored only in ignored .cache.")
except (httpx.HTTPError, KeyError, ValueError) as exc:
    print("Neon Auth smoke setup failed:", type(exc).__name__)
    raise SystemExit(1) from None

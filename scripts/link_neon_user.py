"""Explicitly authorize a Neon identity as an application user."""

import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api"))
from app.db import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.security import audit, hasher  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--subject", required=True)
parser.add_argument("--admin", action="store_true")
args = parser.parse_args()
with SessionLocal() as db:
    # Validate the managed identity in the selected branch; never infer it from an email claim.
    managed = (
        db.execute(
            text('SELECT id, email, name FROM neon_auth."user" WHERE id = :subject'),
            {"subject": args.subject},
        )
        .mappings()
        .first()
    )
    if managed is None:
        raise SystemExit("Managed identity does not exist in this branch")
    user = db.scalar(select(User).where(User.email == managed["email"].lower()))
    if user is not None and user.neon_subject not in (None, args.subject):
        raise SystemExit("This workspace user is linked to a different managed identity")
    if user is None:
        user = User(
            email=managed["email"].lower(),
            display_name=managed["name"][:100],
            password_hash=hasher.hash(secrets.token_urlsafe(32)),
        )
        db.add(user)
    user.neon_subject = args.subject
    if args.admin:
        user.is_admin = True
    db.flush()
    audit(db, user, "user.neon_linked_by_operator", user.id)
    db.commit()
print("Managed identity linked to workspace access.")

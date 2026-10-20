import os

from sqlalchemy import select

from app.db import SessionLocal
from app.models import User
from app.security import audit, hasher


def main() -> None:
    email = os.environ.get("SEED_ADMIN_EMAIL", "admin@deliverygap.example.com").strip().lower()
    password = os.environ.get("SEED_ADMIN_PASSWORD", "")
    if len(password) < 12:
        raise SystemExit(
            "Set SEED_ADMIN_PASSWORD to at least 12 characters; no default is supplied."
        )
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            print("Seed user already exists; credentials and permissions were not changed.")
            return
        user = User(
            email=email,
            display_name=os.environ.get("SEED_ADMIN_NAME", "Workspace Admin"),
            password_hash=hasher.hash(password),
            is_admin=True,
        )
        db.add(user)
        db.flush()
        audit(db, user, "user.seeded", user.id)
        db.commit()
    print("Workspace administrator created.")


if __name__ == "__main__":
    main()

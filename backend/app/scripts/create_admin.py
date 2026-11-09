"""Create an admin user.

Usage:
    python -m app.scripts.create_admin admin@example.com 'a-strong-password' --name "Shop Admin"
"""
import argparse

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import Role, User


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an admin user")
    parser.add_argument("email")
    parser.add_argument("password")
    parser.add_argument("--name", default="Admin")
    args = parser.parse_args()

    email = args.email.lower()
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            print(f"User {email} already exists")
            return
        db.add(
            User(
                email=email,
                full_name=args.name,
                hashed_password=hash_password(args.password),
                role=Role.ADMIN.value,
            )
        )
        db.commit()
    print(f"Admin {email} created")


if __name__ == "__main__":
    main()
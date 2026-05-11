import argparse

from sqlalchemy import select

from src.app.db import SessionLocal, init_db
from src.web.auth import hash_password
from src.web.models import WebUser


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)

    args = parser.parse_args()

    init_db()

    with SessionLocal() as db:
        user = db.scalar(select(WebUser).where(WebUser.username == args.username))

        if user is None:
            user = WebUser(username=args.username)
            db.add(user)

        user.password_hash = hash_password(args.password)
        user.role = "admin"
        user.is_active = True

        db.commit()

    print("Admin created/updated")


if __name__ == "__main__":
    main()
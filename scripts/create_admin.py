"""Create or promote an HR admin account.

Self-registration through the API always creates an employee, so this script is
the supported way to make an administrator. Run it on the machine hosting the
application, where database access already implies trust.

Usage::

    python -m scripts.create_admin --email hr.lead@acme.com --name "HR Lead"
    python -m scripts.create_admin --email existing@acme.com --promote

The password is read interactively so it never lands in shell history. Pass
``--password`` only for non-interactive provisioning.
"""
from __future__ import annotations

import argparse
import getpass
import sys

from backend.database.database import SessionLocal
from backend.database.init_db import init_db
from backend.models.user import UserRole
from backend.services import auth_service

MIN_PASSWORD_LENGTH = 8


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="admin email address")
    parser.add_argument("--name", default="HR Admin", help="display name")
    parser.add_argument("--password", help="password (prompted if omitted)")
    parser.add_argument(
        "--promote",
        action="store_true",
        help="promote an existing user to admin instead of creating one",
    )
    args = parser.parse_args()

    init_db()

    with SessionLocal() as db:
        existing = auth_service.get_user_by_email(db, args.email)

        if args.promote:
            if existing is None:
                print(f"No user found with email {args.email}", file=sys.stderr)
                return 1
            existing.role = UserRole.admin
            db.commit()
            print(f"Promoted {args.email} to admin.")
            return 0

        if existing is not None:
            print(
                f"{args.email} already exists (role: {existing.role.value}). "
                "Use --promote to grant admin rights.",
                file=sys.stderr,
            )
            return 1

        password = args.password or getpass.getpass("Password: ")
        if len(password) < MIN_PASSWORD_LENGTH:
            print(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
                file=sys.stderr,
            )
            return 1

        user = auth_service.register_user(
            db,
            name=args.name,
            email=args.email,
            password=password,
            role=UserRole.admin,
        )
        print(f"Created admin {user.email} (id={user.id}).")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

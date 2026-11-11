"""Operator-only account bootstrap: python -m app.platform.accounts --help."""

import argparse
from getpass import getpass
from uuid import uuid4

from dotenv import load_dotenv

from app.platform.auth import password_hash
from app.platform.store import Store


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Create a local PayPool account")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument(
        "--role", choices=["ADMIN", "SELLER", "RETAILER", "DRIVER"], required=True
    )
    parser.add_argument("--lon", type=float, default=0)
    parser.add_argument("--lat", type=float, default=0)
    parser.add_argument("--verified", action="store_true")
    args = parser.parse_args()
    if not (-180 <= args.lon <= 180 and -90 <= args.lat <= 90):
        parser.error("Coordinates must be longitude / latitude")
    email = args.email.strip().lower()
    if "@" not in email or email.endswith("@paypool.demo"):
        parser.error("Use an account address outside the reserved demo domain")
    password = getpass("New password (12+ characters): ")
    if len(password) < 12 or getpass("Confirm password: ") != password:
        parser.error("Passwords must match and contain at least 12 characters")
    with Store().transaction() as tx:
        if any(user["email"] == email for user in tx.all("users")):
            parser.error("An account with that email already exists")
        user = tx.put(
            "users",
            {
                "id": str(uuid4()),
                "email": email,
                "name": args.name,
                "roles": [args.role],
                "active": True,
                "verified": args.verified,
                "location": [args.lon, args.lat],
                "password_hash": password_hash(password),
            },
        )
        tx.audit(user["id"], "ACCOUNT_BOOTSTRAPPED", user["id"])
    print(f"Created {args.role} account {user['id']}")


if __name__ == "__main__":
    main()

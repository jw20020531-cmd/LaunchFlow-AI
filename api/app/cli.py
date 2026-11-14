import argparse
from getpass import getpass
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from .auth import passwords
from .db import Session
from .models import Link, SessionRecord, User, Workspace

def password_input():
    first = getpass("Password (at least 12 characters): ")
    if not 12 <= len(first) <= 256 or first != getpass("Repeat password: "):
        raise SystemExit("Passwords must match and contain 12–256 characters.")
    return passwords.hash(first)

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    provision = sub.add_parser("provision")
    provision.add_argument("--email", required=True)
    provision.add_argument("--workspace", required=True)
    reset = sub.add_parser("reset-password")
    reset.add_argument("--email", required=True)
    remove = sub.add_parser("delete-workspace")
    remove.add_argument("--id", required=True)
    sub.add_parser("revoke-all-access")
    args = parser.parse_args()
    try:
        with Session.begin() as db:
            if args.action == "provision":
                email = args.email.strip().lower()
                name = args.workspace.strip()
                if "@" not in email or len(email) > 254 or not 1 <= len(name) <= 120:
                    raise SystemExit("Provide a valid email and workspace name.")
                w = Workspace(name=name)
                db.add(w)
                db.flush()
                db.add(User(email=email, workspace_id=w.id, password_hash=password_input()))
                print("Workspace ID:", w.id)
            elif args.action == "reset-password":
                user = db.scalar(select(User).where(User.email == args.email.strip().lower()))
                if not user:
                    raise SystemExit("Owner not found.")
                user.password_hash = password_input()
                db.execute(delete(SessionRecord).where(SessionRecord.user_id == user.id))
            elif args.action == "delete-workspace":
                w = db.get(Workspace, args.id)
                if not w:
                    raise SystemExit("Workspace not found.")
                if input("Type the workspace ID to permanently delete it: ") != w.id:
                    raise SystemExit("Cancelled.")
                db.delete(w)
            else:
                if input("Type REVOKE to invalidate all active links and sessions: ") != "REVOKE":
                    raise SystemExit("Cancelled.")
                db.execute(delete(SessionRecord))
                db.execute(delete(Link))
    except IntegrityError:
        raise SystemExit("Operation violates a uniqueness or integrity constraint.") from None

if __name__ == "__main__":
    main()

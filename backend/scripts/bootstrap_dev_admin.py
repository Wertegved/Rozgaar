"""Create or update one development Admin account without opening public Admin registration."""
import os

from sqlalchemy import select

from app.auth.hashing import hash_password
from app.db.models.enums import AccountStatus, UserRole
from app.db.models.users import User
from app.db.session import SessionLocal


def main() -> None:
    if os.getenv("ENVIRONMENT", "development").lower() not in {"development", "test"}:
        raise RuntimeError("Development Admin bootstrap is disabled outside development/test")
    email = os.environ["DEV_ADMIN_EMAIL"].strip().lower()
    password = os.environ["DEV_ADMIN_PASSWORD"]
    name = os.getenv("DEV_ADMIN_NAME", "Development Admin").strip()
    phone = os.environ["DEV_ADMIN_PHONE"].strip()
    session = SessionLocal()
    try:
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(name=name, phone=phone, email=email, password_hash=hash_password(password), role=UserRole.ADMIN, account_status=AccountStatus.ACTIVE)
            session.add(user)
        else:
            user.name, user.phone, user.password_hash = name, phone, hash_password(password)
            user.role, user.account_status = UserRole.ADMIN, AccountStatus.ACTIVE
        session.commit()
        print("Development Admin account is ready.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
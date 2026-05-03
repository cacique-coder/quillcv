"""Quick check: list users in the database."""
import asyncio
from sqlalchemy import select

from app.infrastructure.persistence.database import async_session
from app.infrastructure.persistence.orm_models import User


async def main() -> None:
    async with async_session() as db:
        result = await db.execute(select(User).order_by(User.created_at.desc()))
        users = result.scalars().all()

        if not users:
            print("No users found.")
            return

        print(f"Found {len(users)} user(s):\n")
        for u in users:
            print(f"  id={u.id}")
            print(f"  email={u.email}")
            print(f"  name={u.name!r}")
            print(f"  role={u.role}  active={u.is_active}")
            print(f"  provider={u.provider or 'password'}")
            print(f"  created={u.created_at}  last_login={u.last_login}")
            print()


if __name__ == "__main__":
    asyncio.run(main())

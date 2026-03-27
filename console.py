"""Interactive console for QuillCV — like `rails c`.

Usage: python -i console.py

Examples:
    # Find a user
    user = await run(get_user("xzdasx@gmail.com"))

    # Run raw SQL
    await run(raw("SELECT count(*) FROM users"))

    # Promote to admin
    await run(promote("someone@email.com"))

    # List all invitations
    await run(list_invitations())
"""

import asyncio

from dotenv import load_dotenv

load_dotenv(".env")

from sqlalchemy import select, text, update  # noqa: E402

from app.infrastructure.persistence.database import async_session  # noqa: E402
from app.infrastructure.persistence.orm_models import ExpressionOfInterest, Invitation, User  # noqa: E402


async def get_user(email: str):
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            print(f"  id:    {user.id}")
            print(f"  email: {user.email}")
            print(f"  name:  {user.name}")
            print(f"  role:  {user.role}")
            print(f"  since: {user.created_at}")
        else:
            print(f"  User {email} not found")
        return user


async def promote(email: str):
    async with async_session() as db:
        result = await db.execute(
            update(User).where(User.email == email).values(role="admin")
        )
        await db.commit()
        print(f"  Promoted {result.rowcount} user(s) to admin")


async def list_users():
    async with async_session() as db:
        result = await db.execute(select(User).order_by(User.created_at.desc()))
        for u in result.scalars():
            print(f"  {u.role:8s} {u.email:30s} {u.name}")


async def list_invitations():
    async with async_session() as db:
        result = await db.execute(select(Invitation).order_by(Invitation.created_at.desc()))
        for inv in result.scalars():
            status = f"redeemed by {inv.redeemed_by}" if inv.redeemed_by else "available"
            print(f"  {inv.code:20s} {inv.credits:3d} credits  {status}")


async def list_eoi():
    async with async_session() as db:
        result = await db.execute(select(ExpressionOfInterest).order_by(ExpressionOfInterest.created_at.desc()))
        for eoi in result.scalars():
            print(f"  {eoi.email:30s} {eoi.name or '':20s} {eoi.created_at}")


async def raw(sql: str):
    async with async_session() as db:
        result = await db.execute(text(sql))
        try:
            rows = result.fetchall()
            for row in rows:
                print(f"  {row}")
            return rows
        except Exception:
            await db.commit()
            print("  Done (no rows returned)")


def run(coro):
    """Shortcut: run(get_user('x@y.com'))"""
    return asyncio.run(coro)


print("=" * 50)
print("  QuillCV Console")
print("=" * 50)
print()
print("  run(get_user('email'))     — find a user")
print("  run(promote('email'))      — make admin")
print("  run(list_users())          — all users")
print("  run(list_invitations())    — all invites")
print("  run(list_eoi())            — expressions of interest")
print("  run(raw('SELECT ...'))     — raw SQL")
print()

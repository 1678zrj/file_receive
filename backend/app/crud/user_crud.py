from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from app.models.table import User


class UserCrud:

    async def get_by_username(self, db: AsyncSession, username: str) -> User | None:
        statement = select(User).where(User.username == username)
        result = await db.exec(statement)
        return result.first()

    async def get_by_id(self, db: AsyncSession, id: int) -> User | None:
        statement = select(User).where(User.id == id)
        result = await db.exec(statement)
        return result.first()

    async def create_user(
            self,
            db: AsyncSession,
            user_data_dict: dict
    ) -> User:
        user = User(**user_data_dict)
        db.add(user)
        await db.flush()
        return user


user_crud = UserCrud()

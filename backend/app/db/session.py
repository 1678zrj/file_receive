from collections.abc import AsyncGenerator
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.base import User, Course, Enrollment, Assignment, UserRole, utc_now
from app.core.config import settings


# 考虑PostgreSQL支持的最大连接数是100
# 而一旦产生连接后就不会释放
# 因此最大连接数=pool_size+max_overflow
# 当前最重要的是FastAPI worker和 TaskIQ worker不能共用一套数据库连接池
# 或者worker的最大连接数要小、还有worker数量减小
# 但这些都是治标不治本，后续要引入PgBouncer还有消息异步落库
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=10,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,
    # 针对MySQL的额外优化参数
    # connect_args={
    #     "connect_timeout": 10,     # 连接数据库的超时
    # }
    # 针对PostgreSQL(asyncpg)的优化参数
    connect_args = {
        "timeout": 10,  # asyncpg 的建立连接超时事件
        "command_timeout": 30, # 单条SQL执行超时事件， 防止慢查询拖死连接
    }
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def create_db_and_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def init_test_data() -> None:
    """初始化核心业务表（User, Course, Enrollment, Assignment）的测试数据"""
    async with AsyncSessionLocal() as session:
        print("开始初始化测试数据...")

        # ==========================================
        # 1. 插入用户数据
        # ==========================================
        users_to_create = [
            User(
                role=UserRole.ADMIN,
                username="admin",
                password_hash="$2b$12$2q90ANd77q2yHoRFJwPHFOxMbmKBsCiyqX8KxKY..E9lV26K2x/me",
                real_name="系统管理员",
                email="admin@tests.com",
            ),
            User(
                role=UserRole.TEACHER,
                username="teacher_li",
                password_hash="$2b$12$2q90ANd77q2yHoRFJwPHFOxMbmKBsCiyqX8KxKY..E9lV26K2x/me",
                real_name="李老师",
                email="li@tests.com",
            ),
            User(
                role=UserRole.STUDENT,
                username="student_zhang",
                password_hash="$2b$12$2q90ANd77q2yHoRFJwPHFOxMbmKBsCiyqX8KxKY..E9lV26K2x/me",
                real_name="张同学",
                email="zhang@tests.com",
            ),
            User(
                role=UserRole.STUDENT,
                username="student_wang",
                password_hash="$2b$12$2q90ANd77q2yHoRFJwPHFOxMbmKBsCiyqX8KxKY..E9lV26K2x/me",
                real_name="王同学",
                email="wang@tests.com",
            ),
        ]

        db_users = {}
        for u in users_to_create:
            stmt = select(User).where(User.username == u.username)
            result = await session.execute(stmt)
            existing_user = result.scalar_one_or_none()

            if not existing_user:
                session.add(u)
                await session.flush()
                db_users[u.username] = u
            else:
                db_users[u.username] = existing_user

        await session.commit()
        print("[-] User 数据就绪")

        # ==========================================
        # 2. 插入课程数据
        # ==========================================
        teacher_id = db_users["teacher_li"].id
        courses_to_create = [
            Course(
                name="高级Python编程",
                course_code="CS-201",
                teacher_id=teacher_id,
                overview="深入理解异步和Web框架",
            ),
            Course(
                name="数据库系统原理",
                course_code="CS-301",
                teacher_id=teacher_id,
                overview="SQL与NoSQL实践",
            ),
        ]

        db_courses = {}
        for c in courses_to_create:
            stmt = select(Course).where(Course.course_code == c.course_code)
            result = await session.execute(stmt)
            existing_course = result.scalar_one_or_none()

            if not existing_course:
                session.add(c)
                await session.flush()
                db_courses[c.course_code] = c
            else:
                db_courses[c.course_code] = existing_course

        await session.commit()
        print("[-] Course 数据就绪")

        # ==========================================
        # 3. 插入选课数据
        # ==========================================
        student1_id = db_users["student_zhang"].id
        student2_id = db_users["student_wang"].id
        course1_id = db_courses["CS-201"].id

        enrollments_to_create = [
            Enrollment(student_id=student1_id, course_id=course1_id),
            Enrollment(student_id=student2_id, course_id=course1_id),
        ]

        for e in enrollments_to_create:
            stmt = select(Enrollment).where(
                Enrollment.student_id == e.student_id,
                Enrollment.course_id == e.course_id,
            )
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                session.add(e)

        await session.commit()
        print("[-] Enrollment 数据就绪")

        # ==========================================
        # 4. 插入作业数据
        # ==========================================
        assignments_to_create = [
            Assignment(
                course_id=course1_id,
                title="第一次作业：实现异步爬虫",
                description="请使用 asyncio 和 aiohttp 抓取指定的五个网页。",
                # 关键修改点：改用统一的带时区 utc_now()
                deadline=utc_now() + timedelta(days=7),
            )
        ]

        for a in assignments_to_create:
            stmt = select(Assignment).where(
                Assignment.course_id == a.course_id, Assignment.title == a.title
            )
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                session.add(a)

        await session.commit()
        print("[-] Assignment 数据就绪")
        print("🎉 测试数据初始化完成！")

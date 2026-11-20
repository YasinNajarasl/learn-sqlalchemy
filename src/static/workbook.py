"""SQLAlchemy 2.x workbook. Run with: python workbook.py 1 (or all)."""
import asyncio
import sys
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint, ForeignKey, String, Table, Column, Integer,
    create_engine, delete, event, func, insert, inspect, select, text, update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, selectinload


class Base(DeclarativeBase):
    pass


post_tags = Table(
    "post_tags", Base.metadata,
    Column("post_id", ForeignKey("posts.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("age >= 0"),)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(unique=True)
    age: Mapped[int]
    bio: Mapped[str | None] = mapped_column(default=None)
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    posts: Mapped[list["Post"]] = relationship(back_populates="author", cascade="all, delete-orphan")


class Post(Base):
    __tablename__ = "posts"
    title: Mapped[str]
    content: Mapped[str]
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    author: Mapped[User] = relationship(back_populates="posts")
    tags: Mapped[list["Tag"]] = relationship(secondary=post_tags)


class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)


def fresh_engine():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        alice = User(name="Alice Johnson", age=25, email="alice@example.com", bio="Backend engineer.")
        alice.posts.extend([
            Post(title="Hello SQL", content="A gentle tour of Engine and Session."),
            Post(title="Queries", content="Filter, sort and paginate."),
            Post(title="Relationships", content="One-to-many and many-to-many."),
        ])
        bob = User(name="Bob Smith", age=32, email="bob@example.com", bio="Async enthusiast.")
        bob.posts.extend([
            Post(title="Async access", content="Using AsyncSession without blocking."),
            Post(title="The N+1 problem", content="Why lazy loading multiplies queries."),
        ])
        session.add_all([alice, bob])
    return engine


def lesson_01(engine):
    """Connect and bind a parameter | slides 3–8
    An engine manages connections; a Connection executes SQL. Use text() for literal SQL and pass values separately so the driver binds them as data.
    Change minimum to 30 and predict the names before running. Why would interpolating an email into the SQL string be a bad habit?
    Alice Johnson, Bob Smith
    """
    with engine.connect() as conn:
        names = conn.execute(
            text(
                "SELECT name FROM users "
                "WHERE email IN ('alice@example.com', 'bob@example.com') "
                "AND age >= :minimum ORDER BY name"
            ),
            {"minimum": 20},
        ).scalars()
        print(", ".join(names))


def lesson_02(engine):
    """Design and inspect a schema | slides 9–14
    Read User and Post in the shared setup. Mapped[int] supplies a SQL type, primary_key identifies a row, and ForeignKey requires a matching key in the parent table when enforcement is enabled. Metadata describes the tables before create_all creates them.
    Add a nullable nickname: Mapped[str | None] to User. Re-run and check that nickname appears. Why does this work on a fresh database but not change an existing table?
    name, email, age, bio, id, created_at
    """
    columns = inspect(engine).get_columns("users")
    print(", ".join(col["name"] for col in columns))


def lesson_03(engine):
    """Insert and follow an object through a session | slides 15–17
    Construct a Python object, add it to the unit of work, then flush. Flush sends the INSERT and obtains its generated id; the begin block commits on a successful exit. Closing the session detaches the object.
    Move the second print before flush and inspect pending instead of persistent. Which step first assigns an id?
    True / True True
    """
    with Session(engine) as s, s.begin():
        user = User(name="Cam", email="cam@example.org", age=24)
        s.add(user)
        print(inspect(user).pending)
        s.flush()
        print(inspect(user).persistent, bool(user.id))


def lesson_04(engine):
    """Write a batch without building objects | slide 18
    Pass insert(User) and a list of mappings to execute. The keys are mapped attribute names. The database, rather than a preliminary lookup in Python, enforces the unique email constraint.
    Add a fourth row to the batch. Then duplicate one email and observe where the transaction fails.
    3
    """
    with Session(engine) as s, s.begin():
        emails = [f"u{i}@example.org" for i in range(3)]
        s.execute(insert(User), [
            {
                "name": f"User {i}",
                "age": 21,
                "email": email,
                "created_at": utcnow(),
            }
            for i, email in enumerate(emails)
        ])
        print(
            s.scalar(
                select(func.count()).select_from(User).where(User.email.in_(emails))
            )
        )


def lesson_05(engine):
    """Read, filter, sort and page | slides 19–21
    Build the SELECT before executing it. scalars() unwraps the first selected column (here, User objects). A primary-key tie breaker makes pagination predictable when ages match.
    Change offset to 1 to see the next person. Then use select(User.name, User.age) and s.execute(stmt).all() to return rows rather than objects.
    Bob Smith
    """
    stmt = (
        select(User)
        .where(User.email.in_(["alice@example.com", "bob@example.com"]))
        .order_by(User.age.desc(), User.id)
        .limit(1)
        .offset(0)
    )
    with Session(engine) as s:
        print(s.scalars(stmt).one().name)


def lesson_06(engine):
    """Update and delete rows | slides 22–23
    get() looks up an object by primary key. Assigning a new value marks it dirty. For a set of rows, send a DELETE with a WHERE clause. Link rows in post_tags must be removed before their post when foreign keys are enforced.
    Replace the two DELETE statements with one delete(Post).where(Post.user_id == 1). Why must the PostTag rows go first?
    [('Alice Johnson', 31), ('Bob Smith', 32)]
    """
    with Session(engine) as s, s.begin():
        s.get(User, 1).age = 31
        s.execute(delete(post_tags).where(post_tags.c.post_id == 1))
        s.execute(delete(Post).where(Post.id == 1))
    with Session(engine) as s:
        print(
            s.execute(
                select(User.name, User.age)
                .where(User.email.in_(["alice@example.com", "bob@example.com"]))
                .order_by(User.id)
            ).all()
        )


def lesson_07(engine):
    """Link authors, posts and tags | slides 24–27
    Append a Post to User.posts instead of assigning an id manually. back_populates keeps Post.author in sync in memory. Appending a Tag writes a link row in post_tags; the composite primary key identifies that pair.
    Attach the same Tag object to Alice's second post. Count the link rows and tag rows separately: expect two links but only one tag.
    Alice Johnson: Joins [sql]
    """
    with Session(engine) as s, s.begin():
        alice = s.get(User, 1)
        post = Post(title="Joins", content="Join authors and posts.", tags=[Tag(name="sql")])
        alice.posts.append(post)
        s.flush()
        print(f"{post.author.name}: {post.title} [{post.tags[0].name}]")


def lesson_08(engine):
    """Measure lazy versus eager loading | slides 28–29, 36–37
    Listen for SQL on the engine and count SELECTs. Lazy traversal issues a query for each author's collection. selectinload batches the related posts. Use a fresh session each time so the identity map cannot mask a load.
    Add another author to fresh_engine. Predict which query count changes. In the app, compare the Relationships page against SQL Console.
    lazy 3 / eager 2
    """
    queries = []

    @event.listens_for(engine, "before_cursor_execute")
    def capture(conn, cursor, statement, parameters, context, many):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)

    authors = select(User).where(User.email.in_(["alice@example.com", "bob@example.com"]))
    for label, stmt in [
        ("lazy", authors),
        ("eager", authors.options(selectinload(User.posts))),
    ]:
        with Session(engine) as s:
            queries.clear()
            for author in s.scalars(stmt):
                len(author.posts)
            print(label, len(queries))
    event.remove(engine, "before_cursor_execute", capture)


def lesson_09(engine):
    """Join and aggregate | slides 30–31
    Start from users, outer join posts and group by author. COUNT(posts.id) ignores the NULL introduced for authors with no posts; COUNT(*) would count that outer-join row.
    Change outerjoin to join. Which author disappears? Restore the outer join and add having(func.count(Post.id) >= 1).
    [('Alice Johnson', 3), ('Bob Smith', 2)]
    """
    stmt = (
        select(User.name, func.count(Post.id))
        .where(User.email.in_(["alice@example.com", "bob@example.com"]))
        .outerjoin(User.posts)
        .group_by(User.id, User.name)
        .order_by(User.id)
    )
    with Session(engine) as s:
        print(s.execute(stmt).all())


def lesson_10(engine):
    """Prove a failed transaction rolls back | slide 32
    Both writes belong to one transaction. The duplicate email makes the INSERT fail. Catch the exception outside the begin block so it can roll back before a fresh session reads the age.
    Give the new user a unique email. Predict the age and total number of users, then query both.
    rolled back / 25
    """
    try:
        with Session(engine) as s, s.begin():
            s.execute(update(User).where(User.id == 1).values(age=99))
            s.add(User(name="Duplicate", age=19, email="alice@example.com"))
    except IntegrityError:
        print("rolled back")
    with Session(engine) as s:
        print(s.get(User, 1).age)


def lesson_11(engine):
    """Use an async session | slide 35
    An async engine needs an async driver such as aiosqlite. Bridge metadata DDL with run_sync, create one session per task, and await database I/O. This example creates a separate in-memory database.
    Insert a second user inside the transaction. Change the SELECT to order by name and collect all names instead of one.
    Dee
    """
    async def main():
        db = create_async_engine("sqlite+aiosqlite://")
        async with db.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(db)
        async with sessions.begin() as s:
            s.add(User(name="Dee", age=27, email="dee@example.org"))
        async with sessions() as s:
            print((await s.scalars(select(User.name))).one())
        await db.dispose()
    asyncio.run(main())


def lesson_12(engine):
    """Capstone: publish and verify an author's report | slides 38–43
    Write a function that accepts a session, finds the author by a unique email, and appends a post. Leave the commit to the caller. Test using a second session so an uncommitted change cannot masquerade as a successful write.
    First write publish without looking at the solution below. Add a test for a missing email: expect NoResultFound and verify the post count stays the same. Connect your version to a FastAPI route using src/main.py as a guide.
    Alice Johnson has 4 posts
    """
    def publish(s, email, title):
        user = s.scalars(select(User).where(User.email == email)).one()
        user.posts.append(Post(title=title, content="Published from the capstone lab."))

    with Session(engine) as s, s.begin():
        publish(s, "alice@example.com", "Transactions")
    with Session(engine) as s:
        alice = s.scalars(
            select(User)
            .options(selectinload(User.posts))
            .where(User.email == "alice@example.com")
        ).one()
        assert "Transactions" in [post.title for post in alice.posts]
        print(f"{alice.name} has {len(alice.posts)} posts")


if __name__ == "__main__":
    lessons = [v for k, v in sorted(globals().items()) if k.startswith("lesson_")]
    choice = sys.argv[1] if len(sys.argv) == 2 else ""
    if choice != "all" and choice not in map(str, range(1, len(lessons) + 1)):
        sys.exit(f"Usage: python workbook.py 1..{len(lessons)} | all")
    for number, lesson in enumerate(lessons, 1):
        if choice in ("all", str(number)):
            db = fresh_engine()
            try:
                lesson(db)
            finally:
                db.dispose()
